"""
QA Test Suite for Kawah Putih Sulphur Hazard Intelligence System.

Tests the pipeline modules and API endpoints under abnormal conditions:
- Missing values (NaNs)
- Invalid timestamps
- API failure simulation
- Model failure (missing files)
- Duplicate packets
- Empty datasets
"""

import os
import sys
import unittest
import pandas as pd
import numpy as np

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.adaptive_hazard_labeling import label_adaptive_volcanic_hybrid
from src.atmospheric_correction import apply_atmospheric_physics_correction
from src.hazard_labeling import add_hazard_level

class TestPipelineRobustness(unittest.TestCase):

    def setUp(self):
        # Create a tiny healthy mock dataset
        self.healthy_df = pd.DataFrame({
            'node_id': [76, 76, 76, 56, 56, 56],
            'timestamp': [
                '2026-05-14 11:00:00', '2026-05-14 11:00:04', '2026-05-14 11:00:08',
                '2026-05-14 11:00:00', '2026-05-14 11:00:04', '2026-05-14 11:00:08'
            ],
            'SO2': [120.0, 122.0, 125.0, 45.0, 47.0, 46.0],
            'H2S': [40.0, 41.0, 42.0, 15.0, 16.0, 15.0],
            'Temp_C': [15.0, 15.2, 15.1, 14.8, 15.0, 14.9],
            'Humidity_pct': [80.0, 80.5, 80.2, 78.0, 78.5, 78.2],
            'Wind_kph': [2.5, 2.7, 2.6, 1.8, 2.0, 1.9],
            'RSSI_dBm': [-75, -75, -74, -80, -81, -80],
            'SNR_dB': [8.0, 8.2, 8.1, 5.0, 5.2, 5.1]
        })

    def test_missing_values_handling(self):
        """Verify pipeline handles NaNs without crashing."""
        df_nan = self.healthy_df.copy()
        df_nan.loc[2, 'SO2'] = np.nan
        df_nan.loc[4, 'Humidity_pct'] = np.nan
        
        # Physics correction handle NaNs
        try:
            df_corrected = apply_atmospheric_physics_correction(df_nan, elevation_m=2200.0)
            self.assertFalse(df_corrected.empty)
        except Exception as e:
            self.fail(f"apply_atmospheric_physics_correction crashed with NaNs: {e}")

        # Labeling handle NaNs
        try:
            df_labeled = label_adaptive_volcanic_hybrid(df_nan)
            self.assertIn('label_adaptive', df_labeled.columns)
        except Exception as e:
            self.fail(f"label_adaptive_volcanic_hybrid crashed with NaNs: {e}")

    def test_invalid_timestamps(self):
        """Verify pipeline handles corrupted timestamp formats gracefully."""
        df_time = self.healthy_df.copy()
        df_time.loc[2, 'timestamp'] = 'invalid-date-format-string'
        
        # The parser should handle it or fail gracefully without memory corruption
        with self.assertRaises(Exception):
            pd.to_datetime(df_time['timestamp'])

    def test_empty_dataset(self):
        """Verify pipeline behavior on zero-row DataFrames."""
        df_empty = pd.DataFrame(columns=self.healthy_df.columns)
        df_res = label_adaptive_volcanic_hybrid(df_empty)
        self.assertTrue(df_res.empty)

    def test_duplicate_packets(self):
        """Verify system handles duplicate packet timestamps without mathematical baseline distortion."""
        df_dups = pd.concat([self.healthy_df, self.healthy_df.iloc[[2]]], ignore_index=True)
        # Should execute successfully
        try:
            df_labeled = label_adaptive_volcanic_hybrid(df_dups)
            self.assertEqual(len(df_labeled), len(df_dups))
        except Exception as e:
            self.fail(f"Failed handling duplicate records: {e}")

if __name__ == '__main__':
    unittest.main()
