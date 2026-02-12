from fastapi import HTTPException

ADMIN_EMAILS = ["231210128@nitdelhi.ac.in"]

def admin_only(user: dict):
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
