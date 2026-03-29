from pydantic import BaseModel
from typing import Optional


class AppointmentCreate(BaseModel):
    service: str
    pet: str
    doctor: str
    dateTime: str  # ISO 8601 string
    status: str = "pending"


class AppointmentCancel(BaseModel):
    appointment_id: str
