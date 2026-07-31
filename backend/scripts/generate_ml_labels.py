"""Generate ML classification labels using multiple threshold schemes.

This script applies the Hybrid Threshold Framework and other schemes to the
expanded 24-hour dataset to generate labels for machine learning classification.
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend" / "src"))

from hazard_labeling import (
    add_hazard_level,
    display_class_distribution,
    save_labeled_dataset,
    calculate_meteorological_modifier,
    calculate_chi,
    classify_by_chi,
    HAZARD_LABELS,
)


def add_missing_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add columns required for hybrid framework if missing."""
    df = df.copy()
    
    # Add hour column if missing
    if "hour" not in df.columns:
        df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour
    
    # Add elevation_m column if missing (use existing elevation column)
    if "elevation_m" not in df.columns and "elevation" in df.columns:
        df["elevation_m"] = df["elevation"]
    
    # Add Wind_kph column if missing (placeholder - would need actual wind data)
    if "Wind_kph" not in df.columns:
        # Use a default value of 5.0 km/h (moderate wind)
        # In production, this should come from actual meteorological data
        df["Wind_kph"] = 5.0
    
    return df


def analyze_gas_concentrations(df: pd.DataFrame) -> dict:
    """Analyze SO2 and H2S concentration ranges."""
    analysis = {
        "SO2": {
            "min": df["SO2"].min(),
            "max": df["SO2"].max(),
            "mean": df["SO2"].mean(),
            "median": df["SO2"].median(),
            "std": df["SO2"].std(),
        },
        "H2S": {
            "min": df["H2S"].min(),
            "max": df["H2S"].max(),
            "mean": df["H2S"].mean(),
            "median": df["H2S"].median(),
            "std": df["H2S"].std(),
        },
    }
    return analysis


def apply_scaling_factor(df: pd.DataFrame, scale_factor: float = 1.0) -> pd.DataFrame:
    """Apply scaling factor to SO2 and H2S concentrations.
    
    Args:
        df: DataFrame with SO2 and H2S columns
        scale_factor: Factor to multiply concentrations by (e.g., 0.001 to convert ppb to ppm)
        
    Returns:
        DataFrame with scaled concentrations
    """
    df = df.copy()
    df["SO2"] = df["SO2"] * scale_factor
    df["H2S"] = df["H2S"] * scale_factor
    return df


def generate_labels_all_schemes(
    df: pd.DataFrame,
    scale_factor: float = 1.0,
    output_dir: str = "data/processed",
) -> dict:
    """Generate labels using all threshold schemes.
    
    Args:
        df: Input DataFrame with sensor data
        scale_factor: Scaling factor for gas concentrations
        output_dir: Directory to save labeled datasets
        
    Returns:
        Dictionary of labeled DataFrames for each scheme
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    # Apply scaling if needed
    if scale_factor != 1.0:
        df = apply_scaling_factor(df, scale_factor)
    
    # Add missing columns
    df = add_missing_columns(df)
    
    labeled_dfs = {}
    
    # Generate labels for each scheme
    schemes = ["WHO", "NIOSH", "DATA_DRIVEN", "HYBRID"]
    
    for scheme in schemes:
        print(f"\n{'='*60}")
        print(f"Generating labels using {scheme} scheme")
        print(f"{'='*60}")
        
        try:
            df_labeled = add_hazard_level(df, scheme=scheme, label_col=f"hazard_level_{scheme.lower()}")
            
            # Display distribution
            distribution = display_class_distribution(df_labeled, label_col=f"hazard_level_{scheme.lower()}")
            
            # Save labeled dataset
            output_path = f"{output_dir}/labeled_{scheme.lower()}_24H.csv"
            save_labeled_dataset(df_labeled, output_path)
            print(f"Saved labeled dataset to: {output_path}")
            
            labeled_dfs[scheme] = df_labeled
            
        except Exception as e:
            print(f"Error generating {scheme} labels: {e}")
            continue
    
    return labeled_dfs


def main():
    """Main execution function."""
    print("="*80)
    print("ML Classification Label Generation")
    print("="*80)
    
    # Load expanded dataset
    data_path = "expanded_24H_all_data.csv"
    print(f"\nLoading dataset from: {data_path}")
    df = pd.read_csv(data_path)
    print(f"Dataset shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    
    # Analyze gas concentrations
    print("\n" + "="*80)
    print("Gas Concentration Analysis (Original Units)")
    print("="*80)
    analysis = analyze_gas_concentrations(df)
    for gas, stats in analysis.items():
        print(f"\n{gas}:")
        for stat, value in stats.items():
            print(f"  {stat}: {value:.2f}")
    
    # Check if scaling is needed
    print("\n" + "="*80)
    print("Threshold Comparison")
    print("="*80)
    print("Hybrid Framework Thresholds (ppm):")
    print("  SO2 Critical: 1.0 ppm")
    print("  H2S Critical: 0.5 ppm")
    print("\nDataset Concentrations:")
    print(f"  SO2 Max: {analysis['SO2']['max']:.2f}")
    print(f"  H2S Max: {analysis['H2S']['max']:.2f}")
    
    # Determine if scaling is needed
    # If values are > 10x the critical threshold, likely in different units
    so2_scale_needed = analysis['SO2']['max'] > 10.0
    h2s_scale_needed = analysis['H2S']['max'] > 0.5
    
    if so2_scale_needed or h2s_scale_needed:
        print("\n⚠️  WARNING: Gas concentrations appear to be in different units than ppm.")
        print("   Applying scaling factor of 0.001 (assuming ppb → ppm conversion)")
        scale_factor = 0.001
    else:
        print("\n✓ Gas concentrations appear to be in ppm (no scaling needed)")
        scale_factor = 1.0
    
    # Generate labels for all schemes
    labeled_dfs = generate_labels_all_schemes(df, scale_factor=scale_factor)
    
    # Summary
    print("\n" + "="*80)
    print("Label Generation Summary")
    print("="*80)
    print(f"Schemes processed: {len(labeled_dfs)}")
    for scheme in labeled_dfs.keys():
        print(f"  ✓ {scheme}")
    
    print("\n✓ Label generation complete!")
    print(f"Labeled datasets saved to: data/processed/")


if __name__ == "__main__":
    main()
