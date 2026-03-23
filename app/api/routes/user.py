from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.utils.auth import get_current_user
from app.utils.notifications import send_push_notification
from app.models.user import User

router = APIRouter()

VALID_ROLES = ["event_organizer", "caterer", "ngo"]


class FCMTokenRequest(BaseModel):
    token: str


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


@router.post("/users/save-fcm-token")
def save_fcm_token(
    request: FCMTokenRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == current_user["uid"]
    ).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db_user.fcm_token = request.token
    db.commit()

    return {"message": "FCM token saved"}


@router.post("/save-fcm-token")
def save_fcm_token_simple(
    request: FCMTokenRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db_user.fcm_token = request.token
    db.commit()

    return {"message": "FCM token saved"}


@router.get("/test-push/{user_id}")
def test_push(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.fcm_token:
        raise HTTPException(status_code=400, detail="User does not have an FCM token")

    print("TOKEN:", user.fcm_token)

    message_id = send_push_notification(
        user.fcm_token,
        "Test Notification",
        "FCM is working"
    )

    if not message_id:
        raise HTTPException(status_code=500, detail="Failed to send push notification")

    return {"message": "sent", "message_id": message_id}
