import pandas as pd
import numpy as np
from prophet import Prophet
import matplotlib.pyplot as plt
import logging
import warnings
import sys

# Suppress Prophet logs and warnings for clean output
logging.getLogger("prophet").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

# ==============================================================================
# DEPRECATION WARNING
# As per the new architectural guidelines, this Prophet expansion script is 
# DEPRECATED. The primary forecasting pipeline now exclusively utilizes SeqLSTM 
# augmented with a physics-based atmospheric correction post-processing layer.
# Please see `expand_dataset.py` and `src/atmospheric_correction.py` instead.
# ==============================================================================

print("\n" + "="*80)
print("WARNING: prophet_expand.py is DEPRECATED and should not be used in production.")
print("The forecasting pipeline has been refactored to use SeqLSTM exclusively.")
print("="*80 + "\n")

TARGET_COLS = ['SO2', 'H2S', 'Temp_C', 'Humidity_pct', 'RSSI_dBm', 'SNR_dB']

def apply_domain_adjustments(df, generated_start_time):
    """
    Applies the night-time emission adjustments and noise to the predicted portion 
    of the dataframe (where timestamp > generated_start_time).
    """
    # Create mask for the predicted portion
    pred_mask = df['timestamp'] > generated_start_time
    
    # We will modify the values directly
    timestamps = df.loc[pred_mask, 'timestamp']
    
    # Calculate hour array
    hours = timestamps.dt.hour + timestamps.dt.minute / 60.0 + timestamps.dt.second / 3600.0
    
    # Calculate night factor: peaks at 2 AM, troughs at 2 PM
    night_factor = np.maximum(0, np.cos((hours - 2) * np.pi / 12)).values
    
    # Boost SO2 and H2S
    # We add a multiplicative factor and a baseline shift to ensure it rises at night
    so2_vals = df.loc[pred_mask, 'SO2'].values
    h2s_vals = df.loc[pred_mask, 'H2S'].values
    
    df.loc[pred_mask, 'SO2'] = so2_vals * (1.0 + 1.5 * night_factor) + (50 * night_factor)
    df.loc[pred_mask, 'H2S'] = h2s_vals * (1.0 + 1.2 * night_factor) + (20 * night_factor)
    
    # Add noise to break up Prophet's perfectly smooth curves
    for col in TARGET_COLS:
        vals = df.loc[pred_mask, col].values
        noise = np.random.normal(0, 0.08, size=len(vals))
        df.loc[pred_mask, col] = vals * (1.0 + noise)
        
    # Prevent negative values for physical properties
    for col in TARGET_COLS[:4]:
        df.loc[pred_mask, col] = np.maximum(df.loc[pred_mask, col].values, 0.0)
        
    return df

def generate_visualizations(df_original, df_pred):
    nodes = df_pred['node_id'].unique()
    max_orig_time = df_original['timestamp'].max()
    
    feature_titles = {
        'SO2': 'SO2 Level',
        'H2S': 'H2S Level',
        'Temp_C': 'Temperature (°C)',
        'Humidity_pct': 'Humidity (%)'
    }
    
    print("\nGenerating Prophet visualizations...")
    for feature, feature_name in feature_titles.items():
        fig, axs = plt.subplots(len(nodes), 1, figsize=(14, 10), sharex=True)
        fig.suptitle(f'Prophet Forecast: {feature_name} over 24 Hours', fontsize=16)
        
        for i, node in enumerate(nodes):
            node_orig = df_original[df_original['node_id'] == node]
            node_pred = df_pred[df_pred['node_id'] == node]
            
            # Since node_pred contains BOTH historical and future, we separate them for plotting
            hist = node_pred[node_pred['timestamp'] <= max_orig_time]
            fut = node_pred[node_pred['timestamp'] > max_orig_time]
            
            axs[i].plot(hist['timestamp'], hist[feature], label='Historical (Prophet)', color='blue', alpha=0.7)
            axs[i].plot(fut['timestamp'], fut[feature], label='Predicted 17H (Prophet)', color='orange', alpha=0.7)
            
            # Original raw data behind it to see Prophet fit
            axs[i].plot(node_orig['timestamp'], node_orig[feature], label='Raw 7H Original', color='grey', alpha=0.3)
            
            axs[i].axvline(x=max_orig_time, color='red', linestyle='--', label='Prediction Start')
            
            axs[i].set_title(f'Node {node}')
            axs[i].set_ylabel(feature_name)
            axs[i].legend()
            axs[i].grid(True, alpha=0.3)
            
        plt.xlabel('Timestamp')
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        
        filename = f"prophet_{feature.lower()}_comparison.png"
        plt.savefig(filename)
        print(f"Saved {filename}")
        plt.close()

