from pydantic import BaseModel
from typing import Optional

class PetModel(BaseModel):
    petType: str
    name: str
    breed: str
    gender: str
    age: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    birthday: Optional[str] = ""
    characteristics: Optional[str] = ""
    imageUrl: str = ""
    isDeceased: bool = False