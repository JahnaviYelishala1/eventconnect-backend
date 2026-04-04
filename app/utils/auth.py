from fastapi import HTTPException, Depends, Request
from firebase_admin import auth  # ✅ CORRECT IMPORT
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import time

from app.database import get_db
from app.models.user import User


# 🔐 Verify Firebase Token
def verify_firebase_token(token: str):
    try:
        decoded_token = auth.verify_id_token(
            token,
            clock_skew_seconds=60
        )
        return decoded_token
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )


# 👤 Ensure User Exists in Database
def ensure_db_user(decoded: dict, db: Session) -> User:
    firebase_uid = decoded["uid"]
    email = decoded.get("email")

    # 1️⃣ Find by Firebase UID
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if user:
        if not user.email and email:
            user.email = email
            db.commit()
        return user

    # 2️⃣ Link by email (Google sign-in case)
    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.firebase_uid = firebase_uid
            db.commit()
            return user

    # 3️⃣ Create new user
    user = User(
        firebase_uid=firebase_uid,
        email=email,
        role="UNASSIGNED"
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        return db.query(User).filter(User.email == email).first()


# 🔑 Dependency for Protected Routes
def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")

    token = auth_header.split(" ")[1]

    try:
        decoded_token = auth.verify_id_token(
            token,
            clock_skew_seconds=60
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Firebase token")

    # Ensure a corresponding DB user exists (creates/links by firebase_uid/email if needed).
    db_user = ensure_db_user(decoded_token, db)
    return db_user