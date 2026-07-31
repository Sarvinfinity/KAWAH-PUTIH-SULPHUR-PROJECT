"""
LSTM forecasting for 1-hour and 24-hour prediction windows.
- 1h: train on all but last 1h of synthetic 24H data, forecast 1h, compare to holdout
- 24h: train on real 7H (all_data_ts.csv), forecast 24h, compare to synthetic reference
"""
import datetime
import json
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import MinMaxScaler

from config import (
    DATA_FILE,
    FORECAST_DIR,
    INTERVAL_SEC,
    NODE_INFO,
    SENSOR_LABELS,
    STEPS_PER_HOUR,
    TARGET_COLS,
    TRAIN_FILE,
    VIZ_DIR,
)
from expand_dataset import MultivariateLSTM, create_dataset, get_time_features
from src.atmospheric_correction import apply_atmospheric_physics_correction

FORECAST_VIZ_DIR = os.path.join(VIZ_DIR, 'forecasts')


def build_feature_matrix(timestamps, values):
    time_features = np.array([get_time_features(pd.to_datetime(t)) for t in timestamps])
    return np.hstack((values, time_features))


def train_lstm(X_tensor, y_tensor, input_size, output_size, epochs=80):
    model = MultivariateLSTM(
        input_size=input_size,
        hidden_size=64,
        num_layers=2,
        output_size=output_size,
    )
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005)

    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        loss = criterion(model(X_tensor), y_tensor)
        loss.backward()
        optimizer.step()
        if (epoch + 1) % 20 == 0:
            print(f'    Epoch {epoch + 1}/{epochs}, loss={loss.item():.6f}')
    return model


def autoregressive_forecast(model, scaler, seed_window, start_timestamp, n_steps, time_step):
    """Generate n_steps predictions from a scaled seed window."""
    input_size = seed_window.shape[1]
    current_window = seed_window.copy()
    last_ts = pd.to_datetime(start_timestamp)
    predictions_scaled = []

    model.eval()
    for _ in range(n_steps):
        x_input = current_window.reshape(1, time_step, input_size)
        with torch.no_grad():
            yhat = model(torch.tensor(x_input, dtype=torch.float32)).numpy()[0]
        predictions_scaled.append(yhat)
        last_ts = last_ts + datetime.timedelta(seconds=INTERVAL_SEC)
        time_feat = get_time_features(last_ts)
        current_window = np.vstack((current_window[1:], np.hstack((yhat, time_feat))))

    return scaler.inverse_transform(np.array(predictions_scaled))


def compute_metrics(actual, predicted):
    metrics = {}
    for i, col in enumerate(TARGET_COLS):
        a, p = actual[:, i], predicted[:, i]
        metrics[col] = {
            'MAE': float(mean_absolute_error(a, p)),
            'RMSE': float(np.sqrt(mean_squared_error(a, p))),
            'R2': float(r2_score(a, p)),
        }
    metrics['overall'] = {
        'MAE': float(mean_absolute_error(actual, predicted)),
        'RMSE': float(np.sqrt(mean_squared_error(actual, predicted))),
    }
    return metrics


def plot_forecast(actual_df, forecast_df, node_id, horizon_label, feature):
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(actual_df['timestamp'], actual_df[feature], label='Actual', color='steelblue', linewidth=1.2)
    ax.plot(forecast_df['timestamp'], forecast_df[feature], label='Forecast', color='darkorange', linewidth=1.2, alpha=0.9)
    info = NODE_INFO[node_id]
    ax.set_title(
        f'{horizon_label} Forecast — Node {node_id} — {SENSOR_LABELS[feature]}\n'
        f'{info["location"]} | {info["elevation"]:.2f} m'
    )
    ax.set_xlabel('Timestamp')
    ax.set_ylabel(SENSOR_LABELS[feature])
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    safe_horizon = horizon_label.replace(' ', '_').lower()
    fname = os.path.join(FORECAST_VIZ_DIR, f'{safe_horizon}_node{node_id}_{feature.lower()}.png')
    plt.savefig(fname, dpi=120, bbox_inches='tight')
    plt.close()


