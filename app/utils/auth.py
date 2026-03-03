from fastapi import Header, HTTPException, Depends
from firebase_admin import auth  # ✅ CORRECT IMPORT
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.user import User


# 🔐 Verify Firebase Token
def verify_firebase_token(token: str):
    try:
        decoded_token = auth.verify_id_token(token)
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
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db)
):
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header"
        )

    token = authorization.replace("Bearer ", "").strip()

    decoded = verify_firebase_token(token)
    db_user = ensure_db_user(decoded, db)

    return {
        "id": db_user.id,
        "uid": db_user.firebase_uid,
        "email": db_user.email,
        "role": db_user.role,
        "name": db_user.name,
        "phone": db_user.phone
    }