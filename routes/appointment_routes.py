from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from models.appointment_model import AppointmentCreate, AppointmentCancel
from logic.appointment_logic import (
    create_appointment,
    get_appointments,
    cancel_appointment,
    reschedule_appointment,
)
from dependencies import verify_user_token
import os

router = APIRouter()


@router.get("/api/test-email")
async def test_email_route():
    """Debug: test SMTP connection and email sending. Remove after fixing."""
    import smtplib
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    # Report loaded env vars (mask password)
    env_status = {
        "SMTP_HOST": smtp_host or "NOT SET",
        "SMTP_PORT": smtp_port,
        "SMTP_USER": smtp_user or "NOT SET",
        "SMTP_PASS": ("SET (" + str(len(smtp_pass)) + " chars)") if smtp_pass else "NOT SET",
    }

    if not all([smtp_host, smtp_user, smtp_pass]):
        return {"status": "failed", "reason": "Missing SMTP env vars", "env": env_status}

    try:
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        msg = MIMEMultipart()
        msg['From'] = f"PawPoint <{smtp_user}>"
        msg['To'] = smtp_user
        msg['Subject'] = "PawPoint SMTP Test"
        msg.attach(MIMEText("<p>SMTP test email from PawPoint backend. If you see this, email is working!</p>", 'html'))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        return {"status": "success", "message": f"Test email sent to {smtp_user}", "env": env_status}
    except Exception as e:
        return {"status": "failed", "error": str(e), "env": env_status}


class RescheduleRequest(BaseModel):
    new_datetime: str   # ISO 8601 string e.g. "2026-05-10T14:00:00"

@router.post("/api/appointments")
async def create_appointment_route(
    appointment: AppointmentCreate,
    uid: str = Depends(verify_user_token)
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


@router.put("/api/appointments/reschedule/{appointment_id}")
async def reschedule_appointment_route(
    appointment_id: str,
    body: RescheduleRequest,
    uid: str = Depends(verify_user_token)
):
    """Reschedule a pending appointment to a new date/time."""
    try:
        result = reschedule_appointment(uid, appointment_id, body.new_datetime)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return {"message": "Appointment rescheduled successfully", "appointment": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/appointments/accept-reschedule/{appointment_id}")
async def accept_reschedule_route(
    appointment_id: str,
    uid: str = Depends(verify_user_token)
):
    """User accepts the clinc's proposed reschedule — status becomes approved."""
    try:
        from logic.appointment_logic import accept_reschedule
        result = accept_reschedule(uid, appointment_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return {"message": "Reschedule accepted", "appointment": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/appointments/decline-reschedule/{appointment_id}")
async def decline_reschedule_route(
    appointment_id: str,
    uid: str = Depends(verify_user_token)
):
    """User declines the clinic's proposed reschedule — cancels and refunds."""
    try:
        from logic.appointment_logic import decline_reschedule
        result = decline_reschedule(uid, appointment_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return {"message": "Reschedule declined and appointment cancelled", "appointment": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))