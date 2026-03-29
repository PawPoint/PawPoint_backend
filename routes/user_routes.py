from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from firebase_admin import firestore, auth

router = APIRouter()


class UpdateProfileRequest(BaseModel):
    name: str
    phone: Optional[str] = ""
    address: Optional[str] = ""
    photoUrl: Optional[str] = None


def get_db():
    return firestore.client()


@router.get("/api/users/{uid}/profile")
async def get_user_profile(uid: str):
    """Fetch user profile data from Firestore using Admin SDK (bypasses security rules)."""
    try:
        db = get_db()
        doc = db.collection("users").document(uid).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="User not found.")
        data = doc.to_dict()
        # Remove sensitive fields before returning
        data.pop("createdAt", None)
        return {"status": "success", "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/users/{uid}/profile")
async def update_user_profile(uid: str, body: UpdateProfileRequest):
    """Update user profile in Firestore using Admin SDK (bypasses security rules)."""
    try:
        db = get_db()
        updates = {
            "name": body.name,
            "phone": body.phone or "",
            "address": body.address or "",
        }
        if body.photoUrl is not None:
            updates["photoUrl"] = body.photoUrl

        db.collection("users").document(uid).set(updates, merge=True)

        # Also update Firebase Auth display name
        try:
            auth.update_user(uid, display_name=body.name)
        except Exception:
            pass  # Non-critical

        return {"status": "success", "message": "Profile updated successfully!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/users/{uid}/pets")
async def get_user_pets(uid: str):
    """Fetch all pets for a user from Firestore using Admin SDK."""
    try:
        db = get_db()
        pets_ref = db.collection("users").document(uid).collection("pets")
        docs = pets_ref.order_by("name").stream()
        pets = []
        for doc in docs:
            pet_data = doc.to_dict()
            pet_data["id"] = doc.id
            # Convert SERVER_TIMESTAMP to string if present
            if "createdAt" in pet_data and pet_data["createdAt"] is not None:
                try:
                    pet_data["createdAt"] = pet_data["createdAt"].isoformat()
                except Exception:
                    pet_data["createdAt"] = str(pet_data["createdAt"])
            pets.append(pet_data)
        return {"status": "success", "pets": pets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
