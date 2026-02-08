import joblib
import os
import pandas as pd

MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "eventconnect_food_prediction_model_optuna.pkl"
)

model = joblib.load(MODEL_PATH)

FEATURE_COLUMNS = [
    "event_type",
    "attendees",
    "duration_hours",
    "meal_style",
    "location_type",
    "season",
]


def predict_food_quantity(features: list) -> float:
    """
    features order:
    [event_type, attendees, duration_hours, meal_style, location_type, season]
    """

    # Convert list → DataFrame (THIS FIXES THE ERROR)
    input_df = pd.DataFrame([features], columns=FEATURE_COLUMNS)

    prediction = model.predict(input_df)
    return float(prediction[0])
