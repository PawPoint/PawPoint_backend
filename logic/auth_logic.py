import requests
from firebase_admin import firestore, auth
from fastapi import HTTPException

# Firebase Auth REST API base URL
FIREBASE_AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts"


class AuthService:
    def __init__(self, api_key: str):
        self.db = firestore.client()
        self.api_key = api_key

    def login(self, email: str, password: str) -> dict:
        """
        Authenticate user via Firebase Auth REST API.
        Returns uid, email, and idToken on success.
        """
        try:
            # Use Firebase Auth REST API to sign in
            url = f"{FIREBASE_AUTH_URL}:signInWithPassword?key={self.api_key}"
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True,
            }
            response = requests.post(url, json=payload)
            data = response.json()

            if response.status_code != 200:
                error_message = data.get("error", {}).get("message", "Login failed.")
                # Map Firebase error codes to user-friendly messages
                error_map = {
                    "EMAIL_NOT_FOUND": "Incorrect email or password.",
                    "INVALID_PASSWORD": "Incorrect email or password.",
                    "INVALID_LOGIN_CREDENTIALS": "Incorrect email or password.",
                    "USER_DISABLED": "This account has been disabled.",
                    "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts. Try again later.",
                }
                friendly = error_map.get(error_message, "Login failed. Please try again.")
                raise HTTPException(status_code=401, detail=friendly)

            return {
                "status": "success",
                "message": "Login successful!",
                "uid": data["localId"],
                "email": data["email"],
                "token": data["idToken"],
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def signup(self, email: str, password: str, confirm_password: str,
               name: str, phone: str, address: str) -> dict:
        """
        Create a new user via Firebase Admin SDK, then save profile to Firestore.
        """
        # Validate passwords match
        if password != confirm_password:
            raise HTTPException(status_code=400, detail="Passwords do not match.")

        # Validate password length
        if len(password) < 8:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 8 characters long.",
            )

        # Validate phone (expect 10 digits after +63 prefix)
        raw_phone = phone.replace("+63", "")
        if len(raw_phone) != 10 or not raw_phone.isdigit():
            raise HTTPException(
                status_code=400,
                detail="Phone number must be exactly 10 digits.",
            )

        try:
            # 1. Create user in Firebase Auth via Admin SDK
            user_record = auth.create_user(
                email=email,
                password=password,
                display_name=name,
            )

            # 2. Save extra profile data to Firestore
            self.db.collection("users").document(user_record.uid).set({
                "uid": user_record.uid,
                "email": email,
                "name": name,
                "phone": phone,
                "address": address,
                "role": "customer",
                "createdAt": firestore.SERVER_TIMESTAMP,
            })

            # 3. Generate a custom token so frontend can sign in
            custom_token = auth.create_custom_token(user_record.uid)

            return {
                "status": "success",
                "message": f"Account created for {name}!",
                "uid": user_record.uid,
                "email": email,
                "token": custom_token.decode("utf-8") if isinstance(custom_token, bytes) else str(custom_token),
            }

        except auth.EmailAlreadyExistsError:
            raise HTTPException(
                status_code=400,
                detail="This email is already registered. Please log in instead.",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
