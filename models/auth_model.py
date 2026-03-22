from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class UserModel(BaseModel):
    uid: str
    email: EmailStr
    name: str
    phone: str
    address: str
    role: str = Field(default="customer")  # <-- new field for role
    createdAt: Optional[str] = None


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    confirm_password: str
    name: str
    phone: str
    address: str
    role: Optional[str] = Field(default="customer")  # allow admin/customer


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    status: str
    message: str
    uid: str
    email: EmailStr
    token: str
    role: str  # <-- include role in login response
