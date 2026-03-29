from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore

# 1. Initialize Firebase Admin
# We check if it's already initialized to prevent errors during server reloads
if not firebase_admin._apps:
    # Point this to the exact name of your downloaded JSON file
    cred = credentials.Certificate("firebase-credentials.json")
    firebase_admin.initialize_app(cred)

# Import routes
from routes.add_pet_routes import router as pet_router
from routes.auth_routes import router as auth_router
from routes.appointment_routes import router as appointment_router
from routes.user_routes import router as user_router

app = FastAPI(title="PawPoint API")

# Allow the Flutter frontend (web & emulator) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(pet_router, tags=["Pets"])
app.include_router(auth_router, tags=["Auth"])
app.include_router(appointment_router, tags=["Appointments"])
app.include_router(user_router, tags=["Users"])

@app.get("/")
def read_root():
    return {"status": "online", "message": "PawPoint Backend is connected to Firebase!"}