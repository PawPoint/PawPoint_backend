from firebase_admin import firestore
from fastapi import HTTPException

class PetService:
    def __init__(self):
        # Because we initialized app in main.py, this will automatically work!
        self.db = firestore.client()

    def add_pet_to_user(self, uid: str, pet_data: dict):
        try:
            pet_data["createdAt"] = firestore.SERVER_TIMESTAMP
            
            # Save to Firestore
            self.db.collection("users").document(uid).collection("pets").add(pet_data)
            
            return {"status": "success", "message": f"{pet_data.get('name')} added successfully!"}
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    def get_all_pets(self, uid: str):
        try:
            # Go to the exact subcollection we saw in your Firebase screenshot
            pets_ref = self.db.collection("users").document(uid).collection("pets").get()
            
            pets_list = []
            for doc in pets_ref:
                pet_data = doc.to_dict()
                # Grab the document ID and attach it so Flutter knows exactly which pet is which
                pet_data["id"] = doc.id
                # Sanitize non-JSON-serializable Firestore types (e.g. DatetimeWithNanoseconds)
                pet_data = self._sanitize(pet_data)
                pets_list.append(pet_data)
                
            return {"pets": pets_list}
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def _sanitize(data: dict) -> dict:
        """Convert Firestore non-JSON-serializable types to JSON-safe equivalents."""
        from datetime import datetime
        safe = {}
        for k, v in data.items():
            if isinstance(v, datetime):
                safe[k] = v.isoformat()
            elif hasattr(v, 'isoformat'):          # DatetimeWithNanoseconds & similar
                safe[k] = v.isoformat()
            elif isinstance(v, dict):
                safe[k] = PetService._sanitize(v)
            else:
                safe[k] = v
        return safe