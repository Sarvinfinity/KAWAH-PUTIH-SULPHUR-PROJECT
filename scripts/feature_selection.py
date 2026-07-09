"""Perform feature selection and importance analysis for ML training.

This script analyzes feature importance, correlations, and selects optimal features
for machine learning classification using the HYBRID threshold scheme.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import mutual_info_classif, SelectKBest
from sklearn.preprocessing import LabelEncoder
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def load_and_prepare_data(input_path: str) -> tuple:
    """Load labeled dataset and prepare for feature analysis.
    
    Args:
        input_path: Path to labeled dataset with features
        
    Returns:
        Tuple of (X, y, feature_names, label_encoder)
    """
    print(f"Loading data from: {input_path}")
    df = pd.read_csv(input_path)
    print(f"Dataset shape: {df.shape}")
    
    # Define target column
    target_col = "hazard_level_hybrid"
    
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in dataset")
    
    # Encode target
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(df[target_col])
    
    # Select feature columns (exclude non-numeric and target)
    exclude_cols = [
        "timestamp", "node_id", "location", "elevation", "elevation_m",
        "day_night", "hazard_level_hybrid", "CHI_class",
        "ack_success", "hour"  # hour is represented by hour_sin, hour_cos
    ]
    
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    
    # Remove columns with all NaN or constant values
    feature_cols = [col for col in feature_cols if df[col].notna().any() and df[col].nunique() > 1]
    
    X = df[feature_cols].fillna(0)
    
    print(f"Features selected: {len(feature_cols)}")
    print(f"Target classes: {label_encoder.classes_}")
    
    return X, y, feature_cols, label_encoder


def analyze_feature_correlations(X: pd.DataFrame, feature_names: list, output_dir: str):
    """Analyze and visualize feature correlations.
    
    Args:
        X: Feature matrix
        feature_names: List of feature names
        output_dir: Directory to save outputs
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n" + "="*80)
    print("Feature Correlation Analysis")
    print("="*80)
    
    # Calculate correlation matrix
    corr_matrix = X.corr()
    
    # Find highly correlated features (>0.9)
    high_corr_pairs = []
    for i in range(len(corr_matrix.columns)):
        for j in range(i+1, len(corr_matrix.columns)):
            corr_val = corr_matrix.iloc[i, j]
            if abs(corr_val) > 0.9:
                high_corr_pairs.append((corr_matrix.columns[i], corr_matrix.columns[j], corr_val))
    
    print(f"\nHighly correlated feature pairs (|r| > 0.9): {len(high_corr_pairs)}")
    for feat1, feat2, corr in high_corr_pairs[:10]:  # Show first 10
        print(f"  {feat1} <-> {feat2}: {corr:.3f}")
    
    # Plot correlation heatmap
    plt.figure(figsize=(16, 14))
    sns.heatmap(corr_matrix, cmap='coolwarm', center=0, 
                annot=False, fmt='.2f', cbar_kws={'label': 'Correlation'})
    plt.title('Feature Correlation Matrix', fontsize=16, fontweight='bold')
    plt.tight_layout()
    output_path = f"{output_dir}/feature_correlation_heatmap.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved correlation heatmap to: {output_path}")
    plt.close()
    
    return high_corr_pairs


