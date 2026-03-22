from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore

# 1. Initialize Firebase Admin
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("firebase-credentials.json")
        firebase_admin.initialize_app(cred)
        print("Firebase initialized successfully.")
    except Exception as e:
        print(f"Firebase initialization failed: {e}")

# Create the FastAPI app instance FIRST
app = FastAPI(title="PawPoint API")

# 2. CORS Middleware (Crucial for Flutter Web/Chrome)
# This MUST come before including any routers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Import and Register Routes
# Doing imports here ensures 'app' is already defined if your routes need it
from routes.add_pet_routes import router as pet_router
from routes.auth_routes import router as auth_router

app.include_router(pet_router, tags=["Pets"])
app.include_router(auth_router, tags=["Auth"])

# 4. Root Route (The "Welcome" page)
@app.get("/")
async def read_root():
    return {
        "status": "online", 
        "message": "PawPoint Backend is connected to Firebase!",
        "docs": "/docs"
    }

# 5. Helper for local running
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)