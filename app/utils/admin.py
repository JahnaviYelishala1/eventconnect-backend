from fastapi import HTTPException

from app.models.user import User


def admin_only(user: User):
    if (user.role or "").upper() != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
