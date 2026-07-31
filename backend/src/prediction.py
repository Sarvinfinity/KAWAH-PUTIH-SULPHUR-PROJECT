"""Prediction utilities for the Sulphur Hazard Intelligence System."""

import joblib
import pandas as pd


def load_model(model_path: str):
    """Load a trained model from file."""
    return joblib.load(model_path)


def predict_hazard(model, df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    """Run hazard predictions and append results to the feature dataset."""
    X = df[feature_columns]
    df = df.copy()
    df["predicted_hazard"] = model.predict(X)
    return df


def save_predictions(df: pd.DataFrame, output_path: str) -> None:
    """Save prediction results to disk."""
    df.to_csv(output_path, index=False)


if __name__ == "__main__":
    print("Use prediction utilities from the package.")