def plot_forecast_dashboard(actual_df, forecast_df, node_id, horizon_label):
    env = ['SO2', 'H2S', 'Temp_C', 'Humidity_pct']
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    fig.suptitle(f'{horizon_label} Forecast Dashboard — Node {node_id}', fontsize=13, fontweight='bold')

    for ax, col in zip(axes.flat, env):
        ax.plot(actual_df['timestamp'], actual_df[col], label='Actual', linewidth=1)
        ax.plot(forecast_df['timestamp'], forecast_df[col], label='Forecast', linewidth=1, alpha=0.85)
        ax.set_ylabel(SENSOR_LABELS[col])
        ax.set_title(SENSOR_LABELS[col])
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    for ax in axes[1, :]:
        ax.set_xlabel('Timestamp')
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    safe_horizon = horizon_label.replace(' ', '_').lower()
    fname = os.path.join(FORECAST_VIZ_DIR, f'{safe_horizon}_dashboard_node{node_id}.png')
    plt.savefig(fname, dpi=120, bbox_inches='tight')
    plt.close()


def forecast_1h_window(df_node, node_id, time_step=30, epochs=60):
    """
    1-hour forecast: train on first 23h, predict last 1h, evaluate vs holdout.
    """
    print(f'\n  [1H] Node {node_id}: train on 23h, forecast 1h')
    df_node = df_node.sort_values('timestamp').reset_index(drop=True)
    n_holdout = STEPS_PER_HOUR
    if len(df_node) <= n_holdout + time_step + 50:
        raise ValueError(f'Node {node_id}: insufficient data for 1h forecast')

    train_df = df_node.iloc[:-n_holdout].copy()
    holdout_df = df_node.iloc[-n_holdout:].copy()

    scaler = MinMaxScaler(feature_range=(0, 1))
    train_scaled = scaler.fit_transform(train_df[TARGET_COLS].values)
    full_train = build_feature_matrix(train_df['timestamp'].values, train_scaled)

    X, y = create_dataset(full_train, time_step)
    y = y[:, : len(TARGET_COLS)]
    X_tensor = torch.tensor(X, dtype=torch.float32)
    y_tensor = torch.tensor(y, dtype=torch.float32)

    input_size = len(TARGET_COLS) + 2
    model = train_lstm(X_tensor, y_tensor, input_size, len(TARGET_COLS), epochs=epochs)

    seed_window = full_train[-time_step:]
    start_ts = train_df['timestamp'].iloc[-1]
    predicted = autoregressive_forecast(model, scaler, seed_window, start_ts, n_holdout, time_step)

    forecast_df = holdout_df[['timestamp', 'node_id', 'location', 'elevation']].copy()
    for i, col in enumerate(TARGET_COLS):
        forecast_df[col] = predicted[:, i]
    forecast_df['ack_success'] = True
    
    # Apply atmospheric physics correction
    elevation_m = df_node['elevation'].iloc[0] if 'elevation' in df_node.columns else 2200.0
    forecast_df = apply_atmospheric_physics_correction(forecast_df, elevation_m)

    # Re-extract actual values for metrics comparison AFTER correction
    # Note: metrics should ideally compare to real values, but if holdout is synthetic it will compare to synthetic
    actual_vals = holdout_df[TARGET_COLS].values
    corrected_predicted = forecast_df[TARGET_COLS].values
    metrics = compute_metrics(actual_vals, corrected_predicted)

    return forecast_df, holdout_df, metrics


def forecast_24h_window(df_train_node, df_ref_node, node_id, time_step=30, epochs=80):
    """
    24-hour forecast: train on real 7H data, predict full 24h, compare to synthetic reference.
    """
    print(f'\n  [24H] Node {node_id}: train on 7H real, forecast 24h')
    df_train_node = df_train_node.sort_values('timestamp').reset_index(drop=True)
    df_ref_node = df_ref_node.sort_values('timestamp').reset_index(drop=True)

    t0 = df_ref_node['timestamp'].min()
    target_end = t0 + pd.Timedelta(hours=24)
    ref_df = df_ref_node[df_ref_node['timestamp'] <= target_end].copy()
    n_steps = len(ref_df)

    scaler = MinMaxScaler(feature_range=(0, 1))
    train_scaled = scaler.fit_transform(df_train_node[TARGET_COLS].values)
    full_train = build_feature_matrix(df_train_node['timestamp'].values, train_scaled)

    X, y = create_dataset(full_train, time_step)
    y = y[:, : len(TARGET_COLS)]
    X_tensor = torch.tensor(X, dtype=torch.float32)
    y_tensor = torch.tensor(y, dtype=torch.float32)

    input_size = len(TARGET_COLS) + 2
    model = train_lstm(X_tensor, y_tensor, input_size, len(TARGET_COLS), epochs=epochs)

    output_ts = pd.date_range(start=t0, end=target_end, freq=f'{INTERVAL_SEC}s')
    seed_window = full_train[:time_step]
    start_ts = output_ts[0] - pd.Timedelta(seconds=INTERVAL_SEC)

    predicted = autoregressive_forecast(model, scaler, seed_window, start_ts, n_steps, time_step)

    meta = NODE_INFO.get(node_id, {})
    forecast_df = pd.DataFrame({
        'timestamp': output_ts[:n_steps],
        'node_id': node_id,
        'location': meta.get('location', df_ref_node['location'].iloc[0]),
        'elevation': meta.get('elevation', df_ref_node['elevation'].iloc[0]),
    })
    for i, col in enumerate(TARGET_COLS):
        forecast_df[col] = predicted[:, i]
    forecast_df['ack_success'] = True
    
    # Apply atmospheric physics correction
    elevation_m = meta.get('elevation', df_ref_node['elevation'].iloc[0] if 'elevation' in df_ref_node.columns else 2200.0)
    forecast_df = apply_atmospheric_physics_correction(forecast_df, elevation_m)

    actual_vals = ref_df[TARGET_COLS].values
    corrected_predicted = forecast_df[TARGET_COLS].values
    metrics = compute_metrics(actual_vals, corrected_predicted)

    return forecast_df, ref_df, metrics


def run_all_forecasts():
    os.makedirs(FORECAST_DIR, exist_ok=True)
    os.makedirs(FORECAST_VIZ_DIR, exist_ok=True)

    print(f'Loading {DATA_FILE} and {TRAIN_FILE}...')
    df = pd.read_csv(DATA_FILE, parse_dates=['timestamp'])
    df_train = pd.read_csv(TRAIN_FILE, parse_dates=['timestamp'])

    # Map legacy train node ids (76,56) to current (1,2)
    id_map = {76: 1, 56: 2}
    df_train['node_id'] = df_train['node_id'].map(id_map)

    all_metrics = {'1h': {}, '24h': {}}
    forecast_frames = {'1h': [], '24h': []}

    for node_id in sorted(df['node_id'].unique()):
        df_node = df[df['node_id'] == node_id]
        train_node = df_train[df_train['node_id'] == node_id]

        # --- 1 hour ---
        fc_1h, actual_1h, m1 = forecast_1h_window(df_node, node_id)
        all_metrics['1h'][str(node_id)] = m1
        fc_1h['horizon'] = '1h'
        forecast_frames['1h'].append(fc_1h)

        fc_1h.to_csv(os.path.join(FORECAST_DIR, f'forecast_1h_node{node_id}.csv'), index=False)
        for col in ['SO2', 'H2S', 'Temp_C', 'Humidity_pct']:
            plot_forecast(actual_1h, fc_1h, node_id, '1-Hour', col)
        plot_forecast_dashboard(actual_1h, fc_1h, node_id, '1-Hour')
        print(f'    1h metrics (overall MAE): {m1["overall"]["MAE"]:.4f}')

        # --- 24 hour ---
        if len(train_node) > 0:
            fc_24h, actual_24h, m24 = forecast_24h_window(train_node, df_node, node_id)
            all_metrics['24h'][str(node_id)] = m24
            fc_24h['horizon'] = '24h'
            forecast_frames['24h'].append(fc_24h)

            fc_24h.to_csv(os.path.join(FORECAST_DIR, f'forecast_24h_node{node_id}.csv'), index=False)
            for col in ['SO2', 'H2S', 'Temp_C', 'Humidity_pct']:
                plot_forecast(actual_24h, fc_24h, node_id, '24-Hour', col)
            plot_forecast_dashboard(actual_24h, fc_24h, node_id, '24-Hour')
            print(f'    24h metrics (overall MAE): {m24["overall"]["MAE"]:.4f}')

    pd.concat(forecast_frames['1h'], ignore_index=True).to_csv(
        os.path.join(FORECAST_DIR, 'forecast_1h_all_nodes.csv'), index=False
    )
    pd.concat(forecast_frames['24h'], ignore_index=True).to_csv(
        os.path.join(FORECAST_DIR, 'forecast_24h_all_nodes.csv'), index=False
    )

    with open(os.path.join(FORECAST_DIR, 'forecast_metrics.json'), 'w', encoding='utf-8') as f:
        json.dump(all_metrics, f, indent=2)

    print(f'\nForecasts saved to {FORECAST_DIR}/')
    print(f'Forecast plots saved to {FORECAST_VIZ_DIR}/')
    return all_metrics


def main():
    run_all_forecasts()


if __name__ == '__main__':
    main()
