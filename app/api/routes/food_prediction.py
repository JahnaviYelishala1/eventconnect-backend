from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.food_prediction import FoodPredictionRequest
from app.services.food_predictor import predict_food_quantities

router = APIRouter(prefix="/api/predict-food", tags=["Food Prediction"])


@router.post("/")
def predict_food(data: FoodPredictionRequest):

    result = predict_food_quantities(
        attendees=data.attendees,
        items=data.items,
        event_type=data.event_type,
        meal_type=data.meal_type
    )

    return {"predictions": result}