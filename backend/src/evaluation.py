"""Model evaluation functions for the Sulphur Hazard Intelligence System."""

import joblib
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix


def load_model(model_path: str):
    """Load a saved scikit-learn or XGBoost model."""
    return joblib.load(model_path)


def evaluate_model(model, X, y):
    """Evaluate the model and return metrics and confusion matrix."""
    y_pred = model.predict(X)
    report = classification_report(y, y_pred, output_dict=True)
    cm = confusion_matrix(y, y_pred)
    return report, cm


def plot_confusion_matrix(cm, class_names: list[str], output_path: str) -> None:
    """Plot and save a confusion matrix figure."""
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=class_names, yticklabels=class_names)
    plt.ylabel("True Label")
    plt.xlabel("Predicted Label")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


if __name__ == "__main__":
    print("Use evaluation functions from the package.")
