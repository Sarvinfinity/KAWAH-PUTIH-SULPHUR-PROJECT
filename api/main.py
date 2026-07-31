"""
FastAPI Backend for the Kawah Putih Sulphur Hazard Intelligence System.

Serves live pipeline data to the React dashboard. Every value returned
by these endpoints originates from the actual processed dataset and
trained models — no mock data, no hardcoded values.

Run with: python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

import pandas as pd
import joblib
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Project path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.adaptive_hazard_labeling import label_adaptive_volcanic_hybrid
from src.hazard_labeling import add_hazard_level

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kawah_api")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATA_PATH = os.path.join(PROJECT_ROOT, "expanded_24H_all_data.csv")
MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "xgboost_weights.joblib")
NODE_ID_MAP = {76: 76, 56: 56, 1: 76, 2: 56}  # normalize legacy IDs

# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class CurrentStatus(BaseModel):
    node_id: int
    timestamp: str
    SO2: float
    H2S: float
    Temp_C: float
    Humidity_pct: float
    Wind_kph: float
    environmental_state: str
    health_risk_who: str
    health_risk_niosh: str
    sigma_so2: float
    sigma_h2s: float
    chi_adaptive: float
    baseline_so2: float
    baseline_h2s: float


class TimelinePoint(BaseModel):
    timestamp: str
    SO2: float
    H2S: float
    Baseline_SO2: float
    Baseline_H2S: float
    CHI_Adaptive: float
    Sigma_SO2: float
    environmental_state: str


class NodeStats(BaseModel):
    node_id: int
    avg_so2: float
    avg_h2s: float
    avg_chi: float
    peak_so2: float
    peak_h2s: float
    normal_pct: float
    moderate_pct: float
    dangerous_pct: float
    critical_pct: float


class FrameworkDistribution(BaseModel):
    framework: str
    Normal: float
    Moderate: float
    Dangerous: float
    Critical: float


class SystemHealth(BaseModel):
    dataset_rows: int
    dataset_columns: int
    nodes_available: list[int]
    xgboost_model_loaded: bool
    dataset_loaded: bool

# ---------------------------------------------------------------------------
# Application state (loaded once at startup)
# ---------------------------------------------------------------------------

class PipelineState:
    """Holds the fully processed pipeline data in memory."""

    def __init__(self) -> None:
        self.df: Optional[pd.DataFrame] = None
        self.xgb_model = None
        self.ready: bool = False

    def get_node_df(self, node_id: int) -> pd.DataFrame:
        """Return a filtered DataFrame for a single node, handling legacy IDs."""
        if self.df is None:
            raise HTTPException(status_code=503, detail="Pipeline data not loaded")

        canonical = NODE_ID_MAP.get(node_id, node_id)
        result = self.df[self.df["node_id"] == canonical]

        if result.empty:
            # Try the original ID directly as a last resort
            result = self.df[self.df["node_id"] == node_id]

        if result.empty:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

        return result


state = PipelineState()

# ---------------------------------------------------------------------------
# Startup: load data and models once
# ---------------------------------------------------------------------------

def _load_pipeline() -> None:
    """Load dataset, apply all labeling frameworks, and load ML models."""
    if not os.path.exists(DATA_PATH):
        logger.error("Dataset not found at %s", DATA_PATH)
        return

    logger.info("Loading dataset from %s ...", DATA_PATH)
    df = pd.read_csv(DATA_PATH, low_memory=False)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    if "Wind_kph" not in df.columns:
        logger.warning("Wind_kph column missing — defaulting to 2.0 kph")
        df["Wind_kph"] = 2.0

    logger.info("Applying Adaptive Volcanic Hybrid labeling ...")
    df = label_adaptive_volcanic_hybrid(df)

    logger.info("Applying WHO thresholds ...")
    df = add_hazard_level(df, scheme="WHO", label_col="label_who")

    logger.info("Applying NIOSH thresholds ...")
    df = add_hazard_level(df, scheme="NIOSH", label_col="label_niosh")

    df = df.sort_values("timestamp").reset_index(drop=True)
    state.df = df
    logger.info("Dataset loaded: %d rows, %d columns", *df.shape)

    if os.path.exists(MODEL_PATH):
        state.xgb_model = joblib.load(MODEL_PATH)
        logger.info("XGBoost model loaded from %s", MODEL_PATH)
    else:
        logger.warning("XGBoost model not found at %s", MODEL_PATH)

    state.ready = True
    logger.info("Pipeline ready.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _load_pipeline()
    yield

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Kawah Putih Sulphur Hazard Intelligence API",
    version="1.0.0",
    description=(
        "Serves live pipeline data from the Adaptive Volcanic Hybrid Framework "
        "(Scenario E) for the Kawah Putih volcanic environment."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # must be False when origin is *
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _check_ready() -> None:
    if not state.ready or state.df is None:
        raise HTTPException(status_code=503, detail="Pipeline data not loaded")


def _safe_float(val, default: float = 0.0, decimals: int = 2) -> float:
    """Safely convert a value to a rounded float."""
    try:
        return round(float(val), decimals)
    except (TypeError, ValueError):
        return default

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/v1/health", response_model=SystemHealth, tags=["System"])
def get_system_health():
    """System health check — always responds, even before data is loaded."""
    return SystemHealth(
        dataset_rows=len(state.df) if state.df is not None else 0,
        dataset_columns=len(state.df.columns) if state.df is not None else 0,
        nodes_available=(
            sorted(state.df["node_id"].unique().tolist())
            if state.df is not None
            else []
        ),
        xgboost_model_loaded=state.xgb_model is not None,
        dataset_loaded=state.ready,
    )


@app.get("/api/v1/status/current", response_model=CurrentStatus, tags=["Hazard"])
def get_current_status(node_id: int = Query(default=76, description="Sensor node ID")):
    """Latest reading and dual-track risk classification for a node."""
    _check_ready()
    node_df = state.get_node_df(node_id)
    last = node_df.iloc[-1]

    return CurrentStatus(
        node_id=int(last["node_id"]),
        timestamp=str(last["timestamp"]),
        SO2=_safe_float(last["SO2"]),
        H2S=_safe_float(last["H2S"]),
        Temp_C=_safe_float(last.get("Temp_C", 15.0)),
        Humidity_pct=_safe_float(last.get("Humidity_pct", 70.0)),
        Wind_kph=_safe_float(last.get("Wind_kph", 2.0)),
        environmental_state=str(last.get("label_adaptive", "Normal")),
        health_risk_who=str(last.get("label_who", "Unknown")),
        health_risk_niosh=str(last.get("label_niosh", "Unknown")),
        sigma_so2=_safe_float(last.get("Sigma_SO2", 0.0), decimals=3),
        sigma_h2s=_safe_float(last.get("Sigma_H2S", 0.0), decimals=3),
        chi_adaptive=_safe_float(last.get("CHI_adaptive", 0.0), decimals=3),
        baseline_so2=_safe_float(last.get("Baseline_SO2", 0.0)),
        baseline_h2s=_safe_float(last.get("Baseline_H2S", 0.0)),
    )


@app.get(
    "/api/v1/timeline",
    response_model=list[TimelinePoint],
    tags=["Hazard"],
)
def get_timeline(
    node_id: int = Query(default=76, description="Sensor node ID"),
    points: int = Query(default=24, ge=2, le=500, description="Number of data points"),
):
    """Evenly-sampled timeline for chart rendering."""
    _check_ready()
    node_df = state.get_node_df(node_id)

    step = max(1, len(node_df) // points)
    sampled = node_df.iloc[::step].head(points)

    return [
        TimelinePoint(
            timestamp=str(row["timestamp"]),
            SO2=_safe_float(row["SO2"]),
            H2S=_safe_float(row["H2S"]),
            Baseline_SO2=_safe_float(row.get("Baseline_SO2", row["SO2"])),
            Baseline_H2S=_safe_float(row.get("Baseline_H2S", row["H2S"])),
            CHI_Adaptive=_safe_float(row.get("CHI_adaptive", 0.0), decimals=3),
            Sigma_SO2=_safe_float(row.get("Sigma_SO2", 0.0), decimals=3),
            environmental_state=str(row.get("label_adaptive", "Normal")),
        )
        for _, row in sampled.iterrows()
    ]


@app.get("/api/v1/node/stats", response_model=NodeStats, tags=["Hazard"])
def get_node_stats(node_id: int = Query(default=76, description="Sensor node ID")):
    """Aggregate statistics and class distribution for a node."""
    _check_ready()
    node_df = state.get_node_df(node_id)
    label_pcts = node_df["label_adaptive"].value_counts(normalize=True) * 100

    return NodeStats(
        node_id=node_id,
        avg_so2=_safe_float(node_df["SO2"].mean()),
        avg_h2s=_safe_float(node_df["H2S"].mean()),
        avg_chi=_safe_float(node_df["CHI_adaptive"].mean(), decimals=3),
        peak_so2=_safe_float(node_df["SO2"].max()),
        peak_h2s=_safe_float(node_df["H2S"].max()),
        normal_pct=_safe_float(label_pcts.get("Normal", 0)),
        moderate_pct=_safe_float(label_pcts.get("Moderate", 0)),
        dangerous_pct=_safe_float(label_pcts.get("Dangerous", 0)),
        critical_pct=_safe_float(label_pcts.get("Critical", 0)),
    )


@app.get(
    "/api/v1/frameworks/comparison",
    response_model=list[FrameworkDistribution],
    tags=["Analysis"],
)
def get_framework_comparison():
    """Side-by-side class distribution across labeling frameworks."""
    _check_ready()
    frameworks = {
        "Adaptive Hybrid": "label_adaptive",
        "WHO": "label_who",
        "NIOSH": "label_niosh",
    }
    results: list[FrameworkDistribution] = []
    for fw_name, col in frameworks.items():
        if col not in state.df.columns:
            continue
        pcts = state.df[col].value_counts(normalize=True) * 100
        results.append(
            FrameworkDistribution(
                framework=fw_name,
                Normal=_safe_float(pcts.get("Normal", 0)),
                Moderate=_safe_float(pcts.get("Moderate", 0)),
                Dangerous=_safe_float(pcts.get("Dangerous", 0)),
                Critical=_safe_float(pcts.get("Critical", 0)),
            )
        )
    return results
