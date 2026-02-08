from fastapi import APIRouter, Depends
from app.schemas.food_prediction import FoodPredictionRequest, FoodPredictionResponse
from app.ml.predictor import predict_food_quantity
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/events", tags=["Food Prediction"])


@router.post(
    "/predict-food",
    response_model=FoodPredictionResponse
)
def predict_food(
    data: FoodPredictionRequest,
    user=Depends(get_current_user)
):
    """
    Predict food quantity required for an event
    """

    # Convert request into model features
    features = [
        data.event_type,
        data.attendees,
        data.duration_hours,
        data.meal_style,
        data.location_type,
        data.season
    ]

    prediction = predict_food_quantity(features)

    return FoodPredictionResponse(
        estimated_food_quantity=round(prediction, 2),
        unit="kg"
    )
