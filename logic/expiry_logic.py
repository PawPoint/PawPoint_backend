"""
expiry_logic.py
───────────────
Background task: auto-cancel stale pending appointments.

Trigger:  appointment status in ('pending', 'scheduled')
          AND  dateTime <= utcnow + 5 hours

Action:
  1. Set status → 'auto_cancelled'
  2. Process 100% PayMongo refund (if checkoutSessionId present)
  3. Write in-app notification to users/{uid}/notifications/
"""

import base64
import requests
import os
from datetime import datetime, timezone, timedelta
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# ── Constants ──────────────────────────────────────────────────────────────────
PAYMONGO_SECRET_KEY = os.getenv("PAYMONGO_SECRET_KEY")
EXPIRY_WINDOW_HOURS = 5   # cancel if appointment is ≤ this many hours away


def get_db():
    return firestore.client()


# ── PayMongo refund helper ─────────────────────────────────────────────────────

def _paymongo_headers() -> dict:
    auth = base64.b64encode(f"{PAYMONGO_SECRET_KEY}:".encode()).decode()
    return {
        "accept": "application/json",
        "Content-Type": "application/json",
        "authorization": f"Basic {auth}",
    }


def _attempt_refund(checkout_session_id: str, amount: float) -> str:
    """
    Try to refund via PayMongo. Returns the resulting refund_status string.
    """
    if not checkout_session_id or amount <= 0:
        return "refund_not_needed" if amount == 0 else "refund_pending"

    headers = _paymongo_headers()
    try:
        # 1. Get payment_intent from the checkout session
        sess = requests.get(
            f"https://api.paymongo.com/v1/checkout_sessions/{checkout_session_id}",
            headers=headers,
            timeout=10,
        )
        if sess.status_code != 200:
            print(f"[expiry] Session lookup failed: {sess.text}")
            return "refund_pending"

        pi_id = (
            sess.json()
            .get("data", {})
            .get("attributes", {})
            .get("payment_intent", {})
            .get("id")
        )
        if not pi_id:
            return "refund_pending"

        # 2. Get payments from the payment_intent
        pi = requests.get(
            f"https://api.paymongo.com/v1/payment_intents/{pi_id}",
            headers=headers,
            timeout=10,
        )
        if pi.status_code != 200:
            return "refund_pending"

        payments = (
            pi.json()
            .get("data", {})
            .get("attributes", {})
            .get("payments", [])
        )
        if not payments:
            return "refund_pending"

        payment_id = payments[0].get("id")

        # 3. Issue refund
        refund = requests.post(
            "https://api.paymongo.com/v1/refunds",
            json={
                "data": {
                    "attributes": {
                        "amount": int(amount * 100),
                        "payment_id": payment_id,
                        "reason": "others",
                        "notes": "Auto-cancelled: clinic did not confirm in time.",
                    }
                }
            },
            headers=headers,
            timeout=10,
        )
        if refund.status_code in (200, 201):
            return "refunded"
        else:
            print(f"[expiry] Refund API error: {refund.text}")
            return "refund_pending"

    except Exception as e:
        print(f"[expiry] Refund exception: {e}")
        return "refund_pending"


# ── Notification writer ────────────────────────────────────────────────────────

def _write_notification(db, user_id: str, appt_id: str, data: dict,
                        amount_paid: float, refund_status: str):
    notif_id = f"auto_cancelled_{appt_id}"
    ref = (
        db.collection("users")
        .document(user_id)
        .collection("notifications")
        .document(notif_id)
    )
    if ref.get().exists:
        return  # already written

    service = data.get("service", "your appointment")
    pet = data.get("pet", "your pet")
    appt_dt_raw = data.get("dateTime", "")
    date_str = appt_dt_raw[:10] if appt_dt_raw else "the scheduled date"

    refund_line = ""
    if refund_status == "refunded":
        refund_line = f" A full refund of PHP {amount_paid:.0f} has been initiated."
    elif refund_status == "refund_pending":
        refund_line = f" Your refund of PHP {amount_paid:.0f} is being processed."

    ref.set({
        "id": notif_id,
        "type": "vetCancelled",
        "title": "Appointment Auto-Cancelled ⏰",
        "body": (
            f"We're sorry — your {service} appointment for {pet} on {date_str} "
            f"was automatically cancelled because the clinic could not confirm it in time."
            f"{refund_line}"
        ),
        "isRead": False,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "appointmentId": appt_id,
        "service": service,
        "pet": pet,
    })


# ── Main job ───────────────────────────────────────────────────────────────────

def auto_expire_pending_appointments():
    """
    Scans every user's appointment subcollection for stale pending appointments
    and auto-cancels them.  Called by APScheduler every 15 minutes.
    """
    db = get_db()
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc + timedelta(hours=EXPIRY_WINDOW_HOURS)

    print(f"[expiry] Running at {now_utc.isoformat()} | cutoff={cutoff.isoformat()}")

    expired_count = 0
    users = db.collection("users").stream()

    for user_doc in users:
        uid = user_doc.id
        appts = (
            db.collection("users")
            .document(uid)
            .collection("appointments")
            .where(filter=FieldFilter("status", "in", ["pending", "scheduled"]))
            .stream()
        )

        for appt in appts:
            data = appt.to_dict() or {}
            dt_raw = data.get("dateTime", "")
            if not dt_raw:
                continue

            # Parse dateTime (stored as ISO string)
            try:
                appt_dt = datetime.fromisoformat(dt_raw)
                # Ensure timezone-aware
                if appt_dt.tzinfo is None:
                    appt_dt = appt_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            # Only expire if appointment is at or within the cutoff window
            if appt_dt > cutoff:
                continue

            appt_id = appt.id
            amount_paid = float(data.get("amountPaidOnline", 0) or 0)
            session_id = data.get("checkoutSessionId", "")

            print(f"[expiry] Auto-cancelling {appt_id} for user {uid} "
                  f"(scheduled={dt_raw}, paid=PHP {amount_paid})")

            # 1. Attempt refund
            refund_status = _attempt_refund(session_id, amount_paid)

            # 2. Build update payload
            cancelled_at = now_utc.isoformat()
            payload = {
                "status": "auto_cancelled",
                "cancelledBy": "system",
                "cancelledAt": cancelled_at,
                "refundStatus": refund_status,
                "refundAmount": amount_paid,
                "refundNote": (
                    "Auto-cancelled: clinic did not confirm in time. "
                    "Full refund issued." if refund_status in ("refunded", "refund_pending")
                    else "Auto-cancelled: no payment was made."
                ),
            }

            # 3. Update user subcollection
            user_ref = (
                db.collection("users")
                .document(uid)
                .collection("appointments")
                .document(appt_id)
            )
            user_ref.update(payload)

            # 4. Update top-level appointments (if mirrored)
            top_ref = db.collection("appointments").document(appt_id)
            if top_ref.get().exists:
                top_ref.update(payload)

            # 5. Write notification
            _write_notification(db, uid, appt_id, data, amount_paid, refund_status)

            expired_count += 1

    print(f"[expiry] Done. Auto-cancelled {expired_count} appointment(s).")