def analyze_feature_importance_rf(X: pd.DataFrame, y: np.ndarray, feature_names: list, output_dir: str):
    """Analyze feature importance using Random Forest.
    
    Args:
        X: Feature matrix
        y: Target labels
        feature_names: List of feature names
        output_dir: Directory to save outputs
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n" + "="*80)
    print("Random Forest Feature Importance")
    print("="*80)
    
    # Train Random Forest
    rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    rf.fit(X, y)
    
    # Get feature importances
    importances = rf.feature_importances_
    indices = np.argsort(importances)[::-1]
    
    # Print feature rankings
    print("\nFeature ranking:")
    for i, idx in enumerate(indices[:20]):  # Top 20
        print(f"  {i+1:2d}. {feature_names[idx]:30s}: {importances[idx]:.4f}")
    
    # Plot feature importances
    plt.figure(figsize=(12, 8))
    plt.title('Random Forest Feature Importances', fontsize=16, fontweight='bold')
    plt.bar(range(len(indices[:20])), importances[indices[:20]], align='center')
    plt.xticks(range(len(indices[:20])), [feature_names[i] for i in indices[:20]], rotation=45, ha='right')
    plt.xlabel('Feature', fontsize=12)
    plt.ylabel('Importance', fontsize=12)
    plt.tight_layout()
    output_path = f"{output_dir}/rf_feature_importance.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved RF importance plot to: {output_path}")
    plt.close()
    
    return dict(zip(feature_names, importances))


def analyze_mutual_information(X: pd.DataFrame, y: np.ndarray, feature_names: list, output_dir: str):
    """Analyze feature importance using mutual information.
    
    Args:
        X: Feature matrix
        y: Target labels
        feature_names: List of feature names
        output_dir: Directory to save outputs
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n" + "="*80)
    print("Mutual Information Feature Selection")
    print("="*80)
    
    # Calculate mutual information
    mi_scores = mutual_info_classif(X, y, random_state=42)
    
    # Create DataFrame for easy viewing
    mi_df = pd.DataFrame({'feature': feature_names, 'mi_score': mi_scores})
    mi_df = mi_df.sort_values('mi_score', ascending=False)
    
    print("\nTop 20 features by mutual information:")
    for i, row in mi_df.head(20).iterrows():
        print(f"  {row['feature']:30s}: {row['mi_score']:.4f}")
    
    # Plot mutual information scores
    plt.figure(figsize=(12, 8))
    plt.title('Mutual Information Scores', fontsize=16, fontweight='bold')
    plt.bar(range(len(mi_df.head(20))), mi_df.head(20)['mi_score'], align='center')
    plt.xticks(range(len(mi_df.head(20))), mi_df.head(20)['feature'], rotation=45, ha='right')
    plt.xlabel('Feature', fontsize=12)
    plt.ylabel('Mutual Information Score', fontsize=12)
    plt.tight_layout()
    output_path = f"{output_dir}/mutual_information_scores.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved MI plot to: {output_path}")
    plt.close()
    
    return mi_df


def select_features(X: pd.DataFrame, y: np.ndarray, feature_names: list, k: int = 20) -> tuple:
    """Select top k features using mutual information.
    
    Args:
        X: Feature matrix
        y: Target labels
        feature_names: List of feature names
        k: Number of features to select
        
    Returns:
        Tuple of (X_selected, selected_features, selector)
    """
    print(f"\nSelecting top {k} features using mutual information...")
    
    selector = SelectKBest(mutual_info_classif, k=k)
    X_selected = selector.fit_transform(X, y)
    
    selected_indices = selector.get_support(indices=True)
    selected_features = [feature_names[i] for i in selected_indices]
    
    print(f"Selected features: {selected_features}")
    
    return X_selected, selected_features, selector


def generate_feature_summary(X: pd.DataFrame, feature_names: list, output_dir: str):
    """Generate summary statistics for all features.
    
    Args:
        X: Feature matrix
        feature_names: List of feature names
        output_dir: Directory to save outputs
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n" + "="*80)
    print("Feature Summary Statistics")
    print("="*80)
    
    # Calculate summary statistics
    summary = X.describe()
    
    # Save to CSV
    output_path = f"{output_dir}/feature_summary_statistics.csv"
    summary.to_csv(output_path)
    print(f"Saved feature summary to: {output_path}")
    
    # Print summary
    print("\nFeature statistics:")
    print(summary.T)


def main():
    """Main execution function."""
    print("="*80)
    print("Feature Selection and Importance Analysis")
    print("="*80)
    
    input_path = "data/processed/labeled_hybrid_24H_features.csv"
    output_dir = "data/processed/feature_analysis"
    
    # Load and prepare data
    X, y, feature_names, label_encoder = load_and_prepare_data(input_path)
    
    # Generate feature summary
    generate_feature_summary(X, feature_names, output_dir)
    
    # Analyze correlations
    high_corr_pairs = analyze_feature_correlations(X, feature_names, output_dir)
    
    # Analyze Random Forest importance
    rf_importances = analyze_feature_importance_rf(X, y, feature_names, output_dir)
    
    # Analyze mutual information
    mi_scores = analyze_mutual_information(X, y, feature_names, output_dir)
    
    # Select top features
    X_selected, selected_features, selector = select_features(X, y, feature_names, k=20)
    
    # Save selected features list
    import os
    os.makedirs(output_dir, exist_ok=True)
    selected_features_path = f"{output_dir}/selected_features.txt"
    with open(selected_features_path, 'w') as f:
        f.write("Selected Features for ML Training\n")
        f.write("="*50 + "\n")
        for i, feat in enumerate(selected_features, 1):
            f.write(f"{i:2d}. {feat}\n")
    print(f"Saved selected features to: {selected_features_path}")
    
    print("\n" + "="*80)
    print("✓ Feature analysis complete!")
    print("="*80)
    print(f"Total features analyzed: {len(feature_names)}")
    print(f"Selected features: {len(selected_features)}")
    print(f"Highly correlated pairs found: {len(high_corr_pairs)}")
    print(f"\nOutputs saved to: {output_dir}")


if __name__ == "__main__":
    main()
