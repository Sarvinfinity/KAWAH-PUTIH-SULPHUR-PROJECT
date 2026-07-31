"""
Adaptive Volcanic Hybrid Hazard Labeling Framework (Scenario E)

This module replaces absolute industrial hygiene limits (WHO, NIOSH) with an
adaptive, statistically-grounded framework tailored to the specific local
baselines of active volcanic craters.

Key Concepts:
1. Rolling Baselines: Uses Exponential Moving Average over a 2-hour window.
2. Sigma Deviation: Risk is defined by how many standard deviations the current
   concentration spikes above the localized baseline.
3. Adaptive CHI: The Composite Hazard Index is calculated relative to the local
   acclimatized norm, rather than zero.
"""

import numpy as np
import pandas as pd

# Constants
PERIODS_2H = 1800  # 2 hours at 4-second intervals
EPSILON = 1e-6     # Prevent division by zero

def calculate_rolling_stats(series: pd.Series, window=PERIODS_2H) -> pd.DataFrame:
    """
    Calculate rolling mean (EMA) and rolling standard deviation.
    Using simple rolling mean/std since EMA std is complex in pandas, 
    but we use span=window for the EMA mean.
    """
    # Use exponential moving average for smooth baseline tracking
    ema = series.ewm(span=window, adjust=False).mean()
    # Use rolling window for standard deviation to capture local variance
    roll_std = series.rolling(window=window, min_periods=1).std()
    
    # Forward fill NaNs created by rolling std at index 0
    roll_std = roll_std.bfill()
    
    return pd.DataFrame({'mean': ema, 'std': roll_std})


def calculate_meteorological_penalty(row: pd.Series) -> float:
    """
    Calculates a risk penalty multiplier based on atmospheric stagnation.
    Uses inverse dispersion approximation:
    P = (v0 / (v + eps)) * (T_base / (T + eps))
    """
    wind = row.get('Wind_kph', 2.0)
    temp = row.get('Temp_C', 15.0)
    
    # Inverse wind dispersion (stagnant wind = higher penalty)
    wind_penalty = 2.0 / (wind + EPSILON)
    wind_penalty = min(2.0, max(0.5, wind_penalty))
    
    # Temperature inversion (colder = higher penalty due to capping)
    # Use max(temp, 0.1) to prevent negative/zero values from creating invalid penalties
    safe_temp = max(temp, 0.1)
    temp_penalty = 15.0 / safe_temp
    temp_penalty = min(1.5, max(0.5, temp_penalty))
    
    return min(2.5, wind_penalty * temp_penalty)


def label_adaptive_volcanic_hybrid(df: pd.DataFrame, window=PERIODS_2H) -> pd.DataFrame:
    """
    Applies the Adaptive Volcanic Hybrid Framework.
    Generates 'label_adaptive' and 'CHI_adaptive'.
    """
    df = df.copy()
    
    df['label_adaptive'] = 'Normal'
    df['CHI_adaptive'] = 0.0
    
    # Process each node independently to establish local baselines
    for node_id in df['node_id'].unique():
        node_mask = df['node_id'] == node_id
        node_df = df.loc[node_mask].copy()
        
        # 1. Calculate baselines
        so2_stats = calculate_rolling_stats(node_df['SO2'], window)
        h2s_stats = calculate_rolling_stats(node_df['H2S'], window)
        
        # We enforce a minimum standard deviation floor to prevent tiny 
        # variances in calm periods from triggering massive sigma spikes.
        # Volcanic baseline variance is typically at least 10% of the mean.
        so2_std = np.maximum(so2_stats['std'], so2_stats['mean'] * 0.1 + EPSILON)
        h2s_std = np.maximum(h2s_stats['std'], h2s_stats['mean'] * 0.1 + EPSILON)
        
        # 2. Calculate Deviation (Sigma score)
        so2_z = (node_df['SO2'] - so2_stats['mean']) / so2_std
        h2s_z = (node_df['H2S'] - h2s_stats['mean']) / h2s_std
        
        # Prevent negative Z-scores from reducing hazard (we only care about spikes)
        so2_z = np.maximum(0, so2_z)
        h2s_z = np.maximum(0, h2s_z)
        
        # 3. Adaptive Weighted CHI Calculation
        # Weighted inversely by NIOSH STEL (SO2: 5ppm, H2S: 15ppm)
        w_so2 = 1.0 / 5.0
        w_h2s = 1.0 / 15.0
        
        # Normalize weights so they sum to 1.0 roughly, or just use raw ratio
        # Ratio is 3:1 (SO2 is 3x more toxic at equal ppm)
        chi_adaptive = np.sqrt((w_so2 * so2_z)**2 + (w_h2s * h2s_z)**2)
        
        # 4. Meteorological Stagnation Penalty
        # Applies a penalty factor to the Z-scores if the air is stagnant
        meteo_penalties = node_df.apply(calculate_meteorological_penalty, axis=1).values
        so2_z = so2_z * meteo_penalties
        h2s_z = h2s_z * meteo_penalties
        chi_adaptive = chi_adaptive * meteo_penalties
        
        # 5. Classify based on Sigma boundaries
        # Normal:   < 1.5 sigma
        # Moderate: >= 1.5 sigma
        # Dangerous:>= 2.5 sigma
        # Critical: >= 3.5 sigma AND Adaptive CHI > 4.5
        
        labels = np.full(len(node_df), 'Normal', dtype=object)
        
        # Using max Z-score of either gas for individual limits
        max_z = np.maximum(so2_z, h2s_z)
        
        labels[max_z >= 1.5] = 'Moderate'
        labels[max_z >= 2.5] = 'Dangerous'
        labels[(max_z >= 3.5) & (chi_adaptive >= 4.5)] = 'Critical'
        
        df.loc[node_mask, 'label_adaptive'] = labels
        df.loc[node_mask, 'CHI_adaptive'] = chi_adaptive
        df.loc[node_mask, 'Baseline_SO2'] = so2_stats['mean'].values
        df.loc[node_mask, 'Baseline_H2S'] = h2s_stats['mean'].values
        df.loc[node_mask, 'Sigma_SO2'] = so2_z.values
        df.loc[node_mask, 'Sigma_H2S'] = h2s_z.values
        
    return df
