from firebase_admin import firestore
from datetime import datetime as dt


def get_db():
    return firestore.client()


def create_appointment(user_id: str, data: dict) -> dict:
    """
    Create a new appointment document.
    Saves to both:
    1. users/{user_id}/appointments/{doc_id}
    2. appointments/{doc_id} (Flat collection for Admin access)
    This ensures near-instant loading for the Admin Dashboard.
    """
    db = get_db()
    batch = db.batch()
    
    # ── Fetch User's Real Name and Email ──────────────────────────────────
    user_name = "Unknown User"
    user_email = ""
    try:
        user_doc = db.collection("users").document(user_id).get()
        if user_doc.exists:
            u_data = user_doc.to_dict() or {}
            user_name = u_data.get("fullName") or u_data.get("name") or u_data.get("username") or "Unknown User"
            user_email = u_data.get("email", "")
    except Exception as e:
        print(f"[create_appointment] Warning: Could not fetch user data: {e}")

    # 1. Create a reference in the user's subcollection
    user_ref = db.collection("users").document(user_id).collection("appointments").document()
    doc_id = user_ref.id
    
    # 2. Create the exact same reference in the top-level collection
    top_ref = db.collection("appointments").document(doc_id)
    
    full_data = {
        **data, 
        "id": doc_id,
        "user_id": user_id,
        "user_name": user_name,
        "user_email": user_email,
        "createdAt": dt.utcnow().isoformat(),
    }
    
    # ── Atomic Write ─────────────────────────────────────────────────────────
    batch.set(user_ref, full_data)
    batch.set(top_ref, full_data)
    batch.commit()
    
    return full_data


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
        top_docs = db.collection("appointments").where("user_id", "==", user_id).stream()
        for top in top_docs:
            top_data = top.to_dict() or {}
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
            # ── Status merge logic ─────────────────────────────────────
            # Terminal statuses set directly on the user sub-collection should
            # NEVER be overridden by the top-level collection, which may lag.
            _TERMINAL_STATUSES = {"rejected", "cancelled", "auto_cancelled", "completed"}
            sub_status = entry.get("status", "")
            if doc.id in top_level_status and top_level_status[doc.id]:
                top_status = top_level_status[doc.id]
                # Only use the top-level status if the sub-collection does NOT
                # already hold a final/terminal value.
                if sub_status not in _TERMINAL_STATUSES:
                    entry["status"] = top_status
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
      - ANY status (pending, scheduled, approved) → No refund (downpayment forfeited)
    """
    from datetime import datetime as dt

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
    amount_paid = float(data.get("amountPaidOnline", 0) or 0)

    # ── Determine refund eligibility ──────────────────────────────────────────
    # Requirement: No refund for user-initiated cancellations.
    refund_status = "forfeited"
    refund_note = "No refund — downpayment forfeited (user-initiated cancellation)."
    refund_amount = 0.0

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

    user_doc_ref.update(update_payload)

    top_doc_ref = db.collection("appointments").document(appointment_id)
    if top_doc_ref.get().exists:
        top_doc_ref.update(update_payload)

    # ── Send cancellation confirmation email to user ───────────────────────────
    try:
        from logic.email_logic import send_cancellation_email
        user_doc = db.collection("users").document(user_id).get()
        u_data = user_doc.to_dict() or {}
        user_email = u_data.get("email")
        user_name = u_data.get("name") or u_data.get("fullName") or "Valued Customer"
        if user_email:
            send_cancellation_email(
                to_email=user_email,
                user_name=user_name,
                appointment_id=appointment_id,
                service_name=data.get("service", "your appointment"),
                pet_name=data.get("pet", "your pet"),
                appointment_date=data.get("dateTime", ""),
                amount_refunded=amount_paid,
                reason="User-initiated cancellation.",
                refunded=False,   # no refund — downpayment forfeited
            )
    except Exception as e:
        print(f"[cancel_appointment] Email notification failed: {e}")

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
    - No refund processed.
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

    amount_paid = float(data.get("amountPaidOnline", 0) or 0)
    cancelled_at = dt.utcnow().isoformat()
    payload = {
        "status": "cancelled",
        "cancelledBy": "user_declined_reschedule",
        "cancelledAt": cancelled_at,
        "refundStatus": "not_applicable",
        "refundAmount": 0.0,
        "refundNote": "User declined proposed reschedule. No refund processed.",
        "proposedDateTime": "",
    }
    user_ref.update(payload)

    # Mirror to top-level collection
    db.collection("appointments").document(appointment_id).set({**data, **payload, "user_id": user_id}, merge=True)

    # ── Send Email Notification ──────────────────────────────
    try:
        from logic.email_logic import send_cancellation_email
        # Fetch user email and name
        user_doc = db.collection("users").document(user_id).get()
        u_data = user_doc.to_dict() or {}
        user_email = u_data.get("email")
        user_name = u_data.get("name") or u_data.get("fullName") or "Valued Customer"
        
        if user_email:
            service = data.get("service", "your appointment")
            pet = data.get("pet", "your pet")
            appt_dt = data.get("dateTime", "")
            send_cancellation_email(
                to_email=user_email,
                user_name=user_name,
                appointment_id=appointment_id,
                service_name=service,
                pet_name=pet,
                appointment_date=appt_dt,
                amount_refunded=0.0,
                reason="User declined the proposed rescheduled date/time.",
                refunded=False
            )
    except Exception as e:
        print(f"[decline_reschedule] Email sending failed: {e}")

    updated = user_ref.get()
    return {"id": appointment_id, "refund_status": "not_applicable", "refund_amount": 0.0, **updated.to_dict()}

