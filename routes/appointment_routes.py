from fastapi import APIRouter, HTTPException, Depends
from models.appointment_model import AppointmentCreate, AppointmentCancel
from logic.appointment_logic import create_appointment, get_appointments, cancel_appointment
from dependencies import verify_user_token

router = APIRouter()

@router.post("/api/appointments")
async def create_appointment_route(
    appointment: AppointmentCreate,
    uid: str = Depends(verify_user_token) # <-- Securely grabs UID
):
    """Create a new appointment for the given user."""
    try:
        data = appointment.model_dump()
        result = create_appointment(uid, data)
        return {"message": "Appointment created successfully", "appointment": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/appointments")
async def get_appointments_route(uid: str = Depends(verify_user_token)):
    """Fetch all appointments for the given user."""
    try:
        appointments = get_appointments(uid)
        return {"appointments": appointments}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/appointments/cancel/{appointment_id}")
async def cancel_appointment_route(
    appointment_id: str,
    uid: str = Depends(verify_user_token)
):
    """Cancel a specific appointment."""
    try:
        result = cancel_appointment(uid, appointment_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return {"message": "Appointment cancelled successfully", "appointment": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))