from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.auth import get_current_user

router = APIRouter()

VALID_ROLES = ["event_organizer", "caterer", "ngo"]

@router.post("/users/select-role")
def select_role(
    role: str,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")

    user.role = role
    db.commit()

    return {"message": "Role updated", "role": user.role}
