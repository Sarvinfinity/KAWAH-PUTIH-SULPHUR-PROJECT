"""Composite Hazard Index (CHI) utilities for volcanic gas exposure."""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns


def normalize_columns(
    df: pd.DataFrame,
    columns: list[str],
    method: str = "minmax",
    min_value: float = 0.0,
    max_value: float = 1.0,
) -> pd.DataFrame:
    """Normalize the selected gas concentration columns.

    Supported methods:
    - minmax: scale to [min_value, max_value]
    - zscore: standardize to zero mean and unit variance
    """
    df = df.copy()
    if method == "minmax":
        for col in columns:
            values = df[col].astype(float)
            min_val = values.min()
            max_val = values.max()
            if max_val == min_val:
                df[f"{col}_norm"] = 0.0
            else:
                df[f"{col}_norm"] = ((values - min_val) / (max_val - min_val)) * (max_value - min_value) + min_value
    elif method == "zscore":
        for col in columns:
            values = df[col].astype(float)
            mean = values.mean()
            std = values.std(ddof=0)
            df[f"{col}_norm"] = (values - mean) / std if std != 0 else 0.0
    else:
        raise ValueError("method must be 'minmax' or 'zscore'.")
    return df


def compute_chi(
    df: pd.DataFrame,
    so2_col: str = "SO2",
    h2s_col: str = "H2S",
    co2_col: str = "CO2",
    weights: dict[str, float] | None = None,
) -> pd.Series:
    """Compute the Composite Hazard Index (CHI) for each row."""
    if weights is None:
        weights = {"SO2": 0.5, "H2S": 0.3, "CO2": 0.2}

    required = [so2_col, h2s_col, co2_col]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns for CHI: {missing}")

    norm_cols = [f"{col}_norm" for col in required]
    if not all(col in df.columns for col in norm_cols):
        raise KeyError(
            "Normalized columns not found. Run normalize_columns() first to create *_norm columns."
        )

    chi = (
        weights["SO2"] * df[f"{so2_col}_norm"]
        + weights["H2S"] * df[f"{h2s_col}_norm"]
        + weights["CO2"] * df[f"{co2_col}_norm"]
    )
    return chi


def add_chi_column(
    df: pd.DataFrame,
    so2_col: str = "SO2",
    h2s_col: str = "H2S",
    co2_col: str = "CO2",
    method: str = "minmax",
) -> pd.DataFrame:
    """Add normalized gas concentrations and CHI to the DataFrame."""
    df = df.copy()
    df = normalize_columns(df, [so2_col, h2s_col, co2_col], method=method)
    df["CHI"] = compute_chi(df, so2_col=so2_col, h2s_col=h2s_col, co2_col=co2_col)
    return df


def chi_hazard_level(df: pd.DataFrame, chi_col: str = "CHI") -> pd.DataFrame:
    """Classify CHI into hazard levels: Normal, Moderate, Dangerous."""
    df = df.copy()
    if chi_col not in df.columns:
        raise KeyError(f"Required column '{chi_col}' not found in DataFrame.")

    thresholds = {
        "Normal": 0.33,
        "Moderate": 0.66,
    }

    def _level(value: float) -> str:
        if value < thresholds["Normal"]:
            return "Normal"
        if value <= thresholds["Moderate"]:
            return "Moderate"
        return "Dangerous"

    df["chi_hazard_level"] = df[chi_col].astype(float).apply(_level)
    return df


def compare_chi_with_thresholds(
    df: pd.DataFrame,
    threshold_col: str = "hazard_level",
    chi_col: str = "chi_hazard_level",
) -> pd.DataFrame:
    """Compare CHI-based hazard labels to threshold-based hazard labels."""
    if threshold_col not in df.columns or chi_col not in df.columns:
        raise KeyError(f"Required columns '{threshold_col}' or '{chi_col}' not found.")

    comparison = (
        df.groupby([threshold_col, chi_col])
        .size()
        .reset_index(name="count")
        .sort_values([threshold_col, chi_col])
    )
    return comparison


def plot_chi_trends(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    chi_col: str = "CHI",
    node_col: str | None = None,
    output_path: str | None = None,
) -> None:
    """Plot CHI trends over time, optionally separated by node."""
    if timestamp_col not in df.columns or chi_col not in df.columns:
        raise KeyError(f"Required columns '{timestamp_col}' or '{chi_col}' not found in DataFrame.")

    df = df.copy()
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])
    plt.figure(figsize=(12, 5))
    if node_col and node_col in df.columns:
        sns.lineplot(data=df, x=timestamp_col, y=chi_col, hue=node_col, marker="o")
        plt.title("Composite Hazard Index (CHI) Trends by Node")
    else:
        sns.lineplot(data=df, x=timestamp_col, y=chi_col, marker="o", color="darkred")
        plt.title("Composite Hazard Index (CHI) Trends Over Time")

    plt.xlabel("Timestamp")
    plt.ylabel("CHI")
    plt.xticks(rotation=45)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path)
    plt.show()


def node_wise_chi_analysis(
    df: pd.DataFrame,
    node_col: str = "node_id",
    chi_col: str = "CHI",
    output_path: str | None = None,
) -> pd.DataFrame:
    """Compute node-wise CHI statistics and plot distributions."""
    if node_col not in df.columns or chi_col not in df.columns:
        raise KeyError(f"Required columns '{node_col}' or '{chi_col}' not found in DataFrame.")

    summary = (
        df.groupby(node_col)[chi_col]
        .agg(["mean", "median", "std", "min", "max"])
        .reset_index()
    )

    plt.figure(figsize=(8, 5))
    sns.boxplot(data=df, x=node_col, y=chi_col, palette="pastel")
    plt.title("Node-wise Composite Hazard Index Distribution")
    plt.xlabel("Node")
    plt.ylabel("CHI")
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path)
    plt.show()

    return summary


def save_chi_dataset(df: pd.DataFrame, output_path: str) -> None:
    """Save the dataset with CHI and CHI hazard labels."""
    df.to_csv(output_path, index=False)


if __name__ == "__main__":
    print("Use composite hazard functions from the package.")