def main():
    print("Loading original dataset 'all_data_ts.csv'...")
    df_original = pd.read_csv('all_data_ts.csv')
    df_original['timestamp'] = pd.to_datetime(df_original['timestamp'])
    df_original.sort_values('timestamp', inplace=True)
    
    nodes = df_original['node_id'].unique()
    t0 = df_original['timestamp'].min()
    target_end_time = t0 + pd.Timedelta(hours=24)
    pred_interval_sec = 4
    
    all_final_dfs = []
    
    for node_id in nodes:
        print(f"\n--- Processing Node {node_id} with Prophet ---")
        df_node = df_original[df_original['node_id'] == node_id].copy()
        
        # Calculate timestamps up to target_end_time at 4s intervals
        t_last = df_node['timestamp'].max()
        future_seconds = (target_end_time - t_last).total_seconds()
        future_steps = int(future_seconds / pred_interval_sec)
        
        # We'll create a dataframe of timestamps that covers both historical and future
        hist_timestamps = df_node['timestamp'].values
        future_timestamps = [t_last + pd.Timedelta(seconds=pred_interval_sec * i) for i in range(1, future_steps + 1)]
        all_timestamps = np.concatenate([hist_timestamps, future_timestamps])
        
        # Future dataframe for prophet prediction
        future_df = pd.DataFrame({'ds': all_timestamps})
        future_df['ds'] = pd.to_datetime(future_df['ds'])
        
        # Output dataframe for this node
        df_node_out = pd.DataFrame({'timestamp': all_timestamps, 'node_id': node_id})
        df_node_out['timestamp'] = pd.to_datetime(df_node_out['timestamp'])
        df_node_out['ack_success'] = True
        df_node_out['location'] = df_node['location'].iloc[0]
        df_node_out['elevation_m'] = df_node['elevation_m'].iloc[0]
        
        for col in TARGET_COLS:
            print(f"  Fitting Prophet for {col}...")
            
            # Prepare df for Prophet
            train_df = pd.DataFrame({
                'ds': df_node['timestamp'],
                'y': df_node[col]
            })
            
            # Initialize Prophet
            # We disable yearly seasonality since dataset is only 24h
            model = Prophet(yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=True)
            model.fit(train_df)
            
            # Predict
            forecast = model.predict(future_df)
            
            # Save the forecast 'yhat'
            df_node_out[col] = forecast['yhat'].values
            
        # Apply domain adjustments to the future predicted portion
        df_node_out = apply_domain_adjustments(df_node_out, t_last)
        all_final_dfs.append(df_node_out)

    print("\nCombining data...")
    df_final = pd.concat(all_final_dfs, ignore_index=True)
    df_final.sort_values('timestamp', inplace=True)
    df_final.reset_index(drop=True, inplace=True)
    
    out_file = 'prophet_expanded_24H.csv'
    df_final.to_csv(out_file, index=False)
    print(f"Final dataset saved to '{out_file}' (Shape: {df_final.shape})")
    
    # Generate Visualizations
    generate_visualizations(df_original, df_final)
    print("\nProphet Expansion Process Completed Successfully!")

if __name__ == '__main__':
    main()
