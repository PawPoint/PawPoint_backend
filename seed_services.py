"""
Seed script to populate the Firestore 'services' collection with all PawPoint services.
Run this once to fix the database:  python seed_services.py
"""

import firebase_admin
from firebase_admin import credentials, firestore

# ── Initialize Firebase ──────────────────────────────────────────────────────
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-credentials.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ── All PawPoint Services ────────────────────────────────────────────────────
# Each service has:
#   - name:          The service name (must match what's used in book_now_page)
#   - category:      Broader category grouping
#   - description:   Detailed description of the service
#   - price:         Base price in PHP
#   - duration:      Estimated duration in minutes
#   - isAvailable:   Whether the service is currently offered
#   - icon:          Icon identifier for frontend reference

SERVICES = [
    {
        "name": "General Check-up",
        "category": "Veterinary Care",
        "description": "A comprehensive physical exam to check your pet's overall health and vital signs. Includes weight monitoring, heart and lung assessment, eye and ear inspection, and general wellness evaluation.",
        "price": 500,
        "duration": 30,
        "isAvailable": True,
        "icon": "medical_services",
    },
    {
        "name": "Diagnostics",
        "category": "Veterinary Care",
        "description": "Advanced lab tests and screenings to detect health issues early. Includes blood work, urinalysis, X-rays, and ultrasound imaging for accurate diagnosis.",
        "price": 1200,
        "duration": 60,
        "isAvailable": True,
        "icon": "biotech",
    },
    {
        "name": "Dental Care",
        "category": "Veterinary Care",
        "description": "Professional dental cleaning and oral health checks to maintain strong teeth and gums. Includes tartar removal, polishing, and oral disease screening.",
        "price": 800,
        "duration": 45,
        "isAvailable": True,
        "icon": "dentistry",
    },
    {
        "name": "Nutrition Consultations",
        "category": "Wellness",
        "description": "Expert advice on your pet's diet, food allergies, and weight management. Personalized meal plans and supplement recommendations tailored to your pet's breed, age, and health needs.",
        "price": 400,
        "duration": 30,
        "isAvailable": True,
        "icon": "restaurant",
    },
    {
        "name": "Parasite Prevention",
        "category": "Preventive Care",
        "description": "Comprehensive protection against fleas, ticks, heartworms, and intestinal parasites. Includes preventive treatments, deworming, and tick/flea control programs.",
        "price": 600,
        "duration": 20,
        "isAvailable": True,
        "icon": "shield",
    },
    {
        "name": "Quick Grooming",
        "category": "Grooming",
        "description": "Fast grooming services including nail clipping, paw tidy-ups, ear cleaning, and basic coat brushing. Perfect for pets that need a quick freshening up.",
        "price": 300,
        "duration": 20,
        "isAvailable": True,
        "icon": "content_cut",
    },
    {
        "name": "Special Treatments",
        "category": "Grooming",
        "description": "Specialized grooming treatments including flea baths, medicated shampoos, coat conditioning, and skin therapy. Ideal for pets with skin conditions or special grooming needs.",
        "price": 700,
        "duration": 45,
        "isAvailable": True,
        "icon": "spa",
    },
    {
        "name": "Full Grooming Packages",
        "category": "Grooming",
        "description": "Complete grooming experience including bath, haircut, nail trim, ear cleaning, teeth brushing, and finishing spray. Your pet leaves looking and feeling their absolute best.",
        "price": 1000,
        "duration": 90,
        "isAvailable": True,
        "icon": "auto_awesome",
    },
]


def seed_services():
    """Delete existing services and re-seed with the full list."""
    services_ref = db.collection("services")

    # 1. Delete all existing documents in the services collection
    existing = services_ref.stream()
    deleted = 0
    for doc in existing:
        doc.reference.delete()
        deleted += 1
    print(f"🗑️  Deleted {deleted} old service document(s).")

    # 2. Add all services
    for svc in SERVICES:
        doc_ref = services_ref.document()  # auto-generate ID
        doc_ref.set(svc)
        print(f"✅ Added: {svc['name']}  (₱{svc['price']}, {svc['duration']}min)")

    print(f"\n🎉 Done! {len(SERVICES)} services seeded successfully.")


if __name__ == "__main__":
    seed_services()
