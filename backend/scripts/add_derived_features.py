"""Add derived features to labeled datasets for ML training.

This script adds derived features including CHI, exposure dose, meteorological
modifiers, and other engineered features to the labeled datasets.
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend" / "src"))

from hazard_labeling import (
    calculate_meteorological_modifier,
    calculate_node_modifier,
    calculate_chi,
    classify_by_chi,
    METEOROLOGICAL_MODIFIERS,
    NODE_MODIFIERS,
    HYBRID_THRESHOLDS,
    CHI_THRESHOLDS,
)


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived features to the dataset.
    
    Args:
        df: DataFrame with sensor data
        
    Returns:
        DataFrame with added derived features
    """
    df = df.copy()
    
    # Ensure required columns exist
    if "hour" not in df.columns:
        df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour
    
    if "elevation_m" not in df.columns and "elevation" in df.columns:
        df["elevation_m"] = df["elevation"]
    
    if "Wind_kph" not in df.columns:
        df["Wind_kph"] = 5.0  # Default moderate wind
    
    # 1. Meteorological modifiers
    print("Calculating meteorological modifiers...")
    df["meteo_modifier"] = df.apply(calculate_meteorological_modifier, axis=1)
    
    # Individual modifier flags
    df["is_night"] = df["hour"].apply(lambda h: 1 if (h >= 20 or h < 6) else 0)
    df["is_high_humidity"] = df["Humidity_pct"].apply(lambda h: 1 if h > 85 else 0)
    df["is_low_wind"] = df["Wind_kph"].apply(lambda w: 1 if w < 1.5 else 0)
    df["is_temp_inversion"] = df["Temp_C"].apply(lambda t: 1 if t < 5 else 0)
    df["is_high_altitude"] = df["elevation_m"].apply(lambda e: 1 if e > 2000 else 0)
    
    # 2. Node modifiers
    print("Calculating node modifiers...")
    df["node_modifier"] = df["node_id"].apply(calculate_node_modifier)
    
    # 3. Composite Hazard Index (CHI)
    print("Calculating Composite Hazard Index (CHI)...")
    
    # Get critical thresholds for normalization
    so2_critical = HYBRID_THRESHOLDS["SO2"]["10min_avg"]["critical"]
    h2s_critical = HYBRID_THRESHOLDS["H2S"]["10min_avg"]["critical"]
    
    # Calculate normalized values
    df["SO2_normalized"] = df["SO2"] / so2_critical
    df["H2S_normalized"] = df["H2S"] / h2s_critical
    
    # Calculate CHI (exposure factor set to 0 for now)
    df["CHI"] = df.apply(
        lambda row: calculate_chi(
            row["SO2_normalized"],
            row["H2S_normalized"],
            0.0  # Exposure duration factor (simplified)
        ),
        axis=1
    )
    
    # CHI-based classification
    df["CHI_class"] = df["CHI"].apply(classify_by_chi)
    
    # 4. Gas ratio
    print("Calculating gas ratios...")
    df["SO2_H2S_ratio"] = df["SO2"] / (df["H2S"] + 0.001)  # Add small value to avoid division by zero
    
    # 5. Rolling statistics (10-minute window ~ 30 samples at 2-second intervals)
    print("Calculating rolling statistics...")
    window_size = 30
    
    # Group by node to avoid cross-node contamination
    for node_id in df["node_id"].unique():
        node_mask = df["node_id"] == node_id
        df.loc[node_mask, "SO2_rolling_mean_10min"] = df.loc[node_mask, "SO2"].rolling(window=window_size, min_periods=1).mean()
        df.loc[node_mask, "SO2_rolling_std_10min"] = df.loc[node_mask, "SO2"].rolling(window=window_size, min_periods=1).std().fillna(0)
        df.loc[node_mask, "SO2_rolling_max_10min"] = df.loc[node_mask, "SO2"].rolling(window=window_size, min_periods=1).max()
        df.loc[node_mask, "H2S_rolling_mean_10min"] = df.loc[node_mask, "H2S"].rolling(window=window_size, min_periods=1).mean()
        df.loc[node_mask, "H2S_rolling_std_10min"] = df.loc[node_mask, "H2S"].rolling(window=window_size, min_periods=1).std().fillna(0)
        df.loc[node_mask, "H2S_rolling_max_10min"] = df.loc[node_mask, "H2S"].rolling(window=window_size, min_periods=1).max()
    
    # 6. Rate of change
    print("Calculating rate of change...")
    for node_id in df["node_id"].unique():
        node_mask = df["node_id"] == node_id
        df.loc[node_mask, "SO2_rate_of_change"] = df.loc[node_mask, "SO2"].diff().fillna(0)
        df.loc[node_mask, "H2S_rate_of_change"] = df.loc[node_mask, "H2S"].diff().fillna(0)
    
    # 7. Cumulative exposure (simplified - 4-hour rolling window)
    print("Calculating cumulative exposure...")
    window_4hour = 7200  # 4 hours in seconds at 2-second intervals
    
    for node_id in df["node_id"].unique():
        node_mask = df["node_id"] == node_id
        # Simplified cumulative dose (concentration * 1 sample)
        df.loc[node_mask, "SO2_cumulative_4hour"] = df.loc[node_mask, "SO2"].rolling(window=window_4hour, min_periods=1).sum()
        df.loc[node_mask, "H2S_cumulative_4hour"] = df.loc[node_mask, "H2S"].rolling(window=window_4hour, min_periods=1).sum()
    
    # 8. Dispersion index (wind * stability factor)
    print("Calculating dispersion index...")
    # Simple dispersion index: wind speed * (1 - humidity/100)
    df["dispersion_index"] = df["Wind_kph"] * (1 - df["Humidity_pct"] / 100)
    
    # 9. Temporal features (already have hour_sin, hour_cos)
    # Add day/night indicator
    df["day_night"] = df["hour"].apply(lambda h: "Night" if (h >= 20 or h < 6) else "Day")
    
    print("Derived features added successfully!")
    return df


def main():
    """Main execution function."""
    print("="*80)
    print("Add Derived Features to Labeled Datasets")
    print("="*80)
    
    input_dir = "data/processed"
    output_dir = "data/processed"
    
    schemes = ["who", "niosh", "data_driven", "hybrid"]
    
    for scheme in schemes:
        input_path = f"{input_dir}/labeled_{scheme}_24H.csv"
        output_path = f"{output_dir}/labeled_{scheme}_24H_features.csv"
        
        print(f"\n{'='*80}")
        print(f"Processing: {scheme.upper()}")
        print(f"{'='*80}")
        
        # Load labeled dataset
        print(f"Loading from: {input_path}")
        df = pd.read_csv(input_path)
        print(f"Dataset shape: {df.shape}")
        
        # Add derived features
        df_features = add_derived_features(df)
        
        # Save with features
        print(f"Saving to: {output_path}")
        df_features.to_csv(output_path, index=False)
        print(f"Final shape: {df_features.shape}")
        print(f"Columns: {len(df_features.columns)}")
    
    print("\n" + "="*80)
    print("✓ Derived features added to all labeled datasets")
    print("="*80)


if __name__ == "__main__":
    main()
