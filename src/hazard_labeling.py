"""Rule-based and data-driven hazard labeling for volcanic sulphur monitoring.

This module implements the Hybrid Threshold Framework for Kawah Putih volcanic
environment, combining volcanic literature standards with health-based guidelines.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Optional, Tuple


HAZARD_LABELS = ["Normal", "Moderate", "Dangerous", "Critical"]
LABEL_ENCODINGS = {label: idx for idx, label in enumerate(HAZARD_LABELS)}
SEVERITY_ORDER = LABEL_ENCODINGS

# ============================================================================
# HYBRID THRESHOLD FRAMEWORK - Kawah Putih Volcanic Environment
# ============================================================================

# Primary thresholds based on volcanic literature (ppm)
HYBRID_THRESHOLDS = {
    "SO2": {
        "1min_peak": {"normal": 0.1, "moderate": 0.5, "dangerous": 2.0, "critical": 2.0},
        "10min_avg": {"normal": 0.05, "moderate": 0.2, "dangerous": 1.0, "critical": 1.0},
        "1hour_avg": {"normal": 0.03, "moderate": 0.1, "dangerous": 0.5, "critical": 0.5},
        "4hour_avg": {"normal": 0.02, "moderate": 0.05, "dangerous": 0.2, "critical": 0.2},
    },
    "H2S": {
        "1min_peak": {"normal": 0.05, "moderate": 0.2, "dangerous": 1.0, "critical": 1.0},
        "10min_avg": {"normal": 0.02, "moderate": 0.1, "dangerous": 0.5, "critical": 0.5},
        "1hour_avg": {"normal": 0.01, "moderate": 0.05, "dangerous": 0.2, "critical": 0.2},
    },
}

# CHI thresholds for composite hazard index (lower bounds)
CHI_THRESHOLDS = {
    "normal": 0.0,      # Lower bound for Normal
    "moderate": 0.3,    # Lower bound for Moderate
    "dangerous": 0.5,   # Lower bound for Dangerous
    "critical": 0.8,    # Lower bound for Critical
}

# Meteorological modifiers (multipliers applied to thresholds)
METEOROLOGICAL_MODIFIERS = {
    "night_time": {"condition": lambda row: row["hour"] >= 20 or row["hour"] < 6, "modifier": 0.7},
    "high_humidity": {"condition": lambda row: row["Humidity_pct"] > 85, "modifier": 0.8},
    "low_wind": {"condition": lambda row: row["Wind_kph"] < 1.5, "modifier": 0.7},
    "temp_inversion": {"condition": lambda row: row["Temp_C"] < 5, "modifier": 0.6},
    "high_altitude": {"condition": lambda row: row["elevation_m"] > 2000, "modifier": 0.8},
}

# Node-specific modifiers based on elevation and proximity
NODE_MODIFIERS = {
    1: 0.9,  # Higher elevation (2201.98m), closer to emission source
    2: 1.0,  # Lower elevation (2192.38m), further from source
}

# Legacy thresholds for comparison (kept for backward compatibility)
NODE_THRESHOLDS = {
    1: {
        "SO2": {"normal": 3.0, "moderate": 6.0, "dangerous": 9.0, "critical": 12.0},
        "H2S": {"normal": 5.0, "moderate": 10.0, "dangerous": 20.0, "critical": 40.0},
    },
    2: {
        "SO2": {"normal": 2.0, "moderate": 5.0, "dangerous": 8.0, "critical": 12.0},
        "H2S": {"normal": 4.0, "moderate": 8.0, "dangerous": 15.0, "critical": 30.0},
    },
}

STANDARD_THRESHOLDS = {
    "WHO": {
        "SO2": {"normal": 3.0, "moderate": 6.0, "dangerous": 10.0, "critical": 20.0},
        "H2S": {"normal": 5.0, "moderate": 10.0, "dangerous": 20.0, "critical": 40.0},
    },
    "NIOSH": {
        "SO2": {"normal": 2.0, "moderate": 5.0, "dangerous": 10.0, "critical": 20.0},
        "H2S": {"normal": 4.0, "moderate": 8.0, "dangerous": 15.0, "critical": 30.0},
    },
}


# ============================================================================
# HYBRID FRAMEWORK FUNCTIONS
# ============================================================================

def calculate_meteorological_modifier(row: pd.Series) -> float:
    """Calculate the combined meteorological modifier for a given row.
    
    Returns the product of all applicable modifiers (values < 1.0 reduce thresholds).
    """
    modifier = 1.0
    
    for mod_name, mod_config in METEOROLOGICAL_MODIFIERS.items():
        try:
            if mod_config["condition"](row):
                modifier *= mod_config["modifier"]
        except (KeyError, TypeError):
            # Skip modifier if required column is missing or condition fails
            continue
    
    return modifier


def calculate_node_modifier(node_id: int) -> float:
    """Get the node-specific modifier based on elevation and proximity.
    
    Args:
        node_id: The node identifier (1 or 2)
        
    Returns:
        Modifier value (0.9 for Node 1, 1.0 for Node 2, 1.0 for unknown nodes)
    """
    return NODE_MODIFIERS.get(node_id, 1.0)


def calculate_chi(
    so2_normalized: float,
    h2s_normalized: float,
    exposure_duration_factor: float,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Calculate the Composite Hazard Index (CHI).
    
    CHI = (SO2_norm × 0.6) + (H2S_norm × 0.3) + (Exposure_Duration × 0.1)
    
    Args:
        so2_normalized: SO2 concentration normalized by critical threshold
        h2s_normalized: H2S concentration normalized by critical threshold
        exposure_duration_factor: Cumulative exposure time / 4 hours
        weights: Optional custom weights for the CHI calculation
        
    Returns:
        Composite Hazard Index value (0.0 to 1.0+)
    """
    if weights is None:
        weights = {"SO2": 0.6, "H2S": 0.3, "exposure": 0.1}
    
    chi = (
        weights["SO2"] * so2_normalized +
        weights["H2S"] * h2s_normalized +
        weights["exposure"] * min(exposure_duration_factor, 1.0)
    )
    
    return chi


