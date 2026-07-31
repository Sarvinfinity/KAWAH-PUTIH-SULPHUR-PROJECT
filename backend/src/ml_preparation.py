"""Machine learning dataset preparation for volcanic sulphur hazard classification."""

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder


def select_features_and_target(
    df: pd.DataFrame,
    feature_columns: list[str] = None,
    target_column: str = "hazard_level",
) -> tuple[pd.DataFrame, pd.Series]:
    """Select feature columns and target series from the dataset."""
    if feature_columns is None:
        feature_columns = ["SO2", "H2S", "CO2", "temperature", "humidity", "CHI", "node_id"]

    missing = set(feature_columns + [target_column]) - set(df.columns)
    if missing:
        raise KeyError(f"Missing required columns: {sorted(missing)}")

    X = df[feature_columns].copy()
    y = df[target_column].copy()
    return X, y


def encode_node_id(df: pd.DataFrame, column: str = "node_id") -> pd.DataFrame:
    """Ensure node_id is encoded numerically for ML models."""
    df = df.copy()
    if column not in df.columns:
        raise KeyError(f"Required column '{column}' not found in DataFrame.")

    if df[column].dtype == object:
        df[column] = pd.Categorical(df[column]).codes
    return df


def create_preprocessing_pipeline(
    numeric_features: list[str],
    categorical_features: list[str] | None = None,
    scaler: object = StandardScaler(),
) -> ColumnTransformer:
    """Build a preprocessing pipeline for numeric and optional categorical features."""
    if categorical_features is None:
        categorical_features = []

    transformers = [
        ("num", scaler, numeric_features),
    ]

    if categorical_features:
        transformers.append(
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse=False), categorical_features)
        )

    return ColumnTransformer(transformers=transformers, remainder="drop")


def split_train_test(
    X: pd.DataFrame,
    y: pd.Series,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Split the dataset into stratified training and testing sets."""
    return train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )


def build_ml_pipeline(
    numeric_features: list[str],
    categorical_features: list[str] | None = None,
    scaler: object = StandardScaler(),
) -> Pipeline:
    """Build a complete ML preprocessing pipeline."""
    preprocessor = create_preprocessing_pipeline(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        scaler=scaler,
    )
    return Pipeline([("preprocessor", preprocessor)])


def prepare_ml_dataset(
    df: pd.DataFrame,
    feature_columns: list[str] = None,
    target_column: str = "hazard_level",
    numeric_features: list[str] = None,
    categorical_features: list[str] | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, object]:
    """Prepare data for ML classification with stratified train-test split and scaling."""
    if feature_columns is None:
        feature_columns = ["SO2", "H2S", "CO2", "temperature", "humidity", "CHI", "node_id"]
    if numeric_features is None:
        numeric_features = ["SO2", "H2S", "CO2", "temperature", "humidity", "CHI", "node_id"]

    X, y = select_features_and_target(df, feature_columns, target_column)
    X = encode_node_id(X, column="node_id")

    X_train, X_test, y_train, y_test = split_train_test(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
    )

    pipeline = build_ml_pipeline(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )

    X_train_scaled = pipeline.fit_transform(X_train)
    X_test_scaled = pipeline.transform(X_test)

    return {
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "X_train_scaled": X_train_scaled,
        "X_test_scaled": X_test_scaled,
        "pipeline": pipeline,
    }


def display_dataset_summary(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
) -> None:
    """Print shapes and class balance for train and test datasets."""
    print("Training shape:", X_train.shape)
    print("Testing shape:", X_test.shape)
    print("\nTraining class balance:\n", y_train.value_counts(normalize=True).rename("proportion"))
    print("\nTesting class balance:\n", y_test.value_counts(normalize=True).rename("proportion"))


if __name__ == "__main__":
    print("Use the ml_preparation functions from the package.")
