from fastapi import APIRouter, Depends
from models.add_pet_model import PetModel
from logic.add_pet_logic import PetService
from dependencies import verify_user_token

router = APIRouter()

def get_pet_service():
    return PetService()

@router.post("/api/pets")
async def add_pet(
    pet: PetModel, 
    uid: str = Depends(verify_user_token), # <-- Catches the token and gets the UID securely!
    service: PetService = Depends(get_pet_service)
):
    # Pass the secure uid straight to your logic
    return service.add_pet_to_user(uid, pet.model_dump())

@router.get("/api/pets")
async def get_pets(
    uid: str = Depends(verify_user_token), 
    service: PetService = Depends(get_pet_service)
):
    return service.get_all_pets(uid)