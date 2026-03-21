from fastapi import APIRouter, Depends
from models.auth_model import LoginRequest, SignupRequest
from logic.auth_logic import AuthService

router = APIRouter()

# Firebase Web API key (from firebase_options.dart — pawpoint-8822d project)
FIREBASE_API_KEY = "AIzaSyB5pNeP4s5f3WF8Du6_oVTNce7vykswgc0"

def get_auth_service():
    return AuthService(api_key=FIREBASE_API_KEY)


@router.post("/api/auth/login")
async def login(request: LoginRequest, service: AuthService = Depends(get_auth_service)):
    """Authenticate a user with email and password."""
    return service.login(email=request.email, password=request.password)


@router.post("/api/auth/signup")
async def signup(request: SignupRequest, service: AuthService = Depends(get_auth_service)):
    """Create a new user account."""
    return service.signup(
        email=request.email,
        password=request.password,
        confirm_password=request.confirmPassword,
        name=request.name,
        phone=request.phone,
        address=request.address,
    )
