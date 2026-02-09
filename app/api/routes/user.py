from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User

router = APIRouter()

VALID_ROLES = ["event_organizer", "caterer", "ngo"]

@router.post("/users/select-role")
def select_role(
    role: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")

    db_user = db.query(User).filter(
        User.firebase_uid == current_user["uid"]
    ).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db_user.role = role
    db.commit()

    return {"message": "Role updated", "role": role}
