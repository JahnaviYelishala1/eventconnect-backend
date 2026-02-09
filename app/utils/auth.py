from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.firebase import verify_firebase_token
from app.database import get_db
from app.models.user import User


def ensure_db_user(decoded: dict, db: Session) -> User:
    firebase_uid = decoded["uid"]
    email = decoded.get("email")

    # 1️⃣ Find by firebase UID
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if user:
        return user

    # 2️⃣ Link by email (important for Google sign-in / admin)
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
        "uid": db_user.firebase_uid,
        "email": db_user.email,
        "role": db_user.role,
        "name": db_user.name,
        "phone": db_user.phone
    }
