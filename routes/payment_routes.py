from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from logic.payment_logic import create_paymongo_checkout, verify_paymongo_session

router = APIRouter()

class CheckoutRequest(BaseModel):
    amount: float
    service_name: str

@router.post("/create-checkout")
async def create_checkout(request: CheckoutRequest):
    result = create_paymongo_checkout(request.amount, request.service_name)
    if result:
        return {
            "checkout_url": result["checkout_url"],
            "session_id": result["session_id"],
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to create PayMongo checkout link")

@router.get("/verify-checkout/{session_id}")
async def verify_checkout(session_id: str):
    """
    Endpoint for frontend to check if a checkout session is already paid.
    """
    is_paid = verify_paymongo_session(session_id)
    return {"paid": is_paid}
