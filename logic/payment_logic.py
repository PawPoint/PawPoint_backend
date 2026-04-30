import requests
import json
import os
import base64

def create_paymongo_checkout(amount: float, service_name: str, description: str = "PawPoint Clinic Appointment"):
    """
    Create a PayMongo Checkout Session and return the redirect URL.
    Amount should be in PHP (e.g., 500.00). PayMongo expects it in centavos (x100).
    """
    # ── YOUR SECRET KEY (now from .env) ──
    PAYMONGO_SECRET_KEY = os.getenv("PAYMONGO_SECRET_KEY")
    if not PAYMONGO_SECRET_KEY:
        print("[create_paymongo_checkout] ERROR: PAYMONGO_SECRET_KEY not found in .env")
        return None
    
    url = "https://api.paymongo.com/v1/checkout_sessions"

    # PayMongo amount is in centavos (e.g., 500.00 PHP = 50000 centavos)
    amount_in_centavos = int(amount * 100)

    payload = {
        "data": {
            "attributes": {
                "billing": {
                    # Removing default values as requested by user
                    "address": {
                        "line1": "",
                        "city": "",
                        "state": "",
                        "postal_code": "",
                        "country": "PH"
                    },
                    "name": "",
                    "email": "",
                    "phone": ""
                },
                "send_email_receipt": True,
                "show_description": True,
                "show_line_items": True,
                "description": description,
                "line_items": [
                    {
                        "currency": "PHP",
                        "amount": amount_in_centavos,
                        "description": service_name,
                        "name": service_name,
                        "quantity": 1
                    }
                ],
                "payment_method_types": ["card", "gcash", "paymaya"],
                "success_url": "https://example.com/success", 
                "cancel_url": "https://example.com/cancel"
            }
        }
    }

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    
    # Authorization: Basic <base64(secret_key:)>
    auth_bytes = f"{PAYMONGO_SECRET_KEY}:".encode("ascii")
    base64_auth = base64.b64encode(auth_bytes).decode("ascii")
    headers["authorization"] = f"Basic {base64_auth}"

    response = requests.post(url, json=payload, headers=headers)
    
    print(f"[create_paymongo_checkout] URL: {url}")
    print(f"[create_paymongo_checkout] Status: {response.status_code}")
    
    if response.status_code == 200:
        res_data = response.json()
        return {
            "checkout_url": res_data["data"]["attributes"]["checkout_url"],
            "session_id": res_data["data"]["id"]
        }
    else:
        print(f"PayMongo Error: {response.text}")
        return None

def verify_paymongo_session(session_id: str):
    """
    Check the status of a PayMongo Checkout Session.
    Returns True if payment is successful/paid, False otherwise.
    """
    PAYMONGO_SECRET_KEY = os.getenv("PAYMONGO_SECRET_KEY")
    if not PAYMONGO_SECRET_KEY:
        return False

    url = f"https://api.paymongo.com/v1/checkout_sessions/{session_id}"
    
    auth_bytes = f"{PAYMONGO_SECRET_KEY}:".encode("ascii")
    base64_auth = base64.b64encode(auth_bytes).decode("ascii")
    headers = {
        "accept": "application/json",
        "authorization": f"Basic {base64_auth}"
    }

    try:
        response = requests.get(url, headers=headers)
        print(f"[verify_paymongo_session] Response Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            # Log the full data for debugging
            print(f"[verify_paymongo_session] Full Response: {json.dumps(data, indent=2)}")
            
            attributes = data.get("data", {}).get("attributes", {})
            status = attributes.get("status", "")
            
            # Sometimes we might need to check if there are successful payments in the list
            payments = attributes.get("payments", [])
            has_successful_payment = any(p.get("attributes", {}).get("status") == "paid" for p in payments)
            
            print(f"[verify_paymongo_session] Session status: {status}, Has payments: {len(payments)}, Success payment: {has_successful_payment}")
            
            return status == "paid" or has_successful_payment
        else:
            print(f"[verify_paymongo_session] Error: {response.text}")
            return False
    except Exception as e:
        print(f"[verify_paymongo_session] Exception: {e}")
        return False
