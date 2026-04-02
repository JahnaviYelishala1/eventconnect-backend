import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest
from app.services.email_service import send_password_reset_email
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])


def _hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with per-password random salt."""
    iterations = 100_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def _token_is_expired(expiry: datetime | None) -> bool:
    if not expiry:
        return True
    return expiry < datetime.utcnow()


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    # Always return success to avoid leaking whether an email exists.
    if not user:
        return {"message": "Reset link sent"}

    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expiry = datetime.utcnow() + timedelta(minutes=15)
    db.commit()

    reset_link = f"{settings.password_reset_base_url}?token={token}"
    sent = send_password_reset_email(user.email, reset_link)
    if not sent:
        raise HTTPException(status_code=500, detail="Unable to send reset email")

    return {"message": "Reset link sent"}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == payload.token).first()

    if not user or _token_is_expired(user.reset_token_expiry):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user.password_hash = _hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    db.commit()

    return {"message": "Password updated successfully"}
