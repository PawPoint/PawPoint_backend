from fastapi import APIRouter, Depends
from models.auth_model import LoginRequest, SignupRequest, LoginResponse, UserModel
from logic.auth_logic import AuthService

router = APIRouter()

# Firebase Web API key (from firebase_options.dart — pawpoint-8822d project)
FIREBASE_API_KEY = "AIzaSyB5pNeP4s5f3WF8Du6_oVTNce7vykswgc0"

def get_auth_service():
    return AuthService(api_key=FIREBASE_API_KEY)


@router.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest, service: AuthService = Depends(get_auth_service)):
    """
    Authenticate a user with email and password.
    Returns uid, email, token, and role.
    """
    result = service.login(email=request.email, password=request.password)
    return result


@router.post("/api/auth/signup", response_model=UserModel)
async def signup(request: SignupRequest, service: AuthService = Depends(get_auth_service)):
    """
    Create a new user account.
    Saves uid, email, name, phone, address, role, and createdAt in Firestore.
    """
    result = service.signup(
        email=request.email,
        password=request.password,
        confirm_password=request.confirm_password,
        name=request.name,
        phone=request.phone,
        address=request.address,
        role=request.role or "customer",  # default role if not provided
    )
    return result
