import pandas as pd
import matplotlib.pyplot as plt
import os

def create_comparison_plot(df_original, df_expanded, feature, feature_name):
    print(f"Generating plot for {feature_name}...")
    
    # Identify the cutoff time where prediction starts
    max_orig_time = df_original['timestamp'].max()
    
    df_pred = df_expanded[df_expanded['timestamp'] > max_orig_time]
    
    nodes = df_expanded['node_id'].unique()
    
    fig, axs = plt.subplots(len(nodes), 1, figsize=(14, 10), sharex=True)
    fig.suptitle(f'{feature_name} over 24 Hours (Original vs Predicted)', fontsize=16)
    
    for i, node in enumerate(nodes):
        # Original data for this node
        node_orig = df_original[df_original['node_id'] == node]
        # Predicted data for this node
        node_pred = df_pred[df_pred['node_id'] == node]
        
        axs[i].plot(node_orig['timestamp'], node_orig[feature], label='Original 7H', color='blue', alpha=0.7)
        axs[i].plot(node_pred['timestamp'], node_pred[feature], label='Predicted 17H', color='orange', alpha=0.7)
        
        # Add a vertical line to indicate where prediction starts
        axs[i].axvline(x=max_orig_time, color='red', linestyle='--', label='Prediction Start')
        
        axs[i].set_title(f'Node {node}')
        axs[i].set_ylabel(feature_name)
        axs[i].legend()
        axs[i].grid(True, alpha=0.3)
        
    plt.xlabel('Timestamp')
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    # Save the plot
    filename = f"{feature.lower()}_comparison.png"
    plt.savefig(filename)
    print(f"Saved {filename}")
    plt.close()

def main():
    print("Loading datasets...")
    df_original = pd.read_csv('all_data_ts.csv')
    df_expanded = pd.read_csv('expanded_24H_all_data.csv')
    
    df_original['timestamp'] = pd.to_datetime(df_original['timestamp'])
    df_expanded['timestamp'] = pd.to_datetime(df_expanded['timestamp'])
    
    features_to_plot = {
        'SO2': 'SO2 Level',
        'H2S': 'H2S Level',
        'Temp_C': 'Temperature (°C)',
        'Humidity_pct': 'Humidity (%)'
    }
    
    for feature, name in features_to_plot.items():
        create_comparison_plot(df_original, df_expanded, feature, name)
        
    print("All visualizations created successfully!")

if __name__ == '__main__':
    main()
