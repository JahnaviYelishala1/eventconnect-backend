from fastapi import Depends, HTTPException
from app.utils.auth import get_current_user


def require_role(required_role: str):
    def checker(user = Depends(get_current_user)):
        if user["role"] != required_role:
            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )
        return user
    return checker


def require_assigned_role(user = Depends(get_current_user)):
    if user["role"] == "UNASSIGNED":
        raise HTTPException(
            status_code=403,
            detail="Please select a role first"
        )
    return user