def classify_by_chi(chi_value: float) -> str:
    """Classify hazard level based on CHI value.
    
    Classification rules:
    - Normal: CHI < 0.3
    - Moderate: 0.3 <= CHI < 0.5
    - Dangerous: 0.5 <= CHI < 0.8
    - Critical: CHI >= 0.8
    
    Args:
        chi_value: Composite Hazard Index value
        
    Returns:
        Hazard level string ("Normal", "Moderate", "Dangerous", "Critical")
    """
    if chi_value >= CHI_THRESHOLDS["critical"]:
        return "Critical"
    elif chi_value >= CHI_THRESHOLDS["dangerous"]:
        return "Dangerous"
    elif chi_value >= CHI_THRESHOLDS["moderate"]:
        return "Moderate"
    else:
        return "Normal"


def apply_threshold_modifiers(
    base_threshold: float,
    meteorological_modifier: float,
    node_modifier: float,
) -> float:
    """Apply meteorological and node modifiers to a base threshold.
    
    Args:
        base_threshold: The unmodified threshold value
        meteorological_modifier: Combined meteorological modifier
        node_modifier: Node-specific modifier
        
    Returns:
        Modified threshold value
    """
    return base_threshold * meteorological_modifier * node_modifier


def label_hazard_hybrid(
    row: pd.Series,
    so2_col: str = "SO2",
    h2s_col: str = "H2S",
    node_col: str = "node_id",
    timestamp_col: str = "timestamp",
) -> str:
    """Assign hazard category using the Hybrid Threshold Framework.
    
    This function implements the complete hybrid framework including:
    - Gas concentration thresholds (SO2, H2S)
    - Meteorological modifiers
    - Node-specific adjustments
    - Composite Hazard Index (CHI)
    - Time-weighted exposure tracking
    
    Args:
        row: Pandas Series containing sensor data
        so2_col: Column name for SO2 concentration
        h2s_col: Column name for H2S concentration
        node_col: Column name for node ID
        timestamp_col: Column name for timestamp
        
    Returns:
        Hazard level string ("Normal", "Moderate", "Dangerous", "Critical")
    """
    # Extract values
    so2 = float(row[so2_col])
    h2s = float(row[h2s_col])
    node_id = int(row[node_col])
    
    # Calculate modifiers
    meteo_modifier = calculate_meteorological_modifier(row)
    node_modifier = calculate_node_modifier(node_id)
    combined_modifier = meteo_modifier * node_modifier
    
    # Get modified thresholds for 10-minute average (primary metric)
    so2_thresholds = HYBRID_THRESHOLDS["SO2"]["10min_avg"]
    h2s_thresholds = HYBRID_THRESHOLDS["H2S"]["10min_avg"]
    
    # Apply modifiers to thresholds
    so2_critical = apply_threshold_modifiers(
        so2_thresholds["critical"], meteo_modifier, node_modifier
    )
    so2_dangerous = apply_threshold_modifiers(
        so2_thresholds["dangerous"], meteo_modifier, node_modifier
    )
    so2_moderate = apply_threshold_modifiers(
        so2_thresholds["moderate"], meteo_modifier, node_modifier
    )
    
    h2s_critical = apply_threshold_modifiers(
        h2s_thresholds["critical"], meteo_modifier, node_modifier
    )
    h2s_dangerous = apply_threshold_modifiers(
        h2s_thresholds["dangerous"], meteo_modifier, node_modifier
    )
    h2s_moderate = apply_threshold_modifiers(
        h2s_thresholds["moderate"], meteo_modifier, node_modifier
    )
    
    # Gas concentration classification
    if so2 > so2_critical or h2s > h2s_critical:
        gas_label = "Critical"
    elif so2 > so2_dangerous or h2s > h2s_dangerous:
        gas_label = "Dangerous"
    elif so2 > so2_moderate or h2s > h2s_moderate:
        gas_label = "Moderate"
    else:
        gas_label = "Normal"
    
    # Calculate CHI
    so2_norm = so2 / so2_critical if so2_critical > 0 else 0
    h2s_norm = h2s / h2s_critical if h2s_critical > 0 else 0
    
    # Exposure duration factor (simplified - would need cumulative tracking in full implementation)
    exposure_factor = 0.0  # Placeholder for cumulative exposure tracking
    
    chi_value = calculate_chi(so2_norm, h2s_norm, exposure_factor)
    chi_label = classify_by_chi(chi_value)
    
    # Combine gas and CHI classifications (worst-case)
    if gas_label == "Critical" or chi_label == "Critical":
        return "Critical"
    if gas_label == "Dangerous" or chi_label == "Dangerous":
        return "Dangerous"
    if gas_label == "Moderate" or chi_label == "Moderate":
        return "Moderate"
    return "Normal"


