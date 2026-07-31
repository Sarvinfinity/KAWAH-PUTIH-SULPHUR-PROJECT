import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
import torch
import torch.nn as nn
import datetime

# Target continuous columns to model and predict
TARGET_COLS = ['SO2', 'H2S', 'Temp_C', 'Humidity_pct', 'RSSI_dBm', 'SNR_dB']

def create_dataset(dataset, time_step=1):
    dataX, dataY = [], []
    for i in range(len(dataset) - time_step):
        a = dataset[i:(i + time_step), :]
        dataX.append(a)
        dataY.append(dataset[i + time_step, :])
    return np.array(dataX), np.array(dataY)

class MultivariateLSTM(nn.Module):
    def __init__(self, input_size, hidden_size=64, num_layers=2, output_size=7):
        super(MultivariateLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc1 = nn.Linear(hidden_size, 32)
        self.fc2 = nn.Linear(32, output_size)

    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        out, _ = self.lstm(x, (h0, c0))
        out = out[:, -1, :] # Last time step
        out = torch.relu(self.fc1(out))
        out = self.fc2(out)
        return out

def get_time_features(timestamp):
    """Calculates cyclical time features from a datetime object."""
    hour = timestamp.hour + timestamp.minute / 60.0 + timestamp.second / 3600.0
    # 24 hour cycle
    hour_sin = np.sin(2 * np.pi * hour / 24.0)
    hour_cos = np.cos(2 * np.pi * hour / 24.0)
    return [hour_sin, hour_cos]

def process_node(df_node, node_id, time_step=30, future_seconds=17*3600):
    print(f"\n--- Processing Node {node_id} ---")
    
    # 1. Prepare Data
    timestamps = df_node['timestamp'].values
    raw_data = df_node[TARGET_COLS].values
    
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(raw_data)
    
    # Add engineered time features to inputs
    # Time features won't be predicted, they are calculated deterministically
    time_features = np.array([get_time_features(pd.to_datetime(t)) for t in timestamps])
    
    # Combine scaled target features with time features
    # shape: (N, 7 + 2) = (N, 9)
    full_features = np.hstack((scaled_data, time_features))
    
    X, y = create_dataset(full_features, time_step)
    # y should only be the targets (first 7 columns), not the time features
    y = y[:, :len(TARGET_COLS)]
    
    X_tensor = torch.tensor(X, dtype=torch.float32)
    y_tensor = torch.tensor(y, dtype=torch.float32)

    # 2. Build and Train Model
    input_size = len(TARGET_COLS) + 2 # 7 targets + 2 time features
    model = MultivariateLSTM(input_size=input_size, hidden_size=64, num_layers=2, output_size=len(TARGET_COLS))
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005)

    epochs = 100
    print(f"Training LSTM for Node {node_id} on {len(X_tensor)} samples...")
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        outputs = model(X_tensor)
        loss = criterion(outputs, y_tensor)
        loss.backward()
        optimizer.step()
        
        if (epoch + 1) % 25 == 0:
            print(f'Epoch [{epoch+1}/{epochs}], Loss: {loss.item():.6f}')

    # 3. Autoregressive Prediction
    # Node frequency is typically 4 seconds.
    # We will generate data up to `future_seconds`.
    pred_interval_sec = 4
    future_steps = int(future_seconds / pred_interval_sec)
    print(f"Predicting next {future_steps} steps (approx {future_seconds/3600:.2f} hours)...")
    
    model.eval()
    
    # Initialize with the last `time_step` window
    current_window = full_features[-time_step:].copy() # shape: (time_step, 9)
    last_timestamp = pd.to_datetime(timestamps[-1])
    
    generated_data = []
    generated_timestamps = []
    
    # To avoid list operations overhead, we do this in a loop
    for i in range(future_steps):
        # Prepare input
        x_input = current_window.reshape((1, time_step, input_size))
        x_tensor = torch.tensor(x_input, dtype=torch.float32)
        
        with torch.no_grad():
            yhat = model(x_tensor).numpy()[0] # shape (7,)
        
        # Determine the next timestamp
        next_timestamp = last_timestamp + datetime.timedelta(seconds=pred_interval_sec)
        generated_timestamps.append(next_timestamp)
        
        # Calculate time features for the next step
        next_time_features = get_time_features(next_timestamp)
        
        # Record the prediction
        generated_data.append(yhat)
        
        # Construct the new feature row (predictions + deterministic time features)
        new_row = np.hstack((yhat, next_time_features))
        
        # Update the sliding window
        current_window = np.vstack((current_window[1:], new_row))
        last_timestamp = next_timestamp

        if (i+1) % 5000 == 0:
            print(f"  ...predicted {i+1}/{future_steps} steps")

    # 4. Inverse transform predictions
    predicted_raw = scaler.inverse_transform(np.array(generated_data))
    
    # 5. Create DataFrame for generated data first, so we can pass it to the physics layer
    df_generated = pd.DataFrame(predicted_raw, columns=TARGET_COLS)
    df_generated['timestamp'] = generated_timestamps
    df_generated['node_id'] = node_id
    df_generated['ack_success'] = True # Assume true for generated future data
    
    # 6. Apply physics-based atmospheric correction
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.atmospheric_correction import apply_atmospheric_physics_correction
    
    # Node 1 is ~2201.98m, Node 2 is ~2192.38m (or legacy ids 76/56)
    elevation_m = 2201.98 if node_id in (1, 76) else 2192.38
    df_generated = apply_atmospheric_physics_correction(df_generated, elevation_m=elevation_m)
    
    return df_generated

