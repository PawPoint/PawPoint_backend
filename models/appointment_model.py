from pydantic import BaseModel
from typing import Optional


class AppointmentCreate(BaseModel):
    service: str
    pet: str
    doctor: str
    dateTime: str  # ISO 8601 string
    status: str = "pending"
    
    # ── Payment Fields ────────────────────────────────────────────────────────
    totalPrice: float = 0.0
    amountPaidOnline: float = 0.0
    balanceRemaining: float = 0.0
    paymentStatus: str = "unpaid"
    paymentMethod: str = ""


class AppointmentCancel(BaseModel):
    appointment_id: str
