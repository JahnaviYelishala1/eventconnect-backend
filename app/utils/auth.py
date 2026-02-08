from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.firebase import verify_firebase_token
from app.database import get_db
from app.crud.user import get_user_by_firebase_uid, create_user

def get_current_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")

    token = authorization.split(" ")[1]
    decoded = verify_firebase_token(token)

    uid = decoded["uid"]
    email = decoded.get("email")

    user = get_user_by_firebase_uid(db, uid)
    if not user:
        user = create_user(db, uid, email)

    # ✅ RETURN EVERYTHING AS DICT
    return {
        "uid": user.firebase_uid,
        "email": user.email,
        "role": user.role,
        "name": user.name,     # 👈 ADD
        "phone": user.phone    # 👈 ADD
    }
