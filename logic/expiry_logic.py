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


# ── Notification writer ────────────────────────────────────────────────────────

def _write_notification(db, user_id: str, appt_id: str, data: dict):
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

    ref.set({
        "id": notif_id,
        "type": "vetCancelled",
        "title": "Appointment Auto-Cancelled ⏰",
        "body": (
            f"We're sorry — your {service} appointment for {pet} on {date_str} "
            f"was automatically cancelled because the clinic could not confirm it in time."
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

            print(f"[expiry] Auto-cancelling {appt_id} for user {uid} "
                  f"(scheduled={dt_raw}, paid=PHP {amount_paid})")

            # 1. Build update payload
            cancelled_at = now_utc.isoformat()
            payload = {
                "status": "auto_cancelled",
                "cancelledBy": "system",
                "cancelledAt": cancelled_at,
                "refundStatus": "not_applicable",
                "refundAmount": 0.0,
                "refundNote": "Auto-cancelled: clinic did not confirm in time.",
            }

            # 2. Update user subcollection
            user_ref = (
                db.collection("users")
                .document(uid)
                .collection("appointments")
                .document(appt_id)
            )
            user_ref.update(payload)

            # 3. Update top-level appointments (if mirrored)
            top_ref = db.collection("appointments").document(appt_id)
            if top_ref.get().exists:
                top_ref.update(payload)

            # 4. Write notification
            _write_notification(db, uid, appt_id, data)

            expired_count += 1

    print(f"[expiry] Done. Auto-cancelled {expired_count} appointment(s).")

