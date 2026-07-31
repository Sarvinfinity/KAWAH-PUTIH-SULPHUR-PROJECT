"""Data preprocessing routines for the Sulphur Hazard Intelligence System."""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import MinMaxScaler, StandardScaler


def load_raw_data(csv_path: str, parse_dates: list[str] = ["timestamp"]) -> pd.DataFrame:
    """Load raw volcanic hazard data from a CSV file."""
    return pd.read_csv(csv_path, parse_dates=parse_dates)


def handle_missing_values(df: pd.DataFrame, method: str = "ffill") -> pd.DataFrame:
    """Fill or drop missing values in the dataset."""
    df = df.copy()
    if method == "ffill":
        return df.fillna(method="ffill").fillna(method="bfill")
    if method == "bfill":
        return df.fillna(method="bfill").fillna(method="ffill")
    if method == "median":
        return df.fillna(df.median(numeric_only=True))
    if method == "mean":
        return df.fillna(df.mean(numeric_only=True))
    if method == "drop":
        return df.dropna()
    raise ValueError("method must be one of 'ffill', 'bfill', 'median', 'mean', or 'drop'.")


def remove_duplicates(df: pd.DataFrame, subset: list[str] | None = None, keep: str = "first") -> pd.DataFrame:
    """Remove duplicate rows from the dataset."""
    df = df.copy()
    return df.drop_duplicates(subset=subset, keep=keep).reset_index(drop=True)


def detect_outliers_iqr(df: pd.DataFrame, columns: list[str], factor: float = 1.5) -> pd.DataFrame:
    """Detect outliers using the IQR method for the specified numeric columns."""
    outlier_mask = pd.DataFrame(index=df.index)
    for col in columns:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - factor * iqr
        upper = q3 + factor * iqr
        outlier_mask[col] = (df[col] < lower) | (df[col] > upper)
    return outlier_mask


def detect_outliers_zscore(df: pd.DataFrame, columns: list[str], threshold: float = 3.0) -> pd.DataFrame:
    """Detect outliers using the z-score method for the specified numeric columns."""
    z_scores = np.abs((df[columns] - df[columns].mean()) / df[columns].std(ddof=0))
    return z_scores > threshold


def normalize_features(df: pd.DataFrame, columns: list[str], method: str = "standard") -> pd.DataFrame:
    """Normalize numeric features using standard scaling or min-max scaling."""
    df = df.copy()
    if method == "standard":
        scaler = StandardScaler()
    elif method == "minmax":
        scaler = MinMaxScaler()
    else:
        raise ValueError("method must be 'standard' or 'minmax'.")

    df[columns] = scaler.fit_transform(df[columns])
    return df


def encode_node_id(df: pd.DataFrame, column: str = "node_id") -> pd.DataFrame:
    """Encode the node_id column using a simple integer mapping if needed."""
    df = df.copy()
    if df[column].dtype == object:
        df[column] = df[column].astype("category").cat.codes
    return df


def visualize_missing(df: pd.DataFrame, output_path: str | None = None) -> None:
    """Plot missing value counts for each column."""
    missing = df.isna().sum()
    plt.figure(figsize=(10, 5))
    sns.barplot(x=missing.index, y=missing.values, palette="viridis")
    plt.title("Missing Values by Column")
    plt.ylabel("Count")
    plt.xticks(rotation=45)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path)
    plt.show()


def visualize_outliers(df: pd.DataFrame, columns: list[str], output_path: str | None = None) -> None:
    """Plot boxplots for numeric features to inspect outliers."""
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=df[columns], palette="coolwarm")
    plt.title("Outlier Distribution by Feature")
    plt.xticks(rotation=45)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path)
    plt.show()


def visualize_distributions(df: pd.DataFrame, columns: list[str], output_path: str | None = None) -> None:
    """Plot distributions for numeric features."""
    n_cols = min(3, len(columns))
    n_rows = int(np.ceil(len(columns) / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))
    axes = np.array(axes).reshape(-1)
    for idx, col in enumerate(columns):
        sns.histplot(df[col].dropna(), kde=True, ax=axes[idx], color="steelblue")
        axes[idx].set_title(f"Distribution of {col}")
    for idx in range(len(columns), len(axes)):
        fig.delaxes(axes[idx])
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path)
    plt.show()


def preprocessing_pipeline(
    df: pd.DataFrame,
    numeric_columns: list[str],
    missing_method: str = "ffill",
    outlier_threshold: float = 3.0,
    normalize_method: str = "standard",
    encode_node: bool = True,
    node_column: str = "node_id",
) -> pd.DataFrame:
    """Run the full preprocessing pipeline for volcanic sulphur sensor data."""
    df = df.copy()
    df = handle_missing_values(df, method=missing_method)
    df = remove_duplicates(df, subset=["timestamp", node_column])

    if encode_node:
        df = encode_node_id(df, column=node_column)

    iqr_mask = detect_outliers_iqr(df, columns=numeric_columns)
    zscore_mask = detect_outliers_zscore(df, columns=numeric_columns, threshold=outlier_threshold)
    df["outlier_iqr"] = iqr_mask.any(axis=1)
    df["outlier_zscore"] = zscore_mask.any(axis=1)

    df = normalize_features(df, columns=numeric_columns, method=normalize_method)
    return df


def save_processed_data(df: pd.DataFrame, output_path: str) -> None:
    """Save processed data to disk."""
    df.to_csv(output_path, index=False)


if __name__ == "__main__":
    print("Use preprocessing functions from the package, not this module directly.")
