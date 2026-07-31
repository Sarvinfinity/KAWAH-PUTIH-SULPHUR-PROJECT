"""
Validation script for the Adaptive Volcanic Hybrid Framework.

Runs the framework against the 24-hour physics-corrected dataset, calculates
class balance, performs sensitivity analysis on sigma multipliers, and compares
against historical frameworks (WHO, NIOSH, Data-driven, Original Hybrid).
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

plt.style.use('seaborn-v0_8-paper')
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'legend.fontsize': 9,
    'figure.dpi': 300,
    'savefig.dpi': 300,
})

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.adaptive_hazard_labeling import label_adaptive_volcanic_hybrid, calculate_rolling_stats
from src.hazard_labeling import (
    add_hazard_level,
    label_data_driven_hazard_levels,
    HAZARD_LABELS,
    LABEL_ENCODINGS
)
from src.training import run_ml_ablation_study

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'expanded_24H_all_data.csv')
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'outputs', 'validation', 'adaptive')
TABLES_DIR = os.path.join(OUT_DIR, 'tables')
FIGURES_DIR = os.path.join(OUT_DIR, 'figures')

for d in [TABLES_DIR, FIGURES_DIR]:
    os.makedirs(d, exist_ok=True)


def load_data():
    df = pd.read_csv(DATA_PATH)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['hour'] = df['timestamp'].dt.hour
    return df


def calculate_distribution(df, label_col):
    counts = df[label_col].value_counts()
    total = len(df)
    return {label: (counts.get(label, 0) / total * 100) for label in HAZARD_LABELS}


def step1_framework_comparison(df):
    print("Running framework comparison...")
    
    # 1. Old Frameworks
    df = add_hazard_level(df, scheme="WHO", label_col="label_who")
    df = add_hazard_level(df, scheme="NIOSH", label_col="label_niosh")
    df = label_data_driven_hazard_levels(df, method="quantile", label_col="label_datadriven")
    df = add_hazard_level(df, scheme="HYBRID", label_col="label_hybrid_old")
    
    # 2. New Adaptive Framework
    df = label_adaptive_volcanic_hybrid(df)
    
    frameworks = {
        'WHO': 'label_who',
        'NIOSH': 'label_niosh',
        'Data-Driven': 'label_datadriven',
        'Original Hybrid': 'label_hybrid_old',
        'Adaptive Hybrid': 'label_adaptive'
    }
    
    summary = []
    for fw_name, col in frameworks.items():
        dist = calculate_distribution(df, col)
        for label in HAZARD_LABELS:
            summary.append({
                'Framework': fw_name,
                'Label': label,
                'Percentage': dist[label]
            })
            
    summary_df = pd.DataFrame(summary)
    summary_df.to_csv(os.path.join(TABLES_DIR, 'adaptive_framework_comparison.csv'), index=False)
    
    # Plot comparison
    plt.figure(figsize=(12, 6))
    sns.barplot(data=summary_df, x='Framework', y='Percentage', hue='Label', hue_order=HAZARD_LABELS,
                palette=['#2ca02c', '#ff7f0e', '#d62728', '#9467bd'])
    plt.title('Risk Distribution: Adaptive Volcanic Hybrid vs Legacy Models')
    plt.ylabel('Percentage of Dataset (%)')
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, 'adaptive_framework_comparison.png'))
    plt.close()
    
    return df


def step2_node_behavior(df):
    print("Running node-wise analysis...")
    
    # We want to plot the raw SO2 vs the Baseline SO2 to visually prove the adaptive nature
    node_76 = df[df['node_id'].isin([76, 1])].copy()
    node_56 = df[df['node_id'].isin([56, 2])].copy()
    
    def plot_baseline_tracking(node_df, name):
        if len(node_df) == 0: return
        # Subsample for cleaner plot (every 100th point)
        plot_df = node_df.iloc[::100]
        
        plt.figure(figsize=(12, 5))
        plt.plot(plot_df['timestamp'], plot_df['SO2'], label='Raw SO2 (ppm)', alpha=0.5, color='grey')
        plt.plot(plot_df['timestamp'], plot_df['Baseline_SO2'], label='Adaptive Baseline (EMA)', color='blue', linewidth=2)
        
        # Overlay Critical markers
        critical = plot_df[plot_df['label_adaptive'] == 'Critical']
        plt.scatter(critical['timestamp'], critical['SO2'], color='red', label='Critical Anomalies', zorder=5, s=20)
        
        plt.title(f'{name} Adaptive Baseline Tracking')
        plt.ylabel('SO2 (ppm)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(FIGURES_DIR, f'{name.replace(" ", "_")}_baseline.png'))
        plt.close()
        
    plot_baseline_tracking(node_76, 'Node 76 (Crater)')
    plot_baseline_tracking(node_56, 'Node 56 (Path)')


def step3_sensitivity_analysis(df):
    print("Running sensitivity analysis on Sigma multipliers...")
    
    # To test sensitivity, we adjust the sigma boundaries manually
    # Base: 1.5, 2.5, 3.5
    # Strict: 1.0, 2.0, 3.0
    # Loose: 2.0, 3.0, 4.0
    
    results = []
    
    scenarios = [
        ('Strict (1, 2, 3)', 1.0, 2.0, 3.0),
        ('Baseline (1.5, 2.5, 3.5)', 1.5, 2.5, 3.5),
        ('Loose (2, 3, 4)', 2.0, 3.0, 4.0)
    ]
    
    for name, m, d, c in scenarios:
        df_mod = df.copy()
        
        # Get Max Z and CHI
        max_z = np.maximum(df_mod['Sigma_SO2'], df_mod['Sigma_H2S'])
        chi = df_mod['CHI_adaptive']
        
        labels = np.full(len(df_mod), 'Normal', dtype=object)
        labels[max_z >= m] = 'Moderate'
        labels[max_z >= d] = 'Dangerous'
        labels[(max_z >= c) & (chi >= (c + 1.0))] = 'Critical'
        
        counts = pd.Series(labels).value_counts()
        total = len(df_mod)
        
        results.append({
            'Scenario': name,
            'Normal_Pct': counts.get('Normal', 0) / total * 100,
            'Moderate_Pct': counts.get('Moderate', 0) / total * 100,
            'Dangerous_Pct': counts.get('Dangerous', 0) / total * 100,
            'Critical_Pct': counts.get('Critical', 0) / total * 100,
        })
        
    sens_df = pd.DataFrame(results)
    sens_df.to_csv(os.path.join(TABLES_DIR, 'adaptive_sensitivity.csv'), index=False)
    
    sens_df.set_index('Scenario').plot(kind='bar', stacked=True, figsize=(10, 6), colormap='viridis_r')
    plt.title('Sigma Sensitivity Analysis: Adaptive Volcanic Hybrid')
    plt.ylabel('Percentage of Dataset (%)')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, 'adaptive_sensitivity.png'))
    plt.close()


def step4_ema_validation(df):
    print("Running EMA Window Validation...")
    # Test windows: 30m, 1h, 2h, 4h
    # 4s interval means: 30m=450, 1h=900, 2h=1800, 4h=3600
    windows = {'30m': 450, '1h': 900, '2h': 1800, '4h': 3600}
    
    node_df = df[df['node_id'] == 76].copy()
    if len(node_df) == 0:
        node_df = df[df['node_id'] == 1].copy()
        
    plt.figure(figsize=(12, 6))
    plt.plot(node_df['timestamp'][::50], node_df['SO2'][::50], label='Raw SO2', alpha=0.3, color='grey')
    
    colors = ['r', 'g', 'b', 'purple']
    results = []
    
    for (name, w), color in zip(windows.items(), colors):
        stats = calculate_rolling_stats(node_df['SO2'], w)
        plt.plot(node_df['timestamp'][::50], stats['mean'][::50], label=f'EMA {name}', color=color, linewidth=1.5)
        
        # Calculate metric: smoothness (inverse of variance of the derivative)
        smoothness = 1.0 / (np.var(np.diff(stats['mean'].values)) + 1e-6)
        results.append({'Window': name, 'Smoothness': smoothness, 'Mean_Std': stats['std'].mean()})
        
    plt.title('EMA Baseline Stability vs Window Size (Node 76)')
    plt.ylabel('SO2 Baseline (ppm)')
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, 'ema_window_comparison.png'))
    plt.close()
    
    pd.DataFrame(results).to_csv(os.path.join(TABLES_DIR, 'ema_validation.csv'), index=False)


def step5_ml_ablation(df):
    print("Running ML Framework Ablation Study...")
    
    # Needs some numeric features
    features = ['SO2', 'H2S', 'Temp_C', 'Humidity_pct', 'Wind_kph']
    label_cols = ['label_who', 'label_niosh', 'label_datadriven', 'label_hybrid_old', 'label_adaptive']
    
    # We only train on a subset for speed in validation script
    subset = df.sample(n=10000, random_state=42)
    
    run_ml_ablation_study(subset, features, label_cols, os.path.join(TABLES_DIR, 'ml_framework_ablation.csv'))


def main():
    try:
        df = load_data()
        df = step1_framework_comparison(df)
        step2_node_behavior(df)
        step3_sensitivity_analysis(df)
        step4_ema_validation(df)
        step5_ml_ablation(df)
        print("\nAdaptive Volcanic Hybrid Validation Completed.")
        print(f"Results saved to {OUT_DIR}")
    except Exception as e:
        print(f"Error during validation: {e}")

if __name__ == '__main__':
    main()
