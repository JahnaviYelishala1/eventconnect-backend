from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/protected")
def protected_route(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return {
        "id": current_user.id,
        "role": current_user.role,
        "email": current_user.email,
    }
