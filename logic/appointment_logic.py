from firebase_admin import firestore
from datetime import datetime as dt


def get_db():
    return firestore.client()


def create_appointment(user_id: str, data: dict) -> dict:
    """
    Create a new appointment document.
    Saves to both:
    1. users/{user_id}/appointments/{doc_id}
    2. appointments/{doc_id} (Flat collection for Admin access/financials)
    """
    db = get_db()
    
    # ── Fetch User's Real Name from Profile ──────────────────────────────────
    user_name = "Unknown User"
    try:
        user_doc = db.collection("users").document(user_id).get()
        if user_doc.exists:
            u_data = user_doc.to_dict() or {}
            # Try common field names for the user's name
            user_name = u_data.get("fullName") or u_data.get("name") or u_data.get("username") or "Unknown User"
    except Exception as e:
        print(f"[create_appointment] Warning: Could not fetch user name: {e}")

    # Create the reference in the user's subcollection
    user_doc_ref = db.collection("users").document(user_id).collection("appointments").document()
    doc_id = user_doc_ref.id
    
    # Enrich the data with verified user identity
    full_data = {
        **data, 
        "user_id": user_id,
        "user_name": user_name
    }
    
    # Save to user subcollection
    user_doc_ref.set(full_data)
    
    # Mirror to top-level 'appointments' collection will now be handled in approve_appointment
    # in backend_admin/logic/admin_logic.py
    
    return {"id": doc_id, **full_data}


def get_appointments(user_id: str) -> list:
    """Fetch all appointments for a user, ordered by dateTime descending.
    
    Also merges the latest status from the top-level 'appointments' collection
    so that admin approvals are reflected immediately even before the sub-collection
    document is updated in the client cache.
    """
    db = get_db()
    try:
        print(f"[get_appointments] Querying appointments for user: {user_id}")

        # Build a status lookup from the top-level approved/completed collection
        top_level_status: dict = {}
        top_docs = db.collection("appointments").stream()
        for top in top_docs:
            top_data = top.to_dict() or {}
            if top_data.get("user_id") == user_id:
                top_level_status[top.id] = top_data.get("status", "")

        docs = (
            db.collection("users")
            .document(user_id)
            .collection("appointments")
            .stream()
        )
        results = []
        for doc in docs:
            data = doc.to_dict()
            print(f"[get_appointments] Found doc {doc.id}: {data}")
            entry = {"id": doc.id, **data}
            # If the top-level collection has a newer/more authoritative status, use it
            if doc.id in top_level_status and top_level_status[doc.id]:
                entry["status"] = top_level_status[doc.id]
            results.append(entry)
        print(f"[get_appointments] Total appointments found: {len(results)}")
        # Sort in Python to avoid requiring a Firestore composite index
        results.sort(key=lambda x: str(x.get("dateTime", "")), reverse=True)
        return results
    except Exception as e:
        print(f"[get_appointments] Error fetching appointments for {user_id}: {e}")
        raise


