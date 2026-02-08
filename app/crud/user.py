from sqlalchemy.orm import Session
from app.models.user import User

def get_user_by_firebase_uid(db: Session, uid: str):
    return db.query(User).filter(User.firebase_uid == uid).first()

def create_user(db: Session, uid: str, email: str):
    user = User(
        firebase_uid=uid,
        email=email,
        role="UNASSIGNED"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
