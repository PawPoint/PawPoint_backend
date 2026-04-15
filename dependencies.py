from fastapi import HTTPException, Header
from firebase_admin import auth

def verify_user_token(authorization: str = Header(None)):
    """
    Checks the Authorization header for a valid Firebase ID token.
    Returns the decoded user UID if valid.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token")

    # Extract the actual token string without the "Bearer " part
    token = authorization.split("Bearer ")[1]

    try:
        # Firebase Admin SDK verifies the token signature and expiration
        decoded_token = auth.verify_id_token(token)
        
        # Return the actual user ID!
        return decoded_token["uid"]
        
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token has expired. Please log in again.")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid authentication token")