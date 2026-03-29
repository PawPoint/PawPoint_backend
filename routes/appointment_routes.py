from fastapi import APIRouter, HTTPException
from models.appointment_model import AppointmentCreate, AppointmentCancel
from logic.appointment_logic import create_appointment, get_appointments, cancel_appointment

router = APIRouter()


@router.post("/appointments/{user_id}")
async def create_appointment_route(user_id: str, appointment: AppointmentCreate):
    """Create a new appointment for the given user."""
    try:
        data = appointment.model_dump()
        result = create_appointment(user_id, data)
        return {"message": "Appointment created successfully", "appointment": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/appointments/{user_id}")
async def get_appointments_route(user_id: str):
    """Fetch all appointments for the given user."""
    try:
        appointments = get_appointments(user_id)
        return {"appointments": appointments}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/appointments/{user_id}/cancel/{appointment_id}")
async def cancel_appointment_route(user_id: str, appointment_id: str):
    """Cancel a specific appointment."""
    try:
        result = cancel_appointment(user_id, appointment_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return {"message": "Appointment cancelled successfully", "appointment": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
