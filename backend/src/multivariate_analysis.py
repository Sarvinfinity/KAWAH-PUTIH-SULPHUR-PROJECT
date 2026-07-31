"""Multivariate analysis tools for volcanic sulphur hazard sensor data."""

import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler


def compute_correlation_matrix(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Compute the Pearson correlation matrix for selected features."""
    return df[columns].corr()


def compute_covariance_matrix(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Compute the covariance matrix for selected features."""
    return df[columns].cov()


def plot_heatmap(matrix: pd.DataFrame, title: str, output_path: str | None = None) -> None:
    """Visualize a matrix as a heatmap."""
    plt.figure(figsize=(8, 6))
    sns.heatmap(matrix, annot=True, fmt=".2f", cmap="vlag", center=0, square=True)
    plt.title(title)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path)
    plt.show()


def plot_pairwise_relationships(df: pd.DataFrame, columns: list[str], hue: str | None = None, output_path: str | None = None) -> None:
    """Create pair plots for a list of features, optionally colored by a hue column."""
    plot = sns.pairplot(df[columns + ([hue] if hue else [])], hue=hue, corner=True, diag_kind="kde")
    plot.fig.suptitle("Pairwise relationships", y=1.02)
    if output_path:
        plot.savefig(output_path)
    plt.show()


def plot_feature_distributions(df: pd.DataFrame, columns: list[str], output_path: str | None = None) -> None:
    """Plot distribution histograms for selected numeric features."""
    n_cols = 3
    n_rows = int(np.ceil(len(columns) / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))
    axes = axes.flatten()

    for idx, col in enumerate(columns):
        sns.histplot(df[col].dropna(), kde=True, ax=axes[idx], color="steelblue")
        axes[idx].set_title(f"{col} distribution")
        axes[idx].set_xlabel(col)

    for ax in axes[len(columns):]:
        fig.delaxes(ax)

    plt.tight_layout()
    if output_path:
        plt.savefig(output_path)
    plt.show()


def run_pca(df: pd.DataFrame, columns: list[str], n_components: int = 3) -> tuple[PCA, np.ndarray, np.ndarray]:
    """Run PCA on standardized features and return the PCA object, transformed data, and explained variance."""
    scaler = StandardScaler()
    X = scaler.fit_transform(df[columns].dropna())
    pca = PCA(n_components=n_components, random_state=42)
    transformed = pca.fit_transform(X)
    return pca, transformed, pca.explained_variance_ratio_


def plot_pca_variance_explained(pca: PCA, output_path: str | None = None) -> None:
    """Visualize variance explained by each PCA component."""
    plt.figure(figsize=(8, 5))
    explained = np.cumsum(pca.explained_variance_ratio_)
    plt.plot(range(1, len(explained) + 1), explained, marker="o", linewidth=2)
    plt.xticks(range(1, len(explained) + 1))
    plt.xlabel("Number of Components")
    plt.ylabel("Cumulative Explained Variance")
    plt.title("PCA Cumulative Explained Variance")
    plt.grid(True)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path)
    plt.show()


def plot_pca_loadings(pca: PCA, columns: list[str], n_components: int = 2, output_path: str | None = None) -> None:
    """Plot PCA component loadings for the first principal components."""
    loadings = pd.DataFrame(pca.components_[:n_components], columns=columns, index=[f"PC{i+1}" for i in range(n_components)])
    plt.figure(figsize=(10, 4 * n_components))
    sns.heatmap(loadings, annot=True, cmap="Spectral", center=0)
    plt.title("PCA Component Loadings")
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path)
    plt.show()


def feature_importance_from_pca(pca: PCA, columns: list[str]) -> pd.DataFrame:
    """Return a DataFrame of feature importances derived from PCA loadings."""
    loadings = np.abs(pca.components_[0])
    importance = pd.DataFrame({"feature": columns, "importance": loadings})
    return importance.sort_values("importance", ascending=False).reset_index(drop=True)


def feature_importance_from_model(df: pd.DataFrame, feature_columns: list[str], target_column: str, output_path: str | None = None) -> pd.DataFrame:
    """Train a simple Random Forest regressor to estimate feature importance for a target variable."""
    df_clean = df.dropna(subset=feature_columns + [target_column])
    X = df_clean[feature_columns]
    y = df_clean[target_column]
    model = RandomForestRegressor(random_state=42, n_estimators=100)
    model.fit(X, y)
    importance = pd.DataFrame({"feature": feature_columns, "importance": model.feature_importances_})
    importance = importance.sort_values("importance", ascending=False).reset_index(drop=True)

    if output_path:
        plt.figure(figsize=(8, 5))
        sns.barplot(data=importance, x="importance", y="feature", palette="viridis")
        plt.title(f"Feature importance for predicting {target_column}")
        plt.tight_layout()
        plt.savefig(output_path)
        plt.show()

    return importance


def compare_node_behaviors(
    df: pd.DataFrame,
    columns: list[str],
    node_column: str = "node_id",
    output_path: str | None = None,
) -> None:
    """Compare distributions and relationships for two sensor nodes."""
    nodes = df[node_column].unique()
    if len(nodes) < 2:
        raise ValueError("Dataset must contain at least two distinct nodes for comparison.")

    fig, axes = plt.subplots(len(columns), 1, figsize=(10, 4 * len(columns)))
    if len(columns) == 1:
        axes = [axes]

    for ax, col in zip(axes, columns):
        sns.kdeplot(data=df, x=col, hue=node_column, fill=True, ax=ax, common_norm=False)
        ax.set_title(f"{col} distribution by node")

    plt.tight_layout()
    if output_path:
        plt.savefig(output_path)
    plt.show()


def summarize_relationships(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Return a compact summary of pairwise correlations for the selected features."""
    corr = compute_correlation_matrix(df, columns)
    summary = corr.unstack().reset_index()
    summary.columns = ["feature_a", "feature_b", "correlation"]
    summary = summary[summary["feature_a"] != summary["feature_b"]]
    summary["abs_correlation"] = summary["correlation"].abs()
    summary = summary.sort_values("abs_correlation", ascending=False).drop_duplicates(subset=["abs_correlation"])
    return summary


if __name__ == "__main__":
    print("Use the multivariate_analysis module functions from the package.")
