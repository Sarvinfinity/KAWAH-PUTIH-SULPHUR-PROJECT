"""Unit tests for the hybrid hazard labeling framework."""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hazard_labeling import (
    calculate_meteorological_modifier,
    calculate_node_modifier,
    calculate_chi,
    classify_by_chi,
    apply_threshold_modifiers,
    label_hazard_hybrid,
    HYBRID_THRESHOLDS,
    CHI_THRESHOLDS,
    METEOROLOGICAL_MODIFIERS,
    NODE_MODIFIERS,
    HAZARD_LABELS,
)


class TestMeteorologicalModifiers:
    """Test meteorological modifier calculations."""
    
    def test_no_modifiers_applied(self):
        """Test that no modifiers are applied when conditions are not met."""
        row = pd.Series({
            "hour": 12,
            "Humidity_pct": 70,
            "Wind_kph": 5.0,
            "Temp_C": 20,
            "elevation_m": 1500,
        })
        modifier = calculate_meteorological_modifier(row)
        assert modifier == 1.0, "No modifiers should be applied"
    
    def test_night_time_modifier(self):
        """Test night-time modifier is applied during night hours."""
        row = pd.Series({
            "hour": 22,  # 10 PM - night time
            "Humidity_pct": 70,
            "Wind_kph": 5.0,
            "Temp_C": 20,
            "elevation_m": 1500,
        })
        modifier = calculate_meteorological_modifier(row)
        assert modifier == 0.7, "Night-time modifier should be 0.7"
    
    def test_high_humidity_modifier(self):
        """Test high humidity modifier is applied."""
        row = pd.Series({
            "hour": 12,
            "Humidity_pct": 90,  # > 85%
            "Wind_kph": 5.0,
            "Temp_C": 20,
            "elevation_m": 1500,
        })
        modifier = calculate_meteorological_modifier(row)
        assert modifier == 0.8, "High humidity modifier should be 0.8"
    
    def test_low_wind_modifier(self):
        """Test low wind modifier is applied."""
        row = pd.Series({
            "hour": 12,
            "Humidity_pct": 70,
            "Wind_kph": 1.0,  # < 1.5 km/h
            "Temp_C": 20,
            "elevation_m": 1500,
        })
        modifier = calculate_meteorological_modifier(row)
        assert modifier == 0.7, "Low wind modifier should be 0.7"
    
    def test_temp_inversion_modifier(self):
        """Test temperature inversion modifier is applied."""
        row = pd.Series({
            "hour": 12,
            "Humidity_pct": 70,
            "Wind_kph": 5.0,
            "Temp_C": 3,  # < 5°C
            "elevation_m": 1500,
        })
        modifier = calculate_meteorological_modifier(row)
        assert modifier == 0.6, "Temperature inversion modifier should be 0.6"
    
    def test_high_altitude_modifier(self):
        """Test high altitude modifier is applied."""
        row = pd.Series({
            "hour": 12,
            "Humidity_pct": 70,
            "Wind_kph": 5.0,
            "Temp_C": 20,
            "elevation_m": 2200,  # > 2000m
        })
        modifier = calculate_meteorological_modifier(row)
        assert modifier == 0.8, "High altitude modifier should be 0.8"
    
    def test_combined_modifiers(self):
        """Test that multiple modifiers are multiplied together."""
        row = pd.Series({
            "hour": 22,  # Night time
            "Humidity_pct": 90,  # High humidity
            "Wind_kph": 1.0,  # Low wind
            "Temp_C": 3,  # Temperature inversion
            "elevation_m": 2200,  # High altitude
        })
        modifier = calculate_meteorological_modifier(row)
        expected = 0.7 * 0.8 * 0.7 * 0.6 * 0.8
        assert abs(modifier - expected) < 0.01, f"Combined modifier should be {expected}"


class TestNodeModifiers:
    """Test node-specific modifier calculations."""
    
    def test_node1_modifier(self):
        """Test Node 1 has 0.9 modifier."""
        modifier = calculate_node_modifier(1)
        assert modifier == 0.9, "Node 1 should have 0.9 modifier"
    
    def test_node2_modifier(self):
        """Test Node 2 has 1.0 modifier."""
        modifier = calculate_node_modifier(2)
        assert modifier == 1.0, "Node 2 should have 1.0 modifier"
    
    def test_unknown_node_modifier(self):
        """Test unknown nodes get 1.0 modifier."""
        modifier = calculate_node_modifier(99)
        assert modifier == 1.0, "Unknown nodes should have 1.0 modifier"


