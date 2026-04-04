from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from fastapi import File, UploadFile
import asyncio
import cloudinary.uploader

from app.database import get_db
from app.models.caterer import Caterer
from app.models.caterer_menu import CatererMenu
from app.schemas.menu import MenuCreate, MenuResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/menus", tags=["Menus"])


def _get_caterer_for_user(db: Session, user_id: int) -> Caterer:
    caterer = db.query(Caterer).filter(
        Caterer.user_id == user_id
    ).first()

    if not caterer:
        raise HTTPException(404, "Create profile first")

    return caterer

@router.post("/", response_model=MenuResponse)
def create_menu(
    data: MenuCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = user

    if not db_user or db_user.role != "caterer":
        raise HTTPException(403, "Only caterers allowed")

    caterer = _get_caterer_for_user(db, db_user.id)
    menu = CatererMenu(
        caterer_id=caterer.id,
        item_name=data.item_name,
        description=data.description,
        price=data.price,
        category=data.category,
        food_type=data.food_type,
        image_url=data.image_url
    )

    db.add(menu)
    db.commit()
    db.refresh(menu)

    return menu

@router.get("/me", response_model=List[MenuResponse])
def get_my_menu(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = user

    if not db_user or db_user.role != "caterer":
        return []

    caterer = db.query(Caterer).filter(Caterer.user_id == db_user.id).first()
    if not caterer:
        return []

    return db.query(CatererMenu).filter(
        CatererMenu.caterer_id == caterer.id
    ).all()


@router.get("/{caterer_id}", response_model=List[MenuResponse])
def get_menu(caterer_id: int, db: Session = Depends(get_db)):
    return db.query(CatererMenu).filter(
        CatererMenu.caterer_id == caterer_id
    ).all()

@router.put("/{menu_id}", response_model=MenuResponse)
def update_menu(
    menu_id: int,
    data: MenuCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = user

    if not db_user or db_user.role != "caterer":
        raise HTTPException(403, "Only caterers allowed")

    caterer = _get_caterer_for_user(db, db_user.id)

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
    menu.image_url = data.image_url

    db.commit()
    db.refresh(menu)

    return menu

@router.delete("/{menu_id}")
def delete_menu(
    menu_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = user

    if not db_user or db_user.role != "caterer":
        raise HTTPException(403, "Only caterers allowed")

    caterer = _get_caterer_for_user(db, db_user.id)

    menu = db.query(CatererMenu).filter(
        CatererMenu.id == menu_id,
        CatererMenu.caterer_id == caterer.id
    ).first()

    if not menu:
        raise HTTPException(404, "Menu not found")

    db.delete(menu)
    db.commit()
    return {"message": "Menu deleted"}

@router.post("/upload-image")
async def upload_menu_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = user

    if not db_user or db_user.role != "caterer":
        raise HTTPException(403, "Only caterers allowed")

    try:
        await file.seek(0)
        loop = asyncio.get_running_loop()

        result = await loop.run_in_executor(
            None,
            lambda: cloudinary.uploader.upload(
                file.file,
                folder="menu_images",
                resource_type="image"
            )
        )

        return {
            "image_url": result.get("secure_url"),
            "message": "Menu image uploaded successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await file.close()
