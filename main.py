from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import os

load_dotenv()

# 1. Initialize Firebase Admin
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-credentials.json")
    firebase_admin.initialize_app(cred)

# Import routes
from routes.add_pet_routes import router as pet_router
from routes.appointment_routes import router as appointment_router
from routes.user_routes import router as user_router
from routes.payment_routes import router as payment_router

# Import the expiry job (imported AFTER firebase_admin is initialised)
from logic.expiry_logic import auto_expire_pending_appointments

# ── Scheduler lifespan ────────────────────────────────────────────────────────
_scheduler = BackgroundScheduler(timezone="UTC")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run immediately on startup, then every 15 minutes
    _scheduler.add_job(
        auto_expire_pending_appointments,
        trigger="interval",
        minutes=15,
        id="auto_expire",
        next_run_time=__import__("datetime").datetime.utcnow(),  # run now too
    )
    _scheduler.start()
    print("[scheduler] Auto-expiry job started (every 15 min).")
    yield
    _scheduler.shutdown(wait=False)
    print("[scheduler] Scheduler stopped.")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="PawPoint API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(pet_router, tags=["Pets"])
app.include_router(appointment_router, tags=["Appointments"])
app.include_router(user_router, tags=["Users"])
app.include_router(payment_router, prefix="/payments", tags=["Payments"])

@app.get("/")
def read_root():
    return {"status": "online", "message": "PawPoint Backend is connected to Firebase!"}