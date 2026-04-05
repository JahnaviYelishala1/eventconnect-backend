from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.food_prediction import FoodPredictionRequest
from app.services.food_predictor import predict_food_quantities

router = APIRouter(prefix="/api/predict-food", tags=["Food Prediction"])


@router.post("/")
def predict_food(data: FoodPredictionRequest):
    try:
        predictions = predict_food_quantities(
            attendees=data.attendees,
            items=data.items,
            meal_type=data.meal_type,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"predictions": predictions}