def cancel_appointment(user_id: str, appointment_id: str) -> dict:
    """
    Cancel an appointment initiated by the USER.

    Refund Matrix (user-initiated):
      - status == 'pending'  → full refund (amountPaidOnline returned)
      - status == 'approved' → no refund (downpayment forfeited)
    """
    import requests, base64, os
    from datetime import datetime as dt

    PAYMONGO_SECRET_KEY = os.getenv("PAYMONGO_SECRET_KEY")

    db = get_db()

    user_doc_ref = (
        db.collection("users")
        .document(user_id)
        .collection("appointments")
        .document(appointment_id)
    )
    doc = user_doc_ref.get()
    if not doc.exists:
        return {"error": "Appointment not found"}

    data = doc.to_dict() or {}
    current_status = data.get("status", "pending")
    amount_paid = float(data.get("amountPaidOnline", 0) or 0)
    checkout_session_id = data.get("checkoutSessionId", "")

    # ── Determine refund eligibility ──────────────────────────────────────────
    if current_status in ("pending", "scheduled"):
        # Full refund
        refund_status = "refunded" if (amount_paid > 0 and checkout_session_id) else (
            "refund_not_needed" if amount_paid == 0 else "refund_pending"
        )
        refund_note = "Full refund processed — appointment was still pending."
        refund_amount = amount_paid
    elif current_status == "approved":
        # No refund — downpayment forfeited
        refund_status = "forfeited"
        refund_note = "No refund — appointment was already approved."
        refund_amount = 0.0
    else:
        refund_status = "not_applicable"
        refund_note = "Appointment was not in a refundable state."
        refund_amount = 0.0

    # ── Attempt PayMongo refund if eligible ────────────────────────────────────
    paymongo_refund_id = None
    if refund_status == "refunded" and checkout_session_id:
        try:
            auth_bytes = f"{PAYMONGO_SECRET_KEY}:".encode("ascii")
            b64 = base64.b64encode(auth_bytes).decode("ascii")
            headers = {
                "accept": "application/json",
                "Content-Type": "application/json",
                "authorization": f"Basic {b64}",
            }
            # Retrieve the payment_id from the checkout session
            session_resp = requests.get(
                f"https://api.paymongo.com/v1/checkout_sessions/{checkout_session_id}",
                headers=headers,
            )
            if session_resp.status_code == 200:
                session_data = session_resp.json()
                payment_id = (
                    session_data.get("data", {})
                    .get("attributes", {})
                    .get("payment_intent", {})
                    .get("id")
                )
                if payment_id:
                    # Retrieve the payment to get the actual payment resource ID
                    pi_resp = requests.get(
                        f"https://api.paymongo.com/v1/payment_intents/{payment_id}",
                        headers=headers,
                    )
                    if pi_resp.status_code == 200:
                        pi_data = pi_resp.json()
                        payments = pi_data.get("data", {}).get("attributes", {}).get("payments", [])
                        if payments:
                            actual_payment_id = payments[0].get("id")
                            refund_payload = {
                                "data": {
                                    "attributes": {
                                        "amount": int(refund_amount * 100),
                                        "payment_id": actual_payment_id,
                                        "reason": "customer_requested",
                                        "notes": "User cancelled pending appointment — full refund issued.",
                                    }
                                }
                            }
                            refund_resp = requests.post(
                                "https://api.paymongo.com/v1/refunds",
                                json=refund_payload,
                                headers=headers,
                            )
                            if refund_resp.status_code in (200, 201):
                                paymongo_refund_id = refund_resp.json().get("data", {}).get("id")
                                refund_status = "refunded"
                            else:
                                print(f"[cancel_appointment] PayMongo refund failed: {refund_resp.text}")
                                refund_status = "refund_pending"
        except Exception as e:
            print(f"[cancel_appointment] Refund error: {e}")
            refund_status = "refund_pending"

    # ── Update Firestore ───────────────────────────────────────────────────────
    cancelled_at = dt.utcnow().isoformat()
    update_payload = {
        "status": "cancelled",
        "cancelledBy": "user",
        "cancelledAt": cancelled_at,
        "refundStatus": refund_status,
        "refundNote": refund_note,
        "refundAmount": refund_amount,
    }
    if paymongo_refund_id:
        update_payload["paymongoRefundId"] = paymongo_refund_id

    user_doc_ref.update(update_payload)

    top_doc_ref = db.collection("appointments").document(appointment_id)
    if top_doc_ref.get().exists:
        top_doc_ref.update(update_payload)

    updated = user_doc_ref.get()
    return {
        "id": updated.id,
        "refund_status": refund_status,
        "refund_amount": refund_amount,
        **updated.to_dict(),
    }


def reschedule_appointment(user_id: str, appointment_id: str, new_datetime: str) -> dict:
    """
    Reschedule a PENDING appointment to a new date/time.

    Rules:
      - Only allowed when status in ('pending', 'scheduled')
      - Downpayment and all payment fields are preserved
      - Status stays 'pending' so the vet must re-confirm
      - new_datetime must be ISO 8601 (e.g. "2026-05-10T14:00:00")
    """
    db = get_db()

    user_ref = (
        db.collection("users")
        .document(user_id)
        .collection("appointments")
        .document(appointment_id)
    )
    doc = user_ref.get()
    if not doc.exists:
        return {"error": "Appointment not found"}

    data = doc.to_dict() or {}
    current_status = data.get("status", "")

    if current_status not in ("pending", "scheduled"):
        return {"error": f"Cannot reschedule appointment with status '{current_status}'"}

    try:
        parsed = dt.fromisoformat(new_datetime)
    except ValueError:
        return {"error": "Invalid datetime format. Use ISO 8601."}

    if parsed <= dt.utcnow():
        return {"error": "New appointment time must be in the future"}

    update_payload = {
        "dateTime": new_datetime,
        "rescheduledAt": dt.utcnow().isoformat(),
        "status": "pending",
    }

    user_ref.update(update_payload)

    top_ref = db.collection("appointments").document(appointment_id)
    if top_ref.get().exists:
        top_ref.update(update_payload)

    updated = user_ref.get()
    return {"id": appointment_id, **updated.to_dict()}