class TestCompositeHazardIndex:
    """Test Composite Hazard Index (CHI) calculations."""
    
    def test_chi_calculation_default_weights(self):
        """Test CHI calculation with default weights."""
        chi = calculate_chi(so2_normalized=0.5, h2s_normalized=0.3, exposure_duration_factor=0.2)
        expected = 0.6 * 0.5 + 0.3 * 0.3 + 0.1 * 0.2
        assert abs(chi - expected) < 0.01, f"CHI should be {expected}"
    
    def test_chi_custom_weights(self):
        """Test CHI calculation with custom weights."""
        custom_weights = {"SO2": 0.5, "H2S": 0.4, "exposure": 0.1}
        chi = calculate_chi(
            so2_normalized=0.5, 
            h2s_normalized=0.3, 
            exposure_duration_factor=0.2,
            weights=custom_weights
        )
        expected = 0.5 * 0.5 + 0.4 * 0.3 + 0.1 * 0.2
        assert abs(chi - expected) < 0.01, f"CHI with custom weights should be {expected}"
    
    def test_chi_exposure_factor_capped(self):
        """Test that exposure factor is capped at 1.0."""
        chi = calculate_chi(so2_normalized=0.5, h2s_normalized=0.3, exposure_duration_factor=2.0)
        expected = 0.6 * 0.5 + 0.3 * 0.3 + 0.1 * 1.0  # exposure capped at 1.0
        assert abs(chi - expected) < 0.01, f"CHI should cap exposure factor at 1.0"
    
    def test_chi_zero_values(self):
        """Test CHI with zero values."""
        chi = calculate_chi(so2_normalized=0.0, h2s_normalized=0.0, exposure_duration_factor=0.0)
        assert chi == 0.0, "CHI should be 0.0 with all zero inputs"


class TestCHIClassification:
    """Test CHI-based hazard classification."""
    
    def test_chi_normal(self):
        """Test CHI classification for Normal."""
        label = classify_by_chi(0.2)
        assert label == "Normal", "CHI 0.2 should be Normal"
    
    def test_chi_moderate(self):
        """Test CHI classification for Moderate."""
        label = classify_by_chi(0.4)
        # 0.4 is in range [0.3, 0.5), so should be Moderate
        assert label == "Moderate", "CHI 0.4 should be Moderate"
    
    def test_chi_dangerous(self):
        """Test CHI classification for Dangerous."""
        label = classify_by_chi(0.65)
        # 0.65 is in range [0.5, 0.8), so should be Dangerous
        assert label == "Dangerous", "CHI 0.65 should be Dangerous"
    
    def test_chi_critical(self):
        """Test CHI classification for Critical."""
        label = classify_by_chi(0.9)
        assert label == "Critical", "CHI 0.9 should be Critical"
    
    def test_chi_boundary_values(self):
        """Test CHI classification at boundary values."""
        assert classify_by_chi(0.29) == "Normal", "CHI 0.29 should be Normal"
        assert classify_by_chi(0.3) == "Moderate", "CHI 0.3 should be Moderate (boundary)"
        assert classify_by_chi(0.49) == "Moderate", "CHI 0.49 should be Moderate"
        assert classify_by_chi(0.5) == "Dangerous", "CHI 0.5 should be Dangerous (boundary)"
        assert classify_by_chi(0.79) == "Dangerous", "CHI 0.79 should be Dangerous"
        assert classify_by_chi(0.8) == "Critical", "CHI 0.8 should be Critical (boundary)"


class TestThresholdModifiers:
    """Test threshold modifier application."""
    
    def test_no_modifiers(self):
        """Test threshold with no modifiers."""
        modified = apply_threshold_modifiers(1.0, 1.0, 1.0)
        assert modified == 1.0, "Threshold should be unchanged with no modifiers"
    
    def test_meteorological_modifier_only(self):
        """Test threshold with only meteorological modifier."""
        modified = apply_threshold_modifiers(1.0, 0.7, 1.0)
        assert modified == 0.7, "Threshold should be reduced by meteorological modifier"
    
    def test_node_modifier_only(self):
        """Test threshold with only node modifier."""
        modified = apply_threshold_modifiers(1.0, 1.0, 0.9)
        assert modified == 0.9, "Threshold should be reduced by node modifier"
    
    def test_combined_modifiers(self):
        """Test threshold with both modifiers."""
        modified = apply_threshold_modifiers(1.0, 0.7, 0.9)
        expected = 0.7 * 0.9
        assert abs(modified - expected) < 0.01, f"Threshold should be {expected}"


