"""Real-time volcanic hazard prediction pipeline for sensor streaming input."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


LABEL_DECODER = {0: "Normal", 1: "Moderate", 2: "Dangerous", 3: "Critical"}
ALERT_COLOR = {
    "Normal": "green",
    "Moderate": "yellow",
    "Dangerous": "red",
    "Critical": "darkred",
}
RISK_MESSAGE = {
    "Normal": "Conditions are within safe limits. Continue monitoring.",
    "Moderate": "Elevated hazard detected. Exercise caution and prepare for escalation.",
    "Dangerous": "High hazard level detected. Evacuate immediately and notify authorities.",
    "Critical": "Critical hazard level detected. Immediate evacuation is required.",
}


def load_model(model_path: str):
    """Load a saved XGBoost or sklearn model from disk."""
    return joblib.load(model_path)


def load_preprocessor(preprocessor_path: str):
    """Load a saved preprocessing pipeline if available."""
    return joblib.load(preprocessor_path)


def _validate_input(input_data: dict[str, Any], required_fields: list[str]) -> None:
    missing = [field for field in required_fields if field not in input_data]
    if missing:
        raise KeyError(f"Missing required real-time fields: {missing}")


def build_input_dataframe(input_data: dict[str, Any], feature_columns: list[str]) -> pd.DataFrame:
    """Convert a real-time input dictionary to a DataFrame for prediction."""
    _validate_input(input_data, feature_columns)
    df = pd.DataFrame([input_data], columns=feature_columns)
    return df


def predict_hazard(
    model,
    input_df: pd.DataFrame,
    preprocessor=None,
    label_decoder: dict[int, str] = LABEL_DECODER,
) -> pd.DataFrame:
    """Run a real-time hazard prediction and return enriched results."""
    processed_df = input_df.copy()
    features = input_df

    if preprocessor is not None:
        features = pd.DataFrame(
            preprocessor.transform(input_df),
            columns=[f"feature_{i}" for i in range(input_df.shape[1])],
        )

    probabilities = model.predict_proba(features)
    prediction_codes = model.predict(features)

    processed_df["predicted_code"] = prediction_codes
    processed_df["hazard_level"] = [label_decoder.get(code, "Unknown") for code in prediction_codes]
    processed_df["hazard_probability"] = [round(max(proba), 4) for proba in probabilities]
    processed_df["hazard_probabilities"] = [proba.tolist() for proba in probabilities]
    processed_df["alert_color"] = processed_df["hazard_level"].map(ALERT_COLOR)
    processed_df["risk_message"] = processed_df["hazard_level"].map(RISK_MESSAGE)
    processed_df["prediction_timestamp"] = datetime.utcnow().isoformat()

    return processed_df


def build_alert_summary(prediction_row: pd.Series) -> dict[str, Any]:
    """Build a concise alert summary from a prediction row."""
    return {
        "hazard_level": prediction_row["hazard_level"],
        "hazard_probability": prediction_row["hazard_probability"],
        "alert_color": prediction_row["alert_color"],
        "risk_message": prediction_row["risk_message"],
        "timestamp": prediction_row["prediction_timestamp"],
    }


def save_prediction_history(
    prediction_df: pd.DataFrame,
    history_path: str,
    append: bool = True,
) -> None:
    """Save prediction history to a CSV file for audit and analysis."""
    path = Path(history_path)
    mode = "a" if append and path.exists() else "w"
    header = not (append and path.exists())
    prediction_df.to_csv(path, mode=mode, header=header, index=False)


def run_real_time_prediction(
    input_data: dict[str, Any],
    model_path: str,
    feature_columns: list[str],
    history_path: str,
    preprocessor_path: str | None = None,
) -> dict[str, Any]:
    """Complete real-time prediction pipeline from sensor input to alert history."""
    model = load_model(model_path)
    preprocessor = load_preprocessor(preprocessor_path) if preprocessor_path else None

    input_df = build_input_dataframe(input_data, feature_columns)
    prediction_df = predict_hazard(model, input_df, preprocessor=preprocessor)
    save_prediction_history(prediction_df, history_path)

    return build_alert_summary(prediction_df.iloc[0])


if __name__ == "__main__":
    print("Use realtime_prediction functions in a streaming or REST pipeline.")
