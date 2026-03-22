import requests
from fastapi import HTTPException
from firebase_admin import firestore

class AuthService:
    def __init__(self, api_key: str):
        self.db = firestore.client()
        self.api_key = api_key
        # 1. Define your Hard-Coded Admin here
        self.ADMIN_EMAIL = "admin@pawpoint.com"
        self.ADMIN_PASSWORD = "AdminSecurePassword123"

    def login(self, email: str, password: str) -> dict:
        """
        Authenticate user. Checks for hard-coded admin first, 
        then falls back to Firebase.
        """
        # 2. INTERCEPT: Check for the hard-coded admin
        if email == self.ADMIN_EMAIL and password == self.ADMIN_PASSWORD:
            return {
                "status": "success",
                "message": "Welcome, Admin!",
                "uid": "admin-001",
                "email": self.ADMIN_EMAIL,
                "token": "admin-special-session-token",
                "role": "admin", # This tells Flutter to go to Admin Dashboard
            }

        # 3. NORMAL LOGIC: If not the hard-coded admin, check Firebase
        try:
            url = f"{FIREBASE_AUTH_URL}:signInWithPassword?key={self.api_key}"
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True,
            }
            response = requests.post(url, json=payload)
            data = response.json()

            if response.status_code != 200:
                # ... (keep your existing error mapping logic here) ...
                raise HTTPException(status_code=401, detail="Incorrect email or password.")

            # Fetch role from Firestore for regular users
            user_doc = self.db.collection("users").document(data["localId"]).get()
            role = "customer"
            if user_doc.exists:
                role = user_doc.to_dict().get("role", "customer")

            return {
                "status": "success",
                "message": "Login successful!",
                "uid": data["localId"],
                "email": data["email"],
                "token": data["idToken"],
                "role": role,
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))