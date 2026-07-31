import os

# Path resolution
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.dirname(BACKEND_DIR)

TARGET_COLS = ['SO2', 'H2S', 'Temp_C', 'Humidity_pct', 'RSSI_dBm', 'SNR_dB']

SENSOR_LABELS = {
    'SO2': 'SO2 (ppm)',
    'H2S': 'H2S (ppm)',
    'Temp_C': 'Temperature (°C)',
    'Humidity_pct': 'Humidity (%)',
    'RSSI_dBm': 'RSSI (dBm)',
    'SNR_dB': 'SNR (dB)',
}

NODE_INFO = {
    1: {
        'location': '7°10\'00.64"S 107°24\'04.92"E',
        'elevation': 2201.98,
    },
    2: {
        'location': '7°09\'59.92"S 107°24\'13.14"E',
        'elevation': 2192.38,
    },
}

INTERVAL_SEC = 4
STEPS_PER_HOUR = 3600 // INTERVAL_SEC  # 900

DATA_FILE = os.path.join(WORKSPACE_ROOT, 'data', 'processed', 'expanded_24H_all_data.csv')
TRAIN_FILE = os.path.join(WORKSPACE_ROOT, 'data', 'raw', 'all_data_ts.csv')

VIZ_DIR = os.path.join(WORKSPACE_ROOT, 'outputs', 'plots')
FORECAST_DIR = os.path.join(WORKSPACE_ROOT, 'outputs', 'predictions')
