"""Model training utilities for the Sulphur Hazard Intelligence System."""

import joblib
import pandas as pd
import matplotlib.pyplot as plt
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def _evaluate_classification(y_true, y_pred, y_proba=None) -> dict:
    """Compute core classification metrics and optional ROC-AUC for multiclass models."""
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision_weighted": precision_score(y_true, y_pred, average="weighted", zero_division=0),
        "recall_weighted": recall_score(y_true, y_pred, average="weighted", zero_division=0),
        "f1_weighted": f1_score(y_true, y_pred, average="weighted", zero_division=0),
    }

    if y_proba is not None and y_proba.shape[1] > 1:
        try:
            metrics["roc_auc_weighted"] = roc_auc_score(
                y_true,
                y_proba,
                multi_class="ovr",
                average="weighted",
            )
        except ValueError:
            metrics["roc_auc_weighted"] = None
    else:
        metrics["roc_auc_weighted"] = None

    return metrics


def train_xgboost(
    df: pd.DataFrame,
    feature_columns: list[str],
    label_column: str,
    model_path: str,
    param_grid: dict | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
    cv: int = 5,
) -> dict:
    """Train an XGBoost classifier with grid search and save the best model.

    This function supports multiclass classification and returns a full evaluation
    summary including confusion matrix and feature importance.
    """
    if param_grid is None:
        param_grid = {
            "learning_rate": [0.01, 0.1, 0.2],
            "max_depth": [3, 5, 7],
            "n_estimators": [100, 200, 300],
            "subsample": [0.8, 1.0],
        }

    X = df[feature_columns]
    y = df[label_column]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    xgb = XGBClassifier(
        objective="multi:softprob",
        use_label_encoder=False,
        eval_metric="mlogloss",
        random_state=random_state,
    )

    grid_search = GridSearchCV(
        estimator=xgb,
        param_grid=param_grid,
        scoring="f1_weighted",
        cv=cv,
        n_jobs=-1,
        verbose=1,
    )
    grid_search.fit(X_train, y_train)
    best_model = grid_search.best_estimator_

    y_pred = best_model.predict(X_test)
    y_proba = best_model.predict_proba(X_test)

    metrics = _evaluate_classification(y_test, y_pred, y_proba)
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_test, y_pred)

    save_model(best_model, model_path)
    return {
        "best_model": best_model,
        "grid_search": grid_search,
        "metrics": metrics,
        "report": report,
        "confusion_matrix": cm,
        "feature_importances": best_model.feature_importances_,
        "X_test": X_test,
        "y_test": y_test,
        "y_pred": y_pred,
        "y_proba": y_proba,
    }


def train_random_forest(
    df: pd.DataFrame,
    feature_columns: list[str],
    label_column: str,
    model_path: str,
    param_grid: dict | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
    cv: int = 5,
) -> dict:
    """Train a Random Forest baseline classifier with hyperparameter tuning."""
    if param_grid is None:
        param_grid = {
            "n_estimators": [100, 200, 300],
            "max_depth": [None, 10, 20, 30],
        }

    X = df[feature_columns]
    y = df[label_column]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    rf = RandomForestClassifier(random_state=random_state)
    grid_search = GridSearchCV(
        estimator=rf,
        param_grid=param_grid,
        scoring="f1_weighted",
        cv=cv,
        n_jobs=-1,
        verbose=1,
    )
    grid_search.fit(X_train, y_train)
    best_model = grid_search.best_estimator_

    y_pred = best_model.predict(X_test)
    metrics = _evaluate_classification(y_test, y_pred)
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_test, y_pred)

    save_model(best_model, model_path)
    return {
        "best_model": best_model,
        "grid_search": grid_search,
        "metrics": metrics,
        "report": report,
        "confusion_matrix": cm,
        "feature_importances": best_model.feature_importances_,
        "X_test": X_test,
        "y_test": y_test,
        "y_pred": y_pred,
    }


def plot_feature_importance(
    importances: list[float],
    feature_names: list[str],
    title: str = "Feature Importance",
    output_path: str | None = None,
) -> None:
    """Plot feature importance for tree-based classification models."""
    importance_df = pd.DataFrame(
        {"feature": feature_names, "importance": importances}
    ).sort_values("importance", ascending=False)

    plt.figure(figsize=(10, 6))
    plt.barh(importance_df["feature"], importance_df["importance"], color="royalblue")
    plt.gca().invert_yaxis()
    plt.xlabel("Importance")
    plt.title(title)
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path)
    plt.show()


def compare_model_performance(
    rf_results: dict,
    xgb_results: dict,
) -> pd.DataFrame:
    """Compare evaluation metrics between Random Forest and XGBoost results."""
    comparison = pd.DataFrame(
        {
            "model": ["RandomForest", "XGBoost"],
            "accuracy": [rf_results["metrics"]["accuracy"], xgb_results["metrics"]["accuracy"]],
            "precision_weighted": [
                rf_results["metrics"]["precision_weighted"],
                xgb_results["metrics"]["precision_weighted"],
            ],
            "recall_weighted": [
                rf_results["metrics"]["recall_weighted"],
                xgb_results["metrics"]["recall_weighted"],
            ],
            "f1_weighted": [
                rf_results["metrics"]["f1_weighted"],
                xgb_results["metrics"]["f1_weighted"],
            ],
            "roc_auc_weighted": [
                rf_results["metrics"].get("roc_auc_weighted"),
                xgb_results["metrics"].get("roc_auc_weighted"),
            ],
        }
    )
    return comparison


def save_model(model, model_path: str) -> None:
    """Persist the trained model object to disk."""
    joblib.dump(model, model_path)


if __name__ == "__main__":
    print("Use training functions from the package for model development.")
