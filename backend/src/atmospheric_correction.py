"""
Physics-based atmospheric correction layer for sulphur gas concentrations.

This module replaces hardcoded multipliers with a deterministic, physically-grounded
post-processing layer that adjusts raw ML predictions (SO2, H2S) based on
local meteorological parameters: Wind, Humidity, Temperature, Pressure, and Time.
"""

import numpy as np
import pandas as pd
from typing import Tuple

# Standard physical constants
P0 = 1013.25  # Standard sea level pressure (hPa)
L = 0.0065    # Temperature lapse rate (K/m)
T0 = 288.15   # Standard sea level temperature (K)
G = 9.80665   # Gravitational acceleration (m/s^2)
M = 0.02896   # Molar mass of Earth's air (kg/mol)
R = 8.31446   # Universal gas constant (J/(mol·K))


def calculate_barometric_pressure(elevation_m: float, temp_c: float) -> float:
    """
    Calculate atmospheric pressure (hPa) based on elevation and temperature
    using the standard barometric formula.
    
    P = P0 * [1 - (L * h) / (T0 + Temp_C)] ^ (g * M / (R * L))
    """
    temp_k = temp_c + 273.15
    # Simplified barometric formula for constant temperature in the local stratum
    exponent = (G * M) / (R * L)
    # Ensure denominator is positive
    base = max(1e-5, 1 - (L * elevation_m) / T0)
    pressure = P0 * (base ** exponent)
    
    # Temperature correction (ideal gas law density adjustment ratio)
    # Density is proportional to P / T
    # We return the pressure, but later we use P/T for density scaling.
    return pressure


def apply_atmospheric_physics_correction(
    df: pd.DataFrame, 
    elevation_m: float,
    so2_col: str = 'SO2',
    h2s_col: str = 'H2S'
) -> pd.DataFrame:
    """
    Applies physics-based corrections to SO2 and H2S concentrations.
    
    The corrections are applied gradually over the series using:
    1. Wind Dispersion (Gaussian plume inverse velocity scaling)
    2. Humidity Scavenging (Wet deposition/scrubbing)
    3. Temperature & Time Inversion (Boundary layer capping)
    4. Pressure/Density scaling
    5. Temporal persistence (Exposure duration)
    """
    df = df.copy()
    
    # Extract arrays for vectorized operations
    so2_raw = df[so2_col].values.copy()
    h2s_raw = df[h2s_col].values.copy()
    
    # Handle missing Wind_kph in legacy datasets
    if 'Wind_kph' not in df.columns:
        df['Wind_kph'] = 2.0
        
    wind = df['Wind_kph'].values
    humidity = df['Humidity_pct'].values
    temp = df['Temp_C'].values
    timestamps = pd.to_datetime(df['timestamp'])
    
    # 1. Barometric Pressure & Density Scaling
    # Gases expand at higher altitudes (lower pressure). 
    # Measured ppm might read differently depending on the sensor's calibration altitude.
    # We apply a slight density correction factor relative to standard conditions.
    pressures = np.array([calculate_barometric_pressure(elevation_m, t) for t in temp])
    # Density ratio = (P / P0) * (T0 / (Temp_C + 273.15))
    density_ratio = (pressures / P0) * (T0 / (temp + 273.15))
    
    # 2. Wind Dispersion (v0 / (v0 + v))
    # v0 represents the calm wind baseline where mixing is minimal
    v0 = 2.0 
    wind_factor = v0 / (v0 + wind)
    # Prevent complete zeroing out during high winds; floor it at 0.3
    wind_factor = np.clip(wind_factor, 0.3, 1.0)
    
    # 3. Humidity Scavenging (Condensation and dissolution)
    # SO2 and H2S dissolve in water droplets. High humidity reduces airborne gas.
    # k is the scavenging coefficient (e.g., 0.15 means 15% reduction at 100% humidity)
    k_so2 = 0.15
    k_h2s = 0.10
    humidity_factor_so2 = 1.0 - (k_so2 * (humidity / 100.0))
    humidity_factor_h2s = 1.0 - (k_h2s * (humidity / 100.0))
    
    # 4. Temperature & Time Inversion (Boundary Layer)
    # At night, temperature drops and boundary layer lowers, trapping gases.
    hours = timestamps.dt.hour + timestamps.dt.minute / 60.0 + timestamps.dt.second / 3600.0
    
    # Nighttime envelope: peaks at 2 AM (hour 2), lowest at 2 PM (hour 14)
    diurnal_curve = np.cos((hours.values - 2) * np.pi / 12)
    night_envelope = np.maximum(0, diurnal_curve)
    
    # Temperature inversion strength: stronger if temperature is low
    # Base temp for Kawah Putih is ~15C. If temp drops below 15, inversion strengthens.
    temp_inversion_strength = np.clip((15.0 - temp) / 10.0, 0.0, 1.0)
    
    # Combined inversion multiplier (max ~1.8x at cold night, 1.0x at warm day)
    inversion_multiplier = 1.0 + (0.8 * night_envelope * temp_inversion_strength)
    
    # 5. Temporal Persistence (Exposure duration smoothing)
    # Plume dynamics mean concentrations don't change instantaneously.
    # We apply a rolling exponential moving average to simulate physical inertia.
    # Alpha determines the persistence (lower alpha = higher persistence).
    # Since timestep is 4 seconds, alpha=0.1 means ~40s half-life.
    alpha = 0.1
    
    # --- Apply Corrections ---
    
    # Calculate the targeted physics-adjusted values
    so2_target = so2_raw * density_ratio * wind_factor * humidity_factor_so2 * inversion_multiplier
    h2s_target = h2s_raw * density_ratio * wind_factor * humidity_factor_h2s * inversion_multiplier
    
    # Apply exponential smoothing for temporal persistence
    so2_smoothed = np.zeros_like(so2_target)
    h2s_smoothed = np.zeros_like(h2s_target)
    
    so2_smoothed[0] = so2_target[0]
    h2s_smoothed[0] = h2s_target[0]
    
    for i in range(1, len(so2_target)):
        so2_smoothed[i] = alpha * so2_target[i] + (1 - alpha) * so2_smoothed[i-1]
        h2s_smoothed[i] = alpha * h2s_target[i] + (1 - alpha) * h2s_smoothed[i-1]
        
    # Add minor natural variance back in (turbulence) - fixed seed for reproducibility
    rng = np.random.default_rng(seed=42)
    noise_so2 = rng.normal(0, 0.02, size=len(so2_smoothed))
    noise_h2s = rng.normal(0, 0.02, size=len(h2s_smoothed))
    
    so2_final = so2_smoothed * (1.0 + noise_so2)
    h2s_final = h2s_smoothed * (1.0 + noise_h2s)
    
    # Ensure no negative concentrations
    df[so2_col] = np.maximum(0.0, so2_final)
    df[h2s_col] = np.maximum(0.0, h2s_final)
    
    # Track the calculated pressure and inversion multiplier for explainability
    df['calculated_pressure_hPa'] = pressures
    df['inversion_multiplier'] = inversion_multiplier
    
    return df
