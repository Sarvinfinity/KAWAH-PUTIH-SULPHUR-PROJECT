# Kawah Putih Sulphur Hazard Intelligence

This repository contains data processing, hazard labeling, and forecasting utilities for Kawah Putih volcanic gas monitoring. It supports threshold-based risk classification, data-driven hazard scoring, and comparison of WHO / NIOSH / hybrid operational status schemes.

## Project overview

- `all_data_ts.csv` - raw time-series sensor data with `SO2` and `H2S` concentrations.
- `expanded_24H_all_data.csv` - expanded 24-hour dataset used for hazard dashboard and comparisons.
- `src/` - core processing modules:
  - `src/hazard_labeling.py` - hazard labeling by `WHO`, `NIOSH`, node-based rules, and data-driven quantile labeling.
  - `src/realtime_prediction.py` - real-time prediction pipeline with alert formatting.
  - `src/dashboard.py` - dashboard runner that compares hazard labels across schemes and saves plots.
  - `src/training.py` - model training utilities (XGBoost / Random Forest).
  - `src/composite_hazard.py` - CHI calculations and hazard classification utilities.

## Classification labels

Operational statuses now include:
- `Normal`
- `Moderate`
- `Dangerous`
- `Critical`

These are used for dashboard, alerting, and risk comparison.

## Installation

Create a Python environment and install the required packages:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## How to run

### 1. Build the hazard dashboard

This script labels the expanded dataset using WHO, NIOSH, and data-driven schemes, then saves a comparison CSV and plot.

```powershell
python src/dashboard.py
```

### 2. Run rule-based hazard labeling manually

For the expanded 24-hour dataset, add `WHO` labels and display counts:

```powershell
python -c "import pandas as pd; from src.hazard_labeling import add_hazard_level, display_class_distribution; df=pd.read_csv('expanded_24H_all_data.csv'); df=add_hazard_level(df, scheme='WHO', label_col='hazard_level_who'); display_class_distribution(df, 'hazard_level_who')"
```

### 3. Run NIOSH-based labeling

```powershell
python -c "import pandas as pd; from src.hazard_labeling import add_hazard_level, display_class_distribution; df=pd.read_csv('expanded_24H_all_data.csv'); df=add_hazard_level(df, scheme='NIOSH', label_col='hazard_level_niosh'); display_class_distribution(df, 'hazard_level_niosh')"
```

### 4. Run data-driven labeling

```powershell
python -c "import pandas as pd; from src.hazard_labeling import label_data_driven_hazard_levels; df=pd.read_csv('expanded_24H_all_data.csv'); df=label_data_driven_hazard_levels(df); display(df['hazard_level_data'].value_counts())"
```

## Outputs

After running `src/dashboard.py`, the following files are created:

- `outputs/visualizations/expanded_24H_hazard_comparison.csv`
- `outputs/visualizations/hazard_label_comparison.png`

## Notes

- The `src/dashboard.py` script uses the expanded 24-hour dataset by default.
- The new dashboard supports comparison between:
  - `WHO` thresholds
  - `NIOSH` thresholds
  - data-driven quantile-based hazard levels
  - hybrid combinations of threshold + data-driven labels

If you want, I can also add a short `README` section with a sample plot interpretation or modeling workflow.