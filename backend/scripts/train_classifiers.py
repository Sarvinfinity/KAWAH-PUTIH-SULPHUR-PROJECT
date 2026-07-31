"""Train classification models for hazard prediction.

This script prepares data with temporal blocking, handles class imbalance,
and trains XGBoost and Random Forest classifiers with hyperparameter tuning.
"""

import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split, TimeSeriesSplit, GridSearchCV
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.ensemble import RandomForestClassifier
from imblearn.over_sampling import SMOTE
from imblearn.combine import SMOTETomek
import xgboost as xgb
import sys
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))


def load_selected_features(input_path: str, features_file: str) -> tuple:
    """Load dataset and selected features.
    
    Args:
        input_path: Path to labeled dataset with features
        features_file: Path to selected features list
        
    Returns:
        Tuple of (X, y, feature_names, label_encoder)
    """
    print(f"Loading data from: {input_path}")
    df = pd.read_csv(input_path)
    print(f"Dataset shape: {df.shape}")
    
    # Load selected features
    with open(features_file, 'r') as f:
        lines = f.readlines()
        selected_features = [line.strip().split('. ')[1] for line in lines[2:] if line.strip()]
    
    print(f"Selected features: {len(selected_features)}")
    
    # Define target column
    target_col = "hazard_level_hybrid"
    
    # Encode target
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(df[target_col])
    
    # Select feature columns
    X = df[selected_features].fillna(0)
    
    print(f"Feature matrix shape: {X.shape}")
    print(f"Target classes: {label_encoder.classes_}")
    print(f"Class distribution: {np.bincount(y)}")
    
    return X, y, selected_features, label_encoder


def temporal_train_test_split(X: pd.DataFrame, y: np.ndarray, test_size: float = 0.2) -> tuple:
    """Split data temporally to avoid data leakage.
    
    Args:
        X: Feature matrix
        y: Target labels
        test_size: Proportion of data for testing
        
    Returns:
        Tuple of (X_train, X_test, y_train, y_test)
    """
    print(f"\nPerforming temporal train/test split (test_size={test_size})...")
    
    # Simple temporal split (last 20% for testing)
    split_idx = int(len(X) * (1 - test_size))
    
    X_train = X.iloc[:split_idx]
    X_test = X.iloc[split_idx:]
    y_train = y[:split_idx]
    y_test = y[split_idx:]
    
    print(f"Train size: {len(X_train)}")
    print(f"Test size: {len(X_test)}")
    print(f"Train class distribution: {np.bincount(y_train)}")
    print(f"Test class distribution: {np.bincount(y_test)}")
    
    return X_train, X_test, y_train, y_test


def handle_class_imbalance(X_train: pd.DataFrame, y_train: np.ndarray, method: str = 'smote') -> tuple:
    """Handle class imbalance using SMOTE or class weights.
    
    Args:
        X_train: Training features
        y_train: Training labels
        method: Method to handle imbalance ('smote', 'smotetomek', 'weights')
        
    Returns:
        Tuple of (X_resampled, y_resampled, class_weights)
    """
    print(f"\nHandling class imbalance using: {method}")
    
    if method == 'smote':
        smote = SMOTE(random_state=42, k_neighbors=5)
        X_resampled, y_resampled = smote.fit_resample(X_train, y_train)
        class_weights = None
        print(f"Resampled size: {len(X_resampled)}")
        print(f"Resampled class distribution: {np.bincount(y_resampled)}")
        
    elif method == 'smotetomek':
        smote_tomek = SMOTETomek(random_state=42)
        X_resampled, y_resampled = smote_tomek.fit_resample(X_train, y_train)
        class_weights = None
        print(f"Resampled size: {len(X_resampled)}")
        print(f"Resampled class distribution: {np.bincount(y_resampled)}")
        
    elif method == 'weights':
        X_resampled, y_resampled = X_train, y_train
        # Calculate class weights inversely proportional to class frequency
        class_counts = np.bincount(y_train)
        class_weights = {i: len(y_train) / (len(class_counts) * count) for i, count in enumerate(class_counts)}
        print(f"Class weights: {class_weights}")
        
    else:
        X_resampled, y_resampled = X_train, y_train
        class_weights = None
        print("No imbalance handling applied")
    
    return X_resampled, y_resampled, class_weights


def train_xgboost(X_train: pd.DataFrame, y_train: np.ndarray, class_weights: dict = None) -> xgb.XGBClassifier:
    """Train XGBoost classifier with hyperparameter tuning.
    
    Args:
        X_train: Training features
        y_train: Training labels
        class_weights: Optional class weights for cost-sensitive learning
        
    Returns:
        Trained XGBoost classifier
    """
    print("\n" + "="*80)
    print("Training XGBoost Classifier")
    print("="*80)
    
    # Calculate scale_pos_weight for binary classification (not applicable here)
    # For multi-class, use sample_weight or class weights in parameter
    
    # Base model
    xgb_base = xgb.XGBClassifier(
        objective='multi:softmax',
        num_class=4,
        random_state=42,
        n_jobs=-1,
        eval_metric='mlogloss'
    )
    
    # Hyperparameter grid (reduced for faster training)
    param_grid = {
        'n_estimators': [100, 200],
        'max_depth': [5, 7],
        'learning_rate': [0.1, 0.2],
        'subsample': [0.8, 1.0],
        'colsample_bytree': [0.8, 1.0],
    }
    
    # Time series cross-validation
    tscv = TimeSeriesSplit(n_splits=3)
    
    # Grid search
    print("Performing grid search with TimeSeriesSplit CV...")
    grid_search = GridSearchCV(
        xgb_base,
        param_grid,
        cv=tscv,
        scoring='f1_weighted',
        n_jobs=-1,
        verbose=1
    )
    
    grid_search.fit(X_train, y_train)
    
    print(f"\nBest parameters: {grid_search.best_params_}")
    print(f"Best CV score: {grid_search.best_score_:.4f}")
    
    return grid_search.best_estimator_


def train_random_forest(X_train: pd.DataFrame, y_train: np.ndarray, class_weights: dict = None) -> RandomForestClassifier:
    """Train Random Forest classifier with hyperparameter tuning.
    
    Args:
        X_train: Training features
        y_train: Training labels
        class_weights: Optional class weights for cost-sensitive learning
        
    Returns:
        Trained Random Forest classifier
    """
    print("\n" + "="*80)
    print("Training Random Forest Classifier")
    print("="*80)
    
    # Base model
    rf_base = RandomForestClassifier(
        random_state=42,
        n_jobs=-1,
        class_weight=class_weights
    )
    
    # Hyperparameter grid
    param_grid = {
        'n_estimators': [100, 200],
        'max_depth': [10, 20, None],
        'min_samples_split': [2, 5, 10],
        'min_samples_leaf': [1, 2, 4],
        'max_features': ['sqrt', 'log2', None],
    }
    
    # Time series cross-validation
    tscv = TimeSeriesSplit(n_splits=3)
    
    # Grid search
    print("Performing grid search with TimeSeriesSplit CV...")
    grid_search = GridSearchCV(
        rf_base,
        param_grid,
        cv=tscv,
        scoring='f1_weighted',
        n_jobs=-1,
        verbose=1
    )
    
    grid_search.fit(X_train, y_train)
    
    print(f"\nBest parameters: {grid_search.best_params_}")
    print(f"Best CV score: {grid_search.best_score_:.4f}")
    
    return grid_search.best_estimator_


def evaluate_model(model, X_test: pd.DataFrame, y_test: np.ndarray, label_encoder, model_name: str):
    """Evaluate model performance.
    
    Args:
        model: Trained model
        X_test: Test features
        y_test: Test labels
        label_encoder: Label encoder for class names
        model_name: Name of the model for reporting
    """
    print(f"\n" + "="*80)
    print(f"Evaluating {model_name}")
    print("="*80)
    
    # Predictions
    y_pred = model.predict(X_test)
    
    # Classification report
    print("\nClassification Report:")
    print(classification_report(
        y_test, y_pred,
        target_names=label_encoder.classes_,
        digits=4
    ))
    
    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    print("\nConfusion Matrix:")
    print(cm)
    
    return y_pred, cm


def save_model(model, model_name: str, output_dir: str):
    """Save trained model to disk.
    
    Args:
        model: Trained model
        model_name: Name for the saved model
        output_dir: Directory to save model
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = f"{output_dir}/{model_name}.joblib"
    joblib.dump(model, output_path)
    print(f"Saved model to: {output_path}")


def main():
    """Main execution function."""
    print("="*80)
    print("Train Classification Models for Hazard Prediction")
    print("="*80)
    
    input_path = "data/processed/labeled_hybrid_24H_features.csv"
    features_file = "data/processed/feature_analysis/selected_features.txt"
    output_dir = "models"
    
    # Load data
    X, y, feature_names, label_encoder = load_selected_features(input_path, features_file)
    
    # Temporal train/test split
    X_train, X_test, y_train, y_test = temporal_train_test_split(X, y, test_size=0.2)
    
    # Handle class imbalance
    imbalance_methods = ['weights', 'smote']
    results = {}
    
    for method in imbalance_methods:
        print(f"\n{'='*80}")
        print(f"Training with imbalance handling: {method.upper()}")
        print(f"{'='*80}")
        
        # Handle imbalance
        X_resampled, y_resampled, class_weights = handle_class_imbalance(X_train, y_train, method=method)
        
        # Train XGBoost
        xgb_model = train_xgboost(X_resampled, y_resampled, class_weights)
        y_pred_xgb, cm_xgb = evaluate_model(xgb_model, X_test, y_test, label_encoder, f"XGBoost ({method})")
        save_model(xgb_model, f"xgboost_{method}", output_dir)
        
        # Train Random Forest
        rf_model = train_random_forest(X_resampled, y_resampled, class_weights)
        y_pred_rf, cm_rf = evaluate_model(rf_model, X_test, y_test, label_encoder, f"Random Forest ({method})")
        save_model(rf_model, f"random_forest_{method}", output_dir)
        
        results[method] = {
            'xgb': {'model': xgb_model, 'predictions': y_pred_xgb, 'cm': cm_xgb},
            'rf': {'model': rf_model, 'predictions': y_pred_rf, 'cm': cm_rf}
        }
    
    # Save label encoder
    joblib.dump(label_encoder, f"{output_dir}/label_encoder.joblib")
    print(f"\nSaved label encoder to: {output_dir}/label_encoder.joblib")
    
    # Save feature names
    joblib.dump(feature_names, f"{output_dir}/feature_names.joblib")
    print(f"Saved feature names to: {output_dir}/feature_names.joblib")
    
    print("\n" + "="*80)
    print("✓ Model training complete!")
    print("="*80)
    print(f"Models trained: {len(imbalance_methods) * 2}")
    print(f"Models saved to: {output_dir}")


if __name__ == "__main__":
    main()
