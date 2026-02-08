from fastapi import APIRouter, Depends
from app.utils.auth import get_current_user

router = APIRouter()

@router.get("/protected")
def protected_route(user = Depends(get_current_user)):
    return {
        "uid": user["uid"],
        "email": user["email"],
        "role": user["role"],
        "name": user["name"],      
        "phone": user["phone"]     
    }
