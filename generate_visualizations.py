"""
Generate all visual representations for the 24H synthetic sulphur dataset.
"""
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from config import (
    DATA_FILE,
    NODE_INFO,
    SENSOR_LABELS,
    TARGET_COLS,
    VIZ_DIR,
)

plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette('husl')


def load_data():
    df = pd.read_csv(DATA_FILE, parse_dates=['timestamp'])
    df.sort_values(['node_id', 'timestamp'], inplace=True)
    return df


def node_title(node_id):
    info = NODE_INFO[node_id]
    return f"Node {node_id} | {info['location']} | {info['elevation']:.2f} m"


def plot_sensor_timeseries(df):
    """24-hour time series for each sensor, per node."""
    for col in TARGET_COLS:
        nodes = sorted(df['node_id'].unique())
        fig, axes = plt.subplots(len(nodes), 1, figsize=(14, 4 * len(nodes)), sharex=True)
        if len(nodes) == 1:
            axes = [axes]
        fig.suptitle(f'24-Hour Synthetic: {SENSOR_LABELS[col]}', fontsize=14, fontweight='bold')

        for ax, node in zip(axes, nodes):
            d = df[df['node_id'] == node]
            ax.plot(d['timestamp'], d[col], linewidth=0.8, alpha=0.85)
            ax.set_ylabel(SENSOR_LABELS[col])
            ax.set_title(node_title(node), fontsize=10)
            ax.grid(True, alpha=0.3)

        axes[-1].set_xlabel('Timestamp')
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        fname = os.path.join(VIZ_DIR, f'timeseries_{col.lower()}.png')
        plt.savefig(fname, dpi=120, bbox_inches='tight')
        plt.close()
        print(f'  Saved {fname}')


def plot_env_dashboard(df):
    """2x2 dashboard: SO2, H2S, Temp, Humidity per node."""
    env_cols = ['SO2', 'H2S', 'Temp_C', 'Humidity_pct']
    for node in sorted(df['node_id'].unique()):
        d = df[df['node_id'] == node]
        fig, axes = plt.subplots(2, 2, figsize=(14, 8))
        fig.suptitle(f'Environmental Dashboard — {node_title(node)}', fontsize=13, fontweight='bold')

        for ax, col in zip(axes.flat, env_cols):
            ax.plot(d['timestamp'], d[col], color='steelblue', linewidth=0.9)
            ax.set_ylabel(SENSOR_LABELS[col])
            ax.set_title(SENSOR_LABELS[col])
            ax.grid(True, alpha=0.3)

        for ax in axes[1, :]:
            ax.set_xlabel('Timestamp')
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        fname = os.path.join(VIZ_DIR, f'dashboard_node{node}.png')
        plt.savefig(fname, dpi=120, bbox_inches='tight')
        plt.close()
        print(f'  Saved {fname}')


def plot_node_comparison(df):
    """Both nodes on same axes for key sensors."""
    compare_cols = ['SO2', 'H2S', 'Temp_C', 'Humidity_pct']
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle('Node Comparison (Synthetic 24H)', fontsize=14, fontweight='bold')

    for ax, col in zip(axes.flat, compare_cols):
        for node in sorted(df['node_id'].unique()):
            d = df[df['node_id'] == node]
            ax.plot(d['timestamp'], d[col], label=f'Node {node}', linewidth=0.8, alpha=0.8)
        ax.set_ylabel(SENSOR_LABELS[col])
        ax.set_title(SENSOR_LABELS[col])
        ax.legend()
        ax.grid(True, alpha=0.3)

    for ax in axes[1, :]:
        ax.set_xlabel('Timestamp')
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fname = os.path.join(VIZ_DIR, 'node_comparison.png')
    plt.savefig(fname, dpi=120, bbox_inches='tight')
    plt.close()
    print(f'  Saved {fname}')


def plot_diurnal_patterns(df):
    """Hourly average diurnal cycle per sensor and node."""
    df = df.copy()
    df['hour'] = df['timestamp'].dt.hour + df['timestamp'].dt.minute / 60.0

    for col in TARGET_COLS:
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle(f'Diurnal Pattern: {SENSOR_LABELS[col]}', fontsize=13, fontweight='bold')

        for ax, node in zip(axes, sorted(df['node_id'].unique())):
            d = df[df['node_id'] == node]
            hourly = d.groupby(d['hour'].astype(int))[col].agg(['mean', 'std']).reset_index()
            ax.plot(hourly['hour'], hourly['mean'], marker='o', linewidth=2, label='Mean')
            ax.fill_between(
                hourly['hour'],
                hourly['mean'] - hourly['std'],
                hourly['mean'] + hourly['std'],
                alpha=0.25,
                label='±1 std',
            )
            ax.set_xlabel('Hour of day')
            ax.set_ylabel(SENSOR_LABELS[col])
            ax.set_title(f'Node {node}')
            ax.set_xticks(range(0, 24, 2))
            ax.legend()
            ax.grid(True, alpha=0.3)

        plt.tight_layout(rect=[0, 0, 1, 0.94])
        fname = os.path.join(VIZ_DIR, f'diurnal_{col.lower()}.png')
        plt.savefig(fname, dpi=120, bbox_inches='tight')
        plt.close()
        print(f'  Saved {fname}')