def accept_reschedule(user_id: str, appointment_id: str) -> dict:
    """
    User accepts the proposed reschedule.
    - dateTime ← proposedDateTime
    - status ← 'approved'
    """
    db = get_db()
    user_ref = (
        db.collection("users")
        .document(user_id)
        .collection("appointments")
        .document(appointment_id)
    )
    doc = user_ref.get()
    if not doc.exists:
        return {"error": "Appointment not found"}

    data = doc.to_dict() or {}
    if data.get("status") != "reschedule_proposed":
        return {"error": "Appointment is not in reschedule_proposed state"}

    proposed = data.get("proposedDateTime", "")
    if not proposed:
        return {"error": "No proposed date/time found"}

    payload = {
        "dateTime": proposed,
        "status": "scheduled",
        "proposedDateTime": "",
    }
    user_ref.update(payload)

    # Mirror to top-level collection so doctors can see it
    full_payload = {**data, **payload, "user_id": user_id}
    db.collection("appointments").document(appointment_id).set(full_payload, merge=True)

    updated = user_ref.get()
    return {"id": appointment_id, **updated.to_dict()}


def decline_reschedule(user_id: str, appointment_id: str) -> dict:
    """
    User declines the proposed reschedule.
    - status ← 'cancelled'
    - Full refund of downpayment via PayMongo
    """
    import base64, requests as req, os
    PAYMONGO_SECRET_KEY = os.getenv("PAYMONGO_SECRET_KEY")

    db = get_db()
    user_ref = (
        db.collection("users")
        .document(user_id)
        .collection("appointments")
        .document(appointment_id)
    )
    doc = user_ref.get()
    if not doc.exists:
        return {"error": "Appointment not found"}

    data = doc.to_dict() or {}
    if data.get("status") != "reschedule_proposed":
        return {"error": "Appointment is not in reschedule_proposed state"}

    amount_paid = float(data.get("amountPaidOnline", 0) or 0)
    session_id = data.get("checkoutSessionId", "")
    refund_status = "refund_not_needed"

    if session_id and amount_paid > 0:
        auth = base64.b64encode(f"{PAYMONGO_SECRET_KEY}:".encode()).decode()
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "authorization": f"Basic {auth}",
        }
        try:
            sess = req.get(
                f"https://api.paymongo.com/v1/checkout_sessions/{session_id}",
                headers=headers, timeout=10,
            )
            pi_id = (sess.json().get("data", {})
                     .get("attributes", {})
                     .get("payment_intent", {})
                     .get("id")) if sess.status_code == 200 else None

            if pi_id:
                pi = req.get(
                    f"https://api.paymongo.com/v1/payment_intents/{pi_id}",
                    headers=headers, timeout=10,
                )
                payments = (pi.json().get("data", {})
                            .get("attributes", {})
                            .get("payments", [])) if pi.status_code == 200 else []
                if payments:
                    refund = req.post(
                        "https://api.paymongo.com/v1/refunds",
                        json={"data": {"attributes": {
                            "amount": int(amount_paid * 100),
                            "payment_id": payments[0]["id"],
                            "reason": "others",
                            "notes": "User declined proposed reschedule. Full refund issued.",
                        }}},
                        headers=headers, timeout=10,
                    )
                    refund_status = "refunded" if refund.status_code in (200, 201) else "refund_pending"
        except Exception as e:
            print(f"[decline_reschedule] Refund error: {e}")
            refund_status = "refund_pending"

    cancelled_at = dt.utcnow().isoformat()
    payload = {
        "status": "cancelled",
        "cancelledBy": "user_declined_reschedule",
        "cancelledAt": cancelled_at,
        "refundStatus": refund_status,
        "refundAmount": amount_paid,
        "refundNote": "User declined proposed reschedule. Full refund processed.",
        "proposedDateTime": "",
    }
    user_ref.update(payload)

    # Mirror to top-level collection
    db.collection("appointments").document(appointment_id).set({**data, **payload, "user_id": user_id}, merge=True)

    updated = user_ref.get()
    return {"id": appointment_id, "refund_status": refund_status, "refund_amount": amount_paid, **updated.to_dict()}
