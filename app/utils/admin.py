from fastapi import HTTPException

ADMIN_EMAILS = [
    "231210128@nitdelhi.ac.in"  # 👈 replace with YOUR Firebase email
]

def admin_only(user: dict):
    if user.get("email") not in ADMIN_EMAILS:
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