def plot_distributions(df):
    """Histogram distributions per sensor and node."""
    n_nodes = df['node_id'].nunique()
    fig, axes = plt.subplots(len(TARGET_COLS), n_nodes, figsize=(5 * n_nodes, 3 * len(TARGET_COLS)))
    if n_nodes == 1:
        axes = axes.reshape(-1, 1)

    for i, col in enumerate(TARGET_COLS):
        for j, node in enumerate(sorted(df['node_id'].unique())):
            d = df[df['node_id'] == node][col]
            axes[i, j].hist(d, bins=40, color='teal', edgecolor='white', alpha=0.85)
            axes[i, j].set_title(f'Node {node} — {col}')
            axes[i, j].set_ylabel('Count')

    fig.suptitle('Sensor Value Distributions (24H Synthetic)', fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    fname = os.path.join(VIZ_DIR, 'distributions.png')
    plt.savefig(fname, dpi=100, bbox_inches='tight')
    plt.close()
    print(f'  Saved {fname}')


def plot_correlation_heatmaps(df):
    """Correlation matrix per node."""
    for node in sorted(df['node_id'].unique()):
        d = df[df['node_id'] == node][TARGET_COLS]
        corr = d.corr()
        fig, ax = plt.subplots(figsize=(8, 6))
        sns.heatmap(
            corr,
            annot=True,
            fmt='.2f',
            cmap='RdBu_r',
            center=0,
            vmin=-1,
            vmax=1,
            square=True,
            ax=ax,
        )
        ax.set_title(f'Sensor Correlations — {node_title(node)}', fontsize=11)
        plt.tight_layout()
        fname = os.path.join(VIZ_DIR, f'correlation_node{node}.png')
        plt.savefig(fname, dpi=120, bbox_inches='tight')
        plt.close()
        print(f'  Saved {fname}')


def plot_rf_quality(df):
    """RSSI and SNR over 24 hours."""
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    fig.suptitle('RF Link Quality (24H Synthetic)', fontsize=14, fontweight='bold')

    for node in sorted(df['node_id'].unique()):
        d = df[df['node_id'] == node]
        axes[0].plot(d['timestamp'], d['RSSI_dBm'], label=f'Node {node}', linewidth=0.8)
        axes[1].plot(d['timestamp'], d['SNR_dB'], label=f'Node {node}', linewidth=0.8)

    axes[0].set_ylabel(SENSOR_LABELS['RSSI_dBm'])
    axes[1].set_ylabel(SENSOR_LABELS['SNR_dB'])
    axes[0].legend()
    axes[1].legend()
    axes[1].set_xlabel('Timestamp')
    for ax in axes:
        ax.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fname = os.path.join(VIZ_DIR, 'rf_quality.png')
    plt.savefig(fname, dpi=120, bbox_inches='tight')
    plt.close()
    print(f'  Saved {fname}')


def plot_summary_overview(df):
    """Single-page overview of all sensors for both nodes."""
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(3, 2, hspace=0.35, wspace=0.25)

    env = ['SO2', 'H2S', 'Temp_C', 'Humidity_pct', 'RSSI_dBm', 'SNR_dB']
    positions = [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)]

    for col, (r, c) in zip(env, positions):
        ax = fig.add_subplot(gs[r, c])
        for node in sorted(df['node_id'].unique()):
            d = df[df['node_id'] == node]
            ax.plot(d['timestamp'], d[col], label=f'Node {node}', linewidth=0.7, alpha=0.85)
        ax.set_title(SENSOR_LABELS[col], fontsize=10)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        if r == 2:
            ax.set_xlabel('Time')

    fig.suptitle('24-Hour Synthetic Dataset — Full Overview', fontsize=15, fontweight='bold')
    fname = os.path.join(VIZ_DIR, 'overview_all_sensors.png')
    plt.savefig(fname, dpi=120, bbox_inches='tight')
    plt.close()
    print(f'  Saved {fname}')


def main():
    os.makedirs(VIZ_DIR, exist_ok=True)
    print(f'Loading {DATA_FILE}...')
    df = load_data()
    print(f'Dataset: {df.shape[0]} rows, nodes {sorted(df["node_id"].unique())}\n')

    print('Generating visualizations:')
    plot_summary_overview(df)
    plot_sensor_timeseries(df)
    plot_env_dashboard(df)
    plot_node_comparison(df)
    plot_diurnal_patterns(df)
    plot_distributions(df)
    plot_correlation_heatmaps(df)
    plot_rf_quality(df)

    print(f'\nAll visualizations saved to {VIZ_DIR}/')


if __name__ == '__main__':
    main()