class TestHybridLabeling:
    """Test hybrid hazard labeling function."""
    
    def test_normal_conditions(self):
        """Test labeling under normal conditions."""
        row = pd.Series({
            "SO2": 0.02,
            "H2S": 0.01,
            "node_id": 1,
            "timestamp": "2024-01-01 12:00:00",
            "Temp_C": 20,
            "Humidity_pct": 70,
            "Wind_kph": 5.0,
            "hour": 12,
            "elevation_m": 2201.98,
        })
        label = label_hazard_hybrid(row)
        assert label == "Normal", "Low concentrations should be Normal"
    
    def test_critical_so2(self):
        """Test labeling with critical SO2 concentration."""
        row = pd.Series({
            "SO2": 2.0,  # Above critical threshold
            "H2S": 0.01,
            "node_id": 1,
            "timestamp": "2024-01-01 12:00:00",
            "Temp_C": 20,
            "Humidity_pct": 70,
            "Wind_kph": 5.0,
            "hour": 12,
            "elevation_m": 2201.98,
        })
        label = label_hazard_hybrid(row)
        assert label == "Critical", "High SO2 should be Critical"
    
    def test_critical_h2s(self):
        """Test labeling with critical H2S concentration."""
        row = pd.Series({
            "SO2": 0.02,
            "H2S": 1.0,  # Above critical threshold
            "node_id": 1,
            "timestamp": "2024-01-01 12:00:00",
            "Temp_C": 20,
            "Humidity_pct": 70,
            "Wind_kph": 5.0,
            "hour": 12,
            "elevation_m": 2201.98,
        })
        label = label_hazard_hybrid(row)
        assert label == "Critical", "High H2S should be Critical"
    
    def test_moderate_conditions(self):
        """Test labeling with moderate concentrations."""
        row = pd.Series({
            "SO2": 0.15,  # Moderate range (0.05-0.2 with node modifier)
            "H2S": 0.08,
            "node_id": 1,
            "timestamp": "2024-01-01 12:00:00",
            "Temp_C": 20,
            "Humidity_pct": 70,
            "Wind_kph": 5.0,
            "hour": 12,
            "elevation_m": 2201.98,
        })
        label = label_hazard_hybrid(row)
        assert label == "Moderate", "Moderate concentrations should be Moderate"
    
    def test_night_time_modifier_effect(self):
        """Test that night-time conditions reduce thresholds."""
        row_day = pd.Series({
            "SO2": 0.06,
            "H2S": 0.03,
            "node_id": 1,
            "timestamp": "2024-01-01 12:00:00",
            "Temp_C": 20,
            "Humidity_pct": 70,
            "Wind_kph": 5.0,
            "hour": 12,
            "elevation_m": 2201.98,
        })
        row_night = pd.Series({
            "SO2": 0.06,
            "H2S": 0.03,
            "node_id": 1,
            "timestamp": "2024-01-01 22:00:00",
            "Temp_C": 20,
            "Humidity_pct": 70,
            "Wind_kph": 5.0,
            "hour": 22,
            "elevation_m": 2201.98,
        })
        label_day = label_hazard_hybrid(row_day)
        label_night = label_hazard_hybrid(row_night)
        # Night should have lower thresholds, so same concentration may be higher hazard
        assert label_night >= label_day, "Night-time should not have lower hazard than day"


class TestThresholdConstants:
    """Test that threshold constants are properly defined."""
    
    def test_hybrid_thresholds_structure(self):
        """Test that HYBRID_THRESHOLDS has correct structure."""
        assert "SO2" in HYBRID_THRESHOLDS, "HYBRID_THRESHOLDS should contain SO2"
        assert "H2S" in HYBRID_THRESHOLDS, "HYBRID_THRESHOLDS should contain H2S"
        assert "10min_avg" in HYBRID_THRESHOLDS["SO2"], "SO2 should have 10min_avg"
        assert "normal" in HYBRID_THRESHOLDS["SO2"]["10min_avg"], "Should have normal threshold"
        assert "moderate" in HYBRID_THRESHOLDS["SO2"]["10min_avg"], "Should have moderate threshold"
        assert "dangerous" in HYBRID_THRESHOLDS["SO2"]["10min_avg"], "Should have dangerous threshold"
        assert "critical" in HYBRID_THRESHOLDS["SO2"]["10min_avg"], "Should have critical threshold"
    
    def test_chi_thresholds_structure(self):
        """Test that CHI_THRESHOLDS has correct structure."""
        assert "normal" in CHI_THRESHOLDS, "CHI_THRESHOLDS should contain normal"
        assert "moderate" in CHI_THRESHOLDS, "CHI_THRESHOLDS should contain moderate"
        assert "dangerous" in CHI_THRESHOLDS, "CHI_THRESHOLDS should contain dangerous"
        assert "critical" in CHI_THRESHOLDS, "CHI_THRESHOLDS should contain critical"
        assert CHI_THRESHOLDS["normal"] < CHI_THRESHOLDS["moderate"], "Thresholds should be increasing"
        assert CHI_THRESHOLDS["moderate"] < CHI_THRESHOLDS["dangerous"], "Thresholds should be increasing"
        assert CHI_THRESHOLDS["dangerous"] <= CHI_THRESHOLDS["critical"], "Thresholds should be increasing"
    
    def test_node_modifiers_range(self):
        """Test that node modifiers are in valid range."""
        for node_id, modifier in NODE_MODIFIERS.items():
            assert 0.0 < modifier <= 1.0, f"Node modifier for {node_id} should be in (0, 1]"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
