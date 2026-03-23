from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/protected")
def protected_route(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(
        User.firebase_uid == current_user["uid"]
    ).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": db_user.id,
        "role": db_user.role,
        "email": db_user.email,
    }
