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
    """Fetch all appointments for a user, ordered by dateTime descending."""
    db = get_db()
    try:
        print(f"[get_appointments] Querying appointments for user: {user_id}")
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
            results.append({"id": doc.id, **data})
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
