from firebase_admin import firestore


def get_db():
    return firestore.client()


def create_appointment(user_id: str, data: dict) -> dict:
    """Create a new appointment document under the user's subcollection."""
    db = get_db()
    doc_ref = db.collection("users").document(user_id).collection("appointments").document()
    doc_ref.set(data)
    return {"id": doc_ref.id, **data}


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
    """Update an appointment's status to 'cancelled'."""
    db = get_db()
    doc_ref = (
        db.collection("users")
        .document(user_id)
        .collection("appointments")
        .document(appointment_id)
    )
    doc = doc_ref.get()
    if not doc.exists:
        return {"error": "Appointment not found"}

    doc_ref.update({"status": "cancelled"})
    updated = doc_ref.get()
    return {"id": updated.id, **updated.to_dict()}
