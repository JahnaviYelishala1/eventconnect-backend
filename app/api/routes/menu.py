from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.caterer import Caterer
from app.models.caterer_menu import CatererMenu
from app.schemas.menu import MenuCreate, MenuResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/menus", tags=["Menus"])

@router.post("/", response_model=MenuResponse)
def create_menu(
    data: MenuCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "caterer":
        raise HTTPException(403, "Only caterers allowed")

    caterer = db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first()

    if not caterer:
        raise HTTPException(404, "Create profile first")

    menu = CatererMenu(
        caterer_id=caterer.id,
        item_name=data.item_name,
        description=data.description,
        price=data.price,
        category=data.category
    )

    db.add(menu)
    db.commit()
    db.refresh(menu)

    return menu

@router.get("/{caterer_id}", response_model=List[MenuResponse])
def get_menu(caterer_id: int, db: Session = Depends(get_db)):
    return db.query(CatererMenu).filter(
        CatererMenu.caterer_id == caterer_id
    ).all()

@router.get("/me", response_model=List[MenuResponse])
def get_my_menu(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "caterer":
        raise HTTPException(403, "Only caterers allowed")

    caterer = db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first()

    return db.query(CatererMenu).filter(
        CatererMenu.caterer_id == caterer.id
    ).all()

@router.put("/{menu_id}", response_model=MenuResponse)
def update_menu(
    menu_id: int,
    data: MenuCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "caterer":
        raise HTTPException(403, "Only caterers allowed")

    caterer = db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first()

    menu = db.query(CatererMenu).filter(
        CatererMenu.id == menu_id,
        CatererMenu.caterer_id == caterer.id
    ).first()

    if not menu:
        raise HTTPException(404, "Menu not found")

    menu.item_name = data.item_name
    menu.description = data.description
    menu.price = data.price
    menu.category = data.category

    db.commit()
    db.refresh(menu)

    return menu

@router.delete("/{menu_id}")
def delete_menu(
    menu_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "caterer":
        raise HTTPException(403, "Only caterers allowed")

    caterer = db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first()

    menu = db.query(CatererMenu).filter(
        CatererMenu.id == menu_id,
        CatererMenu.caterer_id == caterer.id
    ).first()

    if not menu:
        raise HTTPException(404, "Menu not found")

    db.delete(menu)
    db.commit()

    return {"message": "Menu deleted"}

