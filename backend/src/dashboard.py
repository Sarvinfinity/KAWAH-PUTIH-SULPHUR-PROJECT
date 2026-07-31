"""Dashboard comparison runner for hazard classification schemes."""

import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.hazard_labeling import (
    add_hazard_level,
    combine_hazard_schemes,
    display_class_distribution,
    label_data_driven_hazard_levels,
    plot_hazard_comparison,
    save_labeled_dataset,
)


INPUT_PATH = Path("expanded_24H_all_data.csv")
OUTPUT_DIR = Path("outputs/visualizations")


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def build_hazard_dashboard() -> pd.DataFrame:
    df = pd.read_csv(INPUT_PATH)

    df = add_hazard_level(df, scheme="WHO", label_col="hazard_level_who")
    df = add_hazard_level(df, scheme="NIOSH", label_col="hazard_level_niosh")
    df = label_data_driven_hazard_levels(df, method="quantile", label_col="hazard_level_data")

    df = combine_hazard_schemes(
        df,
        source_cols=["hazard_level_who", "hazard_level_data"],
        combined_col="hazard_level_hybrid_who",
    )
    df = combine_hazard_schemes(
        df,
        source_cols=["hazard_level_niosh", "hazard_level_data"],
        combined_col="hazard_level_hybrid_niosh",
    )

    save_labeled_dataset(df, OUTPUT_DIR / "expanded_24H_hazard_comparison.csv")

    label_columns = [
        "hazard_level_who",
        "hazard_level_niosh",
        "hazard_level_data",
        "hazard_level_hybrid_who",
        "hazard_level_hybrid_niosh",
    ]

    plot_hazard_comparison(
        df,
        label_columns=label_columns,
        output_path=str(OUTPUT_DIR / "hazard_label_comparison.png"),
    )

    for label_col in label_columns:
        display_class_distribution(df, label_col=label_col)

    return df


def main() -> None:
    ensure_output_dir()
    df = build_hazard_dashboard()
    print(f"Dashboard labels saved to: {OUTPUT_DIR / 'expanded_24H_hazard_comparison.csv'}")
    print(f"Comparison plot saved to: {OUTPUT_DIR / 'hazard_label_comparison.png'}")
    print(f"Rows processed: {len(df)}")


if __name__ == "__main__":
    main()
