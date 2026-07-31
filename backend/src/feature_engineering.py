"""Feature engineering for volcanic sulphur hazard classification."""

import pandas as pd
import numpy as np


def add_rolling_features(df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    """Add rolling statistics and derived environmental indicators."""
    df = df.copy()
    df[f"so2_roll_mean_{window}"] = df["so2"].rolling(window=window, min_periods=1).mean()
    df[f"so2_roll_std_{window}"] = df["so2"].rolling(window=window, min_periods=1).std().fillna(0)
    df[f"wind_roll_mean_{window}"] = df["wind_kph"].rolling(window=window, min_periods=1).mean()
    return df


def create_feature_set(df: pd.DataFrame) -> pd.DataFrame:
    """Generate a feature set suitable for model training."""
    df = df.copy()
    df = add_rolling_features(df, window=3)
    df["so2_wind_ratio"] = np.where(df["wind_kph"] != 0, df["so2"] / df["wind_kph"], 0)
    df["night_flag"] = df["timestamp"].dt.hour.isin(range(20, 24)).astype(int)
    return df


def save_feature_data(df: pd.DataFrame, output_path: str) -> None:
    """Save engineered features to CSV."""
    df.to_csv(output_path, index=False)


if __name__ == "__main__":
    print("Use the feature_engineering functions as part of the pipeline.")
