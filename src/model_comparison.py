"""Compare volcanic hazard classification models and generate publication-quality outputs."""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


def extract_model_metrics(results: dict, model_name: str) -> dict:
    """Extract summary metrics for a trained model result dictionary."""
    metrics = results.get("metrics", {})
    summary = {
        "model": model_name,
        "accuracy": metrics.get("accuracy"),
        "precision_weighted": metrics.get("precision_weighted"),
        "recall_weighted": metrics.get("recall_weighted"),
        "f1_weighted": metrics.get("f1_weighted"),
        "roc_auc_weighted": metrics.get("roc_auc_weighted"),
        "cv_f1_weighted": None,
        "overfitting_delta": None,
    }

    grid_search = results.get("grid_search")
    if grid_search is not None:
        best_score = getattr(grid_search, "best_score_", None)
        summary["cv_f1_weighted"] = best_score
        if summary["f1_weighted"] is not None and best_score is not None:
            summary["overfitting_delta"] = summary["f1_weighted"] - best_score

    return summary


def build_comparison_table(rf_results: dict, xgb_results: dict) -> pd.DataFrame:
    """Build a comparison table containing performance metrics for each model."""
    rows = [
        extract_model_metrics(rf_results, "RandomForest"),
        extract_model_metrics(xgb_results, "XGBoost"),
    ]
    return pd.DataFrame(rows)


def plot_performance_bars(
    comparison_df: pd.DataFrame,
    metrics: list[str] | None = None,
    output_path: str | None = None,
) -> None:
    """Plot performance comparison bars for selected metrics."""
    if metrics is None:
        metrics = ["accuracy", "precision_weighted", "recall_weighted", "f1_weighted", "roc_auc_weighted"]

    plot_df = comparison_df.melt(
        id_vars=["model"],
        value_vars=[m for m in metrics if m in comparison_df.columns],
        var_name="metric",
        value_name="value",
    )
    plot_df = plot_df.dropna(subset=["value"])

    plt.figure(figsize=(10, 6))
    sns.barplot(data=plot_df, x="metric", y="value", hue="model", palette="Set2")
    plt.title("Classification Model Performance Comparison")
    plt.ylabel("Score")
    plt.xlabel("Metric")
    plt.ylim(0, 1)
    plt.legend(title="Model")
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path)
    plt.show()


def plot_overfitting_analysis(
    comparison_df: pd.DataFrame,
    output_path: str | None = None,
) -> None:
    """Plot overfitting analysis using CV versus test F1 weighted scores."""
    if "cv_f1_weighted" not in comparison_df.columns:
        raise ValueError("Comparison dataframe must contain 'cv_f1_weighted'.")

    plot_df = comparison_df.melt(
        id_vars=["model"],
        value_vars=["cv_f1_weighted", "f1_weighted"],
        var_name="stage",
        value_name="score",
    ).dropna(subset=["score"])

    plt.figure(figsize=(8, 5))
    sns.barplot(data=plot_df, x="model", y="score", hue="stage", palette="muted")
    plt.title("Overfitting Analysis: CV vs Test F1 Weighted")
    plt.ylabel("F1 Weighted Score")
    plt.ylim(0, 1)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path)
    plt.show()


def select_best_model(comparison_df: pd.DataFrame, primary_metric: str = "f1_weighted") -> str:
    """Select the best model according to the primary metric and return its name."""
    if primary_metric not in comparison_df.columns:
        raise ValueError(f"Primary metric '{primary_metric}' missing from comparison table.")

    best_index = comparison_df[primary_metric].idxmax()
    return comparison_df.loc[best_index, "model"]


def summarize_model_comparison(comparison_df: pd.DataFrame) -> str:
    """Generate a detailed text summary for model comparison results."""
    rf_row = comparison_df[comparison_df["model"] == "RandomForest"].iloc[0]
    xgb_row = comparison_df[comparison_df["model"] == "XGBoost"].iloc[0]

    summary = [
        "Model Comparison Summary:",
        f"- Random Forest F1-weighted: {rf_row['f1_weighted']:.3f}, XGBoost F1-weighted: {xgb_row['f1_weighted']:.3f}.",
        f"- Random Forest accuracy: {rf_row['accuracy']:.3f}, XGBoost accuracy: {xgb_row['accuracy']:.3f}.",
    ]

    if pd.notna(rf_row.get("roc_auc_weighted")) and pd.notna(xgb_row.get("roc_auc_weighted")):
        summary.append(
            f"- Random Forest ROC-AUC weighted: {rf_row['roc_auc_weighted']:.3f}, XGBoost ROC-AUC weighted: {xgb_row['roc_auc_weighted']:.3f}."
        )

    if pd.notna(rf_row.get("cv_f1_weighted")) and pd.notna(xgb_row.get("cv_f1_weighted")):
        summary.append(
            f"- Random Forest CV F1-weighted: {rf_row['cv_f1_weighted']:.3f}, XGBoost CV F1-weighted: {xgb_row['cv_f1_weighted']:.3f}."
        )
        summary.append(
            f"- Random Forest overfitting delta: {rf_row['overfitting_delta']:.3f}, XGBoost overfitting delta: {xgb_row['overfitting_delta']:.3f}."
        )

    best_model = select_best_model(comparison_df)
    summary.append(f"- Best final model selected: {best_model}.")

    if best_model == "XGBoost":
        summary.append(
            "XGBoost is selected because it achieves a higher balanced F1-weighted score "
            "and typically handles multivariate non-linear interactions better in this volcanic hazard classification task."
        )
    else:
        summary.append(
            "Random Forest is selected because it provides stronger performance on the available test set "
            "with lower apparent overfitting under the selected hyperparameter range."
        )

    return "\n".join(summary)


def save_comparison_table(comparison_df: pd.DataFrame, output_path: str) -> None:
    """Save the comparison table to CSV for downstream reporting."""
    comparison_df.to_csv(output_path, index=False)


if __name__ == "__main__":
    print("Use model comparison utilities from the package.")
