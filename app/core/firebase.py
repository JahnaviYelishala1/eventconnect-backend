import firebase_admin
from firebase_admin import credentials, auth
from fastapi import Depends, HTTPException, Header
from requests import Session

from app.database import get_db
from app.models.user import User

if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_service_account.json")
    firebase_admin.initialize_app(cred)

def verify_firebase_token(id_token: str):
    try:
        return auth.verify_id_token(id_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Firebase token")

def get_current_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
) -> User:
    """
    Extracts Firebase token from Authorization header,
    verifies it, and returns the corresponding User from DB.
    """

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.replace("Bearer ", "")
    decoded = verify_firebase_token(token)

    firebase_uid = decoded.get("uid")
    email = decoded.get("email")

    if not firebase_uid:
        raise HTTPException(status_code=401, detail="Invalid Firebase token")

    # 🔹 Find user in DB
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()

    if not user:
        # 🔹 Optional: auto-create user if not exists
        user = User(
            firebase_uid=firebase_uid,
            email=email
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user