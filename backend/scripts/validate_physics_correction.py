"""
Validation script for the Atmospheric Physics Correction Layer.

This script demonstrates the physical plausibility of the corrections by simulating
various meteorological conditions and plotting their effect on a baseline SO2 concentration.
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR = os.path.dirname(SCRIPTS_DIR)
WORKSPACE_ROOT = os.path.dirname(ML_DIR)
sys.path.append(os.path.join(WORKSPACE_ROOT, "backend"))
from src.atmospheric_correction import apply_atmospheric_physics_correction

OUTPUT_DIR = os.path.join(WORKSPACE_ROOT, 'outputs', 'plots', 'physics_validation')


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def simulate_wind_dispersion():
    """Simulate the effect of varying wind speeds on SO2 concentration."""
    print("Simulating Wind Dispersion...")
    wind_speeds = np.linspace(0, 15, 100)
    
    # Create baseline dataframe (constant SO2, varying wind)
    df = pd.DataFrame({
        'timestamp': pd.date_range(start='2026-07-20 12:00', periods=100, freq='4s'),
        'SO2': np.full(100, 10.0),
        'H2S': np.full(100, 5.0),
        'Temp_C': np.full(100, 15.0),
        'Humidity_pct': np.full(100, 50.0),
        'Wind_kph': wind_speeds
    })
    
    df_corrected = apply_atmospheric_physics_correction(df, elevation_m=2200.0)
    
    plt.figure(figsize=(10, 6))
    plt.plot(df['Wind_kph'], df['SO2'], label='Baseline (10 ppm)', color='grey', linestyle='--')
    plt.plot(df_corrected['Wind_kph'], df_corrected['SO2'], label='Physics-Corrected SO2', color='steelblue', linewidth=2)
    
    plt.title('Effect of Wind Dispersion on SO2 Concentration')
    plt.xlabel('Wind Speed (kph)')
    plt.ylabel('SO2 Concentration (ppm)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'wind_dispersion_effect.png'), dpi=120)
    plt.close()


def simulate_diurnal_inversion():
    """Simulate the effect of temperature inversion over a 24-hour cycle."""
    print("Simulating Diurnal Temperature Inversion...")
    
    timestamps = pd.date_range(start='2026-07-20 00:00', periods=24, freq='1h')
    
    # Synthetic temperature curve (colder at night, warmer in day)
    hours = timestamps.hour.values
    temp_c = 15.0 - 10.0 * np.cos((hours - 2) * np.pi / 12) # min ~5C at 2 AM, max ~25C at 2 PM
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'SO2': np.full(24, 10.0), # Constant emission source
        'H2S': np.full(24, 5.0),
        'Temp_C': temp_c,
        'Humidity_pct': np.full(24, 60.0),
        'Wind_kph': np.full(24, 2.0) # Constant low wind
    })
    
    df_corrected = apply_atmospheric_physics_correction(df, elevation_m=2200.0)
    
    fig, ax1 = plt.subplots(figsize=(12, 6))
    
    color = 'tab:red'
    ax1.set_xlabel('Time of Day')
    ax1.set_ylabel('Temperature (°C)', color=color)
    ax1.plot(df['timestamp'], df['Temp_C'], color=color, linestyle='--', marker='o', label='Temp_C')
    ax1.tick_params(axis='y', labelcolor=color)
    
    ax2 = ax1.twinx()
    color = 'tab:blue'
    ax2.set_ylabel('SO2 Concentration (ppm)', color=color)
    ax2.plot(df_corrected['timestamp'], df_corrected['SO2'], color=color, linewidth=2, label='Physics-Corrected SO2')
    ax2.tick_params(axis='y', labelcolor=color)
    
    # Baseline
    ax2.axhline(y=10.0, color='grey', linestyle=':', label='Baseline Emission (10 ppm)')
    
    plt.title('Diurnal Temperature Inversion Effect on Sulfur Concentration')
    fig.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'diurnal_inversion_effect.png'), dpi=120)
    plt.close()


def main():
    ensure_dir(OUTPUT_DIR)
    print(f"Generating physics validation plots in {OUTPUT_DIR}...")
    
    simulate_wind_dispersion()
    simulate_diurnal_inversion()
    
    print("Validation completed successfully.")


if __name__ == '__main__':
    main()