def main():
    print("Loading original dataset 'all_data_ts.csv'...")
    df_original = pd.read_csv('all_data_ts.csv')
    df_original['timestamp'] = pd.to_datetime(df_original['timestamp'])
    
    # Ensure dataset is sorted by time
    df_original.sort_values('timestamp', inplace=True)
    
    # Extract cyclical time features for the ORIGINAL dataframe as requested by user
    time_feats = np.array([get_time_features(t) for t in df_original['timestamp']])
    df_original['hour_sin'] = time_feats[:, 0]
    df_original['hour_cos'] = time_feats[:, 1]
    
    print(f"Original dataset shape: {df_original.shape}")
    
    # Separate nodes
    nodes = df_original['node_id'].unique()
    
    # Calculate target end time (24 hours from the very first timestamp)
    t0 = df_original['timestamp'].min()
    target_end_time = t0 + pd.Timedelta(hours=24)
    
    all_generated_dfs = []
    
    for node_id in nodes:
        df_node = df_original[df_original['node_id'] == node_id].copy()
        df_node.sort_values('timestamp', inplace=True)
        
        # Calculate exactly how many seconds we need to reach target_end_time
        t_last = df_node['timestamp'].max()
        future_seconds = (target_end_time - t_last).total_seconds()
        
        # Process and predict for this node
        df_gen = process_node(df_node, node_id, time_step=30, future_seconds=future_seconds)
        
        # Add engineered features to the generated dataframe so it matches original
        gen_time_feats = np.array([get_time_features(t) for t in df_gen['timestamp']])
        df_gen['hour_sin'] = gen_time_feats[:, 0]
        df_gen['hour_cos'] = gen_time_feats[:, 1]
        
        all_generated_dfs.append(df_gen)

    print("\nCombining generated data with original data...")
    # Combine original and all generated data
    df_final = pd.concat([df_original] + all_generated_dfs, ignore_index=True)
    
    # Sort the final combined dataset chronologically
    df_final.sort_values('timestamp', inplace=True)
    df_final.reset_index(drop=True, inplace=True)
    
    # Save to CSV
    out_file = 'expanded_24H_all_data.csv'
    df_final.to_csv(out_file, index=False)
    print(f"Final dataset saved to '{out_file}' (Shape: {df_final.shape})")
    
    # Plotting one feature (e.g., SO2) for one node to verify continuity
    print("Generating plot for verification...")
    plot_node = nodes[0]
    df_plot_orig = df_original[df_original['node_id'] == plot_node]
    df_plot_gen = all_generated_dfs[0] # correspods to nodes[0]
    
    plt.figure(figsize=(14, 6))
    plt.plot(df_plot_orig['timestamp'], df_plot_orig['SO2'], label=f'Original SO2 (Node {plot_node})', color='blue')
    plt.plot(df_plot_gen['timestamp'], df_plot_gen['SO2'], label=f'Predicted SO2 (Node {plot_node})', color='orange')
    plt.title(f'SO2 Dataset Expansion for Node {plot_node}')
    plt.xlabel('Timestamp')
    plt.ylabel('SO2')
    plt.legend()
    plt.grid(True)
    plt.savefig('node_expansion_plot.png')
    print("Plot saved to 'node_expansion_plot.png'")
    
    print("\nExpansion Process Completed Successfully!")

if __name__ == '__main__':
    main()
