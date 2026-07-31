"""Validate label distributions and class balance for ML training."""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path


def validate_label_distribution(df: pd.DataFrame, label_col: str, scheme_name: str) -> dict:
    """Validate label distribution and class balance.
    
    Args:
        df: DataFrame with labels
        label_col: Column name for hazard labels
        scheme_name: Name of the threshold scheme
        
    Returns:
        Dictionary with validation metrics
    """
    print(f"\n{'='*80}")
    print(f"Validation: {scheme_name.upper()}")
    print(f"{'='*80}")
    
    # Distribution
    distribution = df[label_col].value_counts()
    percentages = df[label_col].value_counts(normalize=True) * 100
    
    print("\nLabel Distribution:")
    for label in ["Normal", "Moderate", "Dangerous", "Critical"]:
        count = distribution.get(label, 0)
        pct = percentages.get(label, 0)
        print(f"  {label:12s}: {count:6d} ({pct:5.2f}%)")
    
    # Class balance metrics
    metrics = {
        "total_samples": len(df),
        "num_classes": len(distribution),
        "min_class_count": distribution.min(),
        "max_class_count": distribution.max(),
        "class_imbalance_ratio": distribution.max() / distribution.min(),
        "entropy": -sum((pct/100) * np.log2(pct/100) for pct in percentages if pct > 0),
    }
    
    print("\nClass Balance Metrics:")
    print(f"  Total samples: {metrics['total_samples']}")
    print(f"  Number of classes: {metrics['num_classes']}")
    print(f"  Min class count: {metrics['min_class_count']}")
    print(f"  Max class count: {metrics['max_class_count']}")
    print(f"  Imbalance ratio: {metrics['class_imbalance_ratio']:.2f}")
    print(f"  Entropy: {metrics['entropy']:.3f}")
    
    # Assessment
    print("\nAssessment:")
    if metrics['class_imbalance_ratio'] < 2:
        print("  ✓ Well-balanced classes")
    elif metrics['class_imbalance_ratio'] < 5:
        print("  ⚠ Moderate imbalance (consider class weights or SMOTE)")
    else:
        print("  ✗ Severe imbalance (requires resampling or weighted loss)")
    
    if metrics['num_classes'] == 4:
        print("  ✓ All four hazard levels present")
    else:
        print(f"  ⚠ Only {metrics['num_classes']} hazard levels present")
    
    return metrics


def plot_label_distributions(schemes: dict, output_dir: str = "data/processed"):
    """Plot label distributions for all schemes."""
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()
    
    for idx, (scheme, df) in enumerate(schemes.items()):
        label_col = f"hazard_level_{scheme}"
        
        if label_col not in df.columns:
            continue
        
        distribution = df[label_col].value_counts()
        order = ["Normal", "Moderate", "Dangerous", "Critical"]
        
        # Filter to only present labels
        present_labels = [l for l in order if l in distribution.index]
        counts = [distribution[l] for l in present_labels]
        
        ax = axes[idx]
        bars = ax.bar(present_labels, counts, color=['green', 'yellow', 'orange', 'red'])
        ax.set_title(f"{scheme.upper()} Scheme", fontsize=14, fontweight='bold')
        ax.set_ylabel("Count", fontsize=12)
        ax.set_xlabel("Hazard Level", fontsize=12)
        
        # Add count labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height)}',
                   ha='center', va='bottom', fontsize=10)
        
        # Add percentage
        total = len(df)
        for i, label in enumerate(present_labels):
            pct = distribution[label] / total * 100
            ax.text(i, counts[i] * 0.5, f'{pct:.1f}%',
                   ha='center', va='center', fontsize=9, color='white', fontweight='bold')
    
    plt.tight_layout()
    output_path = f"{output_dir}/label_distributions_comparison.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\nSaved comparison plot to: {output_path}")
    plt.close()


def main():
    """Main execution function."""
    import numpy as np
    
    print("="*80)
    print("Label Distribution and Class Balance Validation")
    print("="*80)
    
    input_dir = "data/processed"
    schemes = ["who", "niosh", "data_driven", "hybrid"]
    
    labeled_dfs = {}
    validation_results = {}
    
    for scheme in schemes:
        input_path = f"{input_dir}/labeled_{scheme}_24H_features.csv"
        
        try:
            df = pd.read_csv(input_path)
            label_col = f"hazard_level_{scheme}"
            
            if label_col not in df.columns:
                print(f"\n⚠ Warning: {label_col} not found in {input_path}")
                continue
            
            labeled_dfs[scheme] = df
            validation_results[scheme] = validate_label_distribution(df, label_col, scheme)
            
        except Exception as e:
            print(f"\n✗ Error loading {scheme}: {e}")
            continue
    
    # Plot comparison
    if labeled_dfs:
        plot_label_distributions(labeled_dfs)
    
    # Summary
    print("\n" + "="*80)
    print("Validation Summary")
    print("="*80)
    print(f"Schemes validated: {len(validation_results)}")
    
    for scheme, metrics in validation_results.items():
        print(f"\n{scheme.upper()}:")
        print(f"  Classes: {metrics['num_classes']}")
        print(f"  Imbalance ratio: {metrics['class_imbalance_ratio']:.2f}")
    
    print("\n✓ Validation complete!")


if __name__ == "__main__":
    main()
