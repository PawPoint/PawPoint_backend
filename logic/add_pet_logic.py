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
            
    # In the future, you can easily add methods here like:
    # def get_all_pets(self, uid: str): ...
    # def delete_pet(self, uid: str, pet_id: str): ...