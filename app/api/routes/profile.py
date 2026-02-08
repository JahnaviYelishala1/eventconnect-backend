from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.auth import get_current_user

router = APIRouter()

class ProfileUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None

@router.put("/profile")
def update_profile(
    data: ProfileUpdate,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if data.name is not None:
        user.name = data.name
    if data.phone is not None:
        user.phone = data.phone

    db.commit()

    return {
        "message": "Profile updated",
        "name": user.name,
        "phone": user.phone
    }