# ============================================================================
# LEGACY FUNCTIONS (kept for backward compatibility)
# ============================================================================

def _threshold_label(value: float, thresholds: dict[str, float]) -> str:
    """Return the hazard label for a single gas measurement."""
    if value < thresholds["normal"]:
        return "Normal"
    if value <= thresholds["moderate"]:
        return "Moderate"
    if value <= thresholds["dangerous"]:
        return "Dangerous"
    return "Critical"


def _validate_df_for_labeling(df: pd.DataFrame) -> None:
    required_cols = {"SO2", "H2S"}
    missing = required_cols - set(df.columns)
    if missing:
        raise KeyError(f"Missing required columns: {sorted(missing)}")


def _get_standard_thresholds(scheme: str) -> dict[str, dict[str, float]]:
    scheme_key = scheme.strip().upper()
    if scheme_key not in STANDARD_THRESHOLDS:
        raise ValueError(f"Unknown threshold scheme '{scheme}'. Use one of: {sorted(STANDARD_THRESHOLDS)}")
    return STANDARD_THRESHOLDS[scheme_key]


def label_hazard_level(
    row: pd.Series,
    scheme: str = "NODE",
    node_col: str = "node_id",
) -> str:
    """Assign a hazard category based on a threshold scheme."""
    so2 = float(row["SO2"])
    h2s = float(row["H2S"])

    scheme_key = scheme.strip().upper()
    if scheme_key == "NODE":
        if node_col not in row.index:
            raise KeyError(f"Required column '{node_col}' not found in row.")
        node_id = int(row[node_col])
        node_thresholds = NODE_THRESHOLDS.get(node_id)
        if node_thresholds is None:
            raise ValueError(f"Unknown node_id: {node_id}")
        so2_thresholds = node_thresholds["SO2"]
        h2s_thresholds = node_thresholds["H2S"]
    else:
        standard_thresholds = _get_standard_thresholds(scheme_key)
        so2_thresholds = standard_thresholds["SO2"]
        h2s_thresholds = standard_thresholds["H2S"]

    so2_label = _threshold_label(so2, so2_thresholds)
    h2s_label = _threshold_label(h2s, h2s_thresholds)

    if "Critical" in (so2_label, h2s_label):
        return "Critical"
    if "Dangerous" in (so2_label, h2s_label):
        return "Dangerous"
    if "Moderate" in (so2_label, h2s_label):
        return "Moderate"
    return "Normal"


def add_hazard_level(
    df: pd.DataFrame,
    scheme: str = "NODE",
    node_col: str = "node_id",
    label_col: str = "hazard_level",
) -> pd.DataFrame:
    """Create a hazard label column using a selected threshold scheme.
    
    Supported schemes:
    - NODE: Node-specific thresholds (legacy)
    - WHO: WHO-based thresholds
    - NIOSH: NIOSH-based thresholds
    - HYBRID: Hybrid Threshold Framework (recommended for Kawah Putih)
    - DATA_DRIVEN: Statistical percentile-based thresholds
    
    Args:
        df: DataFrame containing sensor data
        scheme: Threshold scheme to use
        node_col: Column name for node ID
        label_col: Column name for the output hazard labels
        
    Returns:
        DataFrame with added hazard level column
    """
    df = df.copy()
    _validate_df_for_labeling(df)

    scheme_upper = scheme.strip().upper()
    
    if scheme_upper == "DATA_DRIVEN":
        return label_data_driven_hazard_levels(df, label_col=label_col)
    
    if scheme_upper == "HYBRID":
        # Ensure required columns for hybrid framework
        required_cols = {"SO2", "H2S", node_col, "timestamp", "Temp_C", "Humidity_pct", "Wind_kph"}
        missing = required_cols - set(df.columns)
        if missing:
            raise KeyError(f"Missing required columns for HYBRID scheme: {sorted(missing)}")
        
        # Add hour column if not present (needed for night-time modifier)
        if "hour" not in df.columns:
            df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour
        
        # Add elevation column if not present (needed for altitude modifier)
        if "elevation_m" not in df.columns:
            # Use default elevation from config if not in data
            df["elevation_m"] = df[node_col].map({1: 2201.98, 2: 2192.38})
        
        df[label_col] = df.apply(
            lambda row: label_hazard_hybrid(row, node_col=node_col), axis=1
        )
        return df

    if scheme_upper != "NODE" and node_col not in df.columns:
        # node_col is optional for WHO/NIOSH, but validate if the user requested NODE labeling.
        pass

    df[label_col] = df.apply(
        lambda row: label_hazard_level(row, scheme=scheme, node_col=node_col), axis=1
    )
    return df


def label_data_driven_hazard_levels(
    df: pd.DataFrame,
    method: str = "quantile",
    label_col: str = "hazard_level_data",
) -> pd.DataFrame:
    """Create data-driven hazard levels from the observed SO2 and H2S distributions."""
    df = df.copy()
    _validate_df_for_labeling(df)

    if method != "quantile":
        raise ValueError("Only 'quantile' method is supported for data-driven hazard levels.")

    severity_score = df[["SO2", "H2S"]].max(axis=1)
    thresholds = severity_score.quantile([0.60, 0.80, 0.95]).tolist()
    boundary_labels = {
        "normal": thresholds[0],
        "moderate": thresholds[1],
        "dangerous": thresholds[2],
    }

    def _label_from_score(value: float) -> str:
        if value < boundary_labels["normal"]:
            return "Normal"
        if value < boundary_labels["moderate"]:
            return "Moderate"
        if value < boundary_labels["dangerous"]:
            return "Dangerous"
        return "Critical"

    df[label_col] = severity_score.apply(_label_from_score)
    df[f"{label_col}_score"] = severity_score
    return df


def combine_hazard_schemes(
    df: pd.DataFrame,
    source_cols: list[str],
    combined_col: str = "hazard_level_hybrid",
    strategy: str = "worst",
) -> pd.DataFrame:
    """Combine multiple hazard label columns into a hybrid classification."""
    df = df.copy()
    if isinstance(source_cols, str):
        source_cols = [source_cols]

    missing = [col for col in source_cols if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required source label columns: {missing}")

    if strategy != "worst":
        raise ValueError("Only 'worst' strategy is currently supported for hybrid hazard levels.")

    def _worst_label(row: pd.Series) -> str:
        severity = max(LABEL_ENCODINGS[row[col]] for col in source_cols)
        return HAZARD_LABELS[severity]

    df[combined_col] = df.apply(_worst_label, axis=1)
    return df


def encode_hazard_labels(df: pd.DataFrame, label_col: str = "hazard_level") -> pd.DataFrame:
    """Encode hazard categories numerically."""
    df = df.copy()
    if label_col not in df.columns:
        raise KeyError(f"Required column '{label_col}' not found in DataFrame.")

    df["hazard_level_encoded"] = df[label_col].map(LABEL_ENCODINGS)
    if df["hazard_level_encoded"].isna().any():
        invalid = df.loc[df["hazard_level_encoded"].isna(), label_col].unique().tolist()
        raise ValueError(f"Found invalid hazard labels: {invalid}")
    return df


def display_class_distribution(df: pd.DataFrame, label_col: str = "hazard_level") -> pd.DataFrame:
    """Return a distribution summary table for hazard labels."""
    if label_col not in df.columns:
        raise KeyError(f"Required column '{label_col}' not found in DataFrame.")

    distribution = df[label_col].value_counts(dropna=False).rename_axis(label_col).reset_index(name="count")
    distribution["percentage"] = (distribution["count"] / len(df) * 100).round(2)
    print(f"Distribution for '{label_col}':")
    print(distribution)
    return distribution


def plot_hazard_categories(
    df: pd.DataFrame,
    label_col: str = "hazard_level",
    node_col: str = "node_id",
    output_path: str | None = None,
) -> None:
    """Visualize hazard category counts overall and by node."""
    if label_col not in df.columns or node_col not in df.columns:
        raise KeyError(f"Required columns '{label_col}' or '{node_col}' not found in DataFrame.")

    plt.figure(figsize=(12, 5))
    subplot = plt.subplot(1, 2, 1)
    sns.countplot(data=df, x=label_col, order=HAZARD_LABELS, palette="Set2")
    subplot.set_title("Overall Hazard Categories")
    subplot.set_xlabel("Hazard Level")
    subplot.set_ylabel("Count")

    subplot = plt.subplot(1, 2, 2)
    sns.countplot(data=df, x=label_col, hue=node_col, order=HAZARD_LABELS, palette="Set1")
    subplot.set_title("Hazard Categories by Node")
    subplot.set_xlabel("Hazard Level")
    subplot.set_ylabel("Count")
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path)
        plt.close()
    else:
        plt.show()


def plot_hazard_comparison(
    df: pd.DataFrame,
    label_columns: list[str],
    output_path: str | None = None,
) -> None:
    """Plot comparative label counts across multiple hazard schemes."""
    missing = [col for col in label_columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required label columns: {missing}")

    comparison_df = df[label_columns].melt(value_vars=label_columns, var_name="scheme", value_name="hazard_level")
    plt.figure(figsize=(12, 6))
    sns.countplot(data=comparison_df, x="hazard_level", hue="scheme", order=HAZARD_LABELS, palette="Set2")
    plt.title("Hazard Label Comparison Across Schemes")
    plt.xlabel("Hazard Level")
    plt.ylabel("Count")
    plt.legend(title="Scheme")
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path)
        plt.close()
    else:
        plt.show()


def save_labeled_dataset(df: pd.DataFrame, output_path: str) -> None:
    """Save the labeled dataset to CSV."""
    df.to_csv(output_path, index=False)


if __name__ == "__main__":
    print("Use hazard labeling functions from the package.")
