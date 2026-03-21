from pydantic import BaseModel
from typing import Optional

class LoginRequest(BaseModel):
    email: str
    password: str

class SignupRequest(BaseModel):
    email: str
    password: str
    confirmPassword: str
    name: str
    phone: str
    address: str

class AuthResponse(BaseModel):
    status: str
    message: str
    uid: Optional[str] = None
    email: Optional[str] = None
    token: Optional[str] = None
