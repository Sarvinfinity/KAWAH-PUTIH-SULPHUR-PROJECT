"""
Regenerate expanded_24H_all_data.csv as fully synthetic (no real 7H rows in output).
- Drops Wind_kph
- Adds location and elevation per node
- Remaps node_id 76 -> 1, 56 -> 2
"""
import datetime

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler

from expand_dataset import MultivariateLSTM, create_dataset, get_time_features

TARGET_COLS = ['SO2', 'H2S', 'Temp_C', 'Humidity_pct', 'RSSI_dBm', 'SNR_dB']

NODE_META = {
    76: {
        'new_id': 1,
        'location': '7°10\'00.64"S 107°24\'04.92"E',
        'elevation': 2201.98,
    },
    56: {
        'new_id': 2,
        'location': '7°09\'59.92"S 107°24\'13.14"E',
        'elevation': 2192.38,
    },
}


def apply_domain_adjustments(predicted_raw, timestamps):
    for i in range(len(predicted_raw)):
        dt = timestamps[i]
        hour = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
        night_factor = max(0, np.cos((hour - 2) * np.pi / 12))
        predicted_raw[i, 0] = predicted_raw[i, 0] * (1.0 + 1.5 * night_factor) + (50 * night_factor)
        predicted_raw[i, 1] = predicted_raw[i, 1] * (1.0 + 1.2 * night_factor) + (20 * night_factor)
        noise_factor = np.random.normal(0, 0.08, size=predicted_raw.shape[1])
        predicted_raw[i] = predicted_raw[i] * (1.0 + noise_factor)
        predicted_raw[i, :4] = np.maximum(predicted_raw[i, :4], 0.0)
    return predicted_raw


def process_node_full_synthetic(df_node, node_id, target_end_time, time_step=30):
    print(f"\n--- Full synthetic generation for node {node_id} ---")
    timestamps = df_node['timestamp'].values
    raw_data = df_node[TARGET_COLS].values

    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(raw_data)
    time_features = np.array([get_time_features(pd.to_datetime(t)) for t in timestamps])
    full_features = np.hstack((scaled_data, time_features))

    X, y = create_dataset(full_features, time_step)
    y = y[:, : len(TARGET_COLS)]
    X_tensor = torch.tensor(X, dtype=torch.float32)
    y_tensor = torch.tensor(y, dtype=torch.float32)

    input_size = len(TARGET_COLS) + 2
    model = MultivariateLSTM(
        input_size=input_size,
        hidden_size=64,
        num_layers=2,
        output_size=len(TARGET_COLS),
    )
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005)

    epochs = 100
    print(f"Training LSTM on {len(X_tensor)} samples (real 7H used only for training)...")
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        outputs = model(X_tensor)
        loss = criterion(outputs, y_tensor)
        loss.backward()
        optimizer.step()
        if (epoch + 1) % 25 == 0:
            print(f"  Epoch [{epoch + 1}/{epochs}], Loss: {loss.item():.6f}")

    model.eval()
    node_start = pd.to_datetime(df_node['timestamp'].min())
    output_timestamps = pd.date_range(start=node_start, end=target_end_time, freq='4s')
    n_out = len(output_timestamps)

    # Fully autoregressive 24h output (real 7H only seeds the initial LSTM window)
    generated_scaled = []
    current_window = full_features[:time_step].copy()

    for i in range(n_out):
        x_input = current_window.reshape((1, time_step, input_size))
        with torch.no_grad():
            yhat = model(torch.tensor(x_input, dtype=torch.float32)).numpy()[0]
        generated_scaled.append(yhat)
        ts = output_timestamps[i]
        next_time_features = get_time_features(ts.to_pydatetime() if hasattr(ts, 'to_pydatetime') else ts)
        current_window = np.vstack((current_window[1:], np.hstack((yhat, next_time_features))))

    predicted_raw = scaler.inverse_transform(np.array(generated_scaled))
    predicted_raw = apply_domain_adjustments(predicted_raw, list(output_timestamps))
    out_timestamps = list(output_timestamps)

    df_out = pd.DataFrame(predicted_raw, columns=TARGET_COLS)
    df_out['timestamp'] = out_timestamps
    meta = NODE_META[node_id]
    df_out['node_id'] = meta['new_id']
    df_out['location'] = meta['location']
    df_out['elevation'] = meta['elevation']
    df_out['ack_success'] = True

    time_feats = np.array([get_time_features(t) for t in df_out['timestamp']])
    df_out['hour_sin'] = time_feats[:, 0]
    df_out['hour_cos'] = time_feats[:, 1]

    print(f"  Generated {len(df_out)} synthetic rows for node {meta['new_id']}")
    return df_out


def main():
    print("Loading real 7H training data from 'all_data_ts.csv'...")
    df_original = pd.read_csv('all_data_ts.csv')
    df_original['timestamp'] = pd.to_datetime(df_original['timestamp'])
    df_original.sort_values('timestamp', inplace=True)

    t0 = df_original['timestamp'].min()
    target_end_time = t0 + pd.Timedelta(hours=24)

    all_dfs = []
    for node_id in df_original['node_id'].unique():
        df_node = df_original[df_original['node_id'] == node_id].copy()
        df_node.sort_values('timestamp', inplace=True)
        all_dfs.append(process_node_full_synthetic(df_node, node_id, target_end_time))

    df_final = pd.concat(all_dfs, ignore_index=True)
    df_final.sort_values('timestamp', inplace=True)
    df_final.reset_index(drop=True, inplace=True)

    col_order = [
        'timestamp',
        'node_id',
        'location',
        'elevation',
        'SO2',
        'H2S',
        'Temp_C',
        'Humidity_pct',
        'RSSI_dBm',
        'SNR_dB',
        'ack_success',
        'hour_sin',
        'hour_cos',
    ]
    df_final = df_final[col_order]

    out_file = 'expanded_24H_all_data.csv'
    df_final.to_csv(out_file, index=False)
    print(f"\nSaved fully synthetic dataset to '{out_file}' (shape: {df_final.shape})")
    print(f"Columns: {list(df_final.columns)}")
    print(f"Node IDs: {sorted(df_final['node_id'].unique())}")


if __name__ == '__main__':
    main()
