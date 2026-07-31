"""
Model training utilities for the Sulphur Hazard Intelligence System.

Refactored for Part 8 Validation: Performs multi-model ablation studies across
multiple labeling frameworks to objectively determine the optimal ML target.
"""

import os
import joblib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
)
import warnings
warnings.filterwarnings('ignore')

def _evaluate_classification(y_true, y_pred, y_proba=None) -> dict:
    """Compute core classification metrics."""
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, average="weighted", zero_division=0),
        "recall": recall_score(y_true, y_pred, average="weighted", zero_division=0),
        "f1": f1_score(y_true, y_pred, average="weighted", zero_division=0),
    }

    if y_proba is not None and y_proba.shape[1] > 1:
        try:
            metrics["roc_auc"] = roc_auc_score(
                y_true, y_proba, multi_class="ovr", average="weighted"
            )
        except ValueError:
            metrics["roc_auc"] = np.nan
    else:
        metrics["roc_auc"] = np.nan

    return metrics


def run_ml_ablation_study(
    df: pd.DataFrame, 
    feature_columns: list[str], 
    label_columns: list[str],
    output_csv: str
):
    """
    Trains Decision Tree, Random Forest, and XGBoost on multiple labeling schemes.
    Saves the comparative metrics to a CSV file.
    """
    results = []
    
    # Base hyperparameters for fair comparison
    rf_params = {"n_estimators": 100, "max_depth": 10, "random_state": 42, "n_jobs": -1}
    xgb_params = {"n_estimators": 100, "max_depth": 6, "learning_rate": 0.1, "random_state": 42, "eval_metric": "mlogloss", "n_jobs": -1}
    dt_params = {"max_depth": 10, "random_state": 42}
    
    for label_col in label_columns:
        print(f"\n--- Evaluating Target: {label_col} ---")
        
        # Check if label exists and has multiple classes
        if label_col not in df.columns:
            print(f"Skipping {label_col} (not found in dataframe)")
            continue
            
        valid_df = df.dropna(subset=[label_col] + feature_columns)
        if len(valid_df[label_col].unique()) < 2:
            print(f"Skipping {label_col} (needs >1 class)")
            continue
            
        X = valid_df[feature_columns]
        y_raw = valid_df[label_col]
        
        le = LabelEncoder()
        y = le.fit_transform(y_raw)
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        models = {
            'Decision Tree': DecisionTreeClassifier(**dt_params),
            'Random Forest': RandomForestClassifier(**rf_params),
            'XGBoost': XGBClassifier(**xgb_params)
        }
        
        for model_name, model in models.items():
            print(f"  Training {model_name}...")
            model.fit(X_train, y_train)
            
            y_pred = model.predict(X_test)
            try:
                y_proba = model.predict_proba(X_test)
            except:
                y_proba = None
                
            metrics = _evaluate_classification(y_test, y_pred, y_proba)
            
            results.append({
                'Framework': label_col.replace('label_', '').upper(),
                'Model': model_name,
                'Accuracy': metrics['accuracy'],
                'Precision': metrics['precision'],
                'Recall': metrics['recall'],
                'F1_Score': metrics['f1'],
                'ROC_AUC': metrics['roc_auc']
            })
            
    results_df = pd.DataFrame(results)
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    results_df.to_csv(output_csv, index=False)
    print(f"\nML Ablation Study complete. Saved to {output_csv}")
    return results_df

if __name__ == "__main__":
    print("This module provides training utilities. Import run_ml_ablation_study directly.")
