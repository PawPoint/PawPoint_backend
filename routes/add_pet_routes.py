from fastapi import APIRouter, Depends
from models.add_pet_model import PetModel
from logic.add_pet_logic import PetService

# This acts like a mini-FastAPI app just for pets
router = APIRouter()

# Dependency Provider: Creates an instance of your OOP class
def get_pet_service():
    return PetService()

@router.post("/api/users/{uid}/pets")
async def add_pet(uid: str, pet: PetModel, service: PetService = Depends(get_pet_service)):
    # Call the method from your OOP class!
    return service.add_pet_to_user(uid, pet.model_dump())