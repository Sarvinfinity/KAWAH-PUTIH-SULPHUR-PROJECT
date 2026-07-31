# Kawah Putih Sulphur Hazard Intelligence System

This repository contains the complete end-to-end implementation of a physics-informed environmental hazard intelligence system designed for active volcanic craters (specifically Kawah Putih, Indonesia). 

The system leverages IoT telemetry streams, predictive modeling (SeqLSTM), atmospheric dispersion adjustments, and adaptive volcanic baseline hazard labeling (Scenario E) to provide dual-track risk assessments for environmental anomaly detection and human safety.

---

## 1. System Architecture

The project is structured into three cleanly decoupled layers:

```
[ IoT Telemetry / csv ] 
        ↓
[ Data & Prediction Layer (Python) ] ──> SeqLSTM Forecasting (forecasting.py)
        ↓                                ──> Atmospheric Correction (src/atmospheric_correction.py)
        ↓                                ──> Adaptive Z-Score Model (src/adaptive_hazard_labeling.py)
[ API / Serving Layer (FastAPI) ]    ──> Pydantic validation & Uvicorn JSON server (api/main.py)
        ↓
[ Presentation Layer (React/Vite) ]   ──> Recharts & Live Polling via TanStack Query (web-dashboard/)
```

*   **Telemetry Processing:** Ingests raw time-series data, scales target metrics, and calculates cyclical diurnal time features.
*   **Neural Forecasting:** Predicts lookahead concentrations using a stacked Multivariate LSTM.
*   **Atmospheric Physics Layer:** Corrects measurements dynamically based on barometric pressure, wind dispersion (inverse Gaussian plume approximation), humidity scrubbing, and diurnal boundary layer temperature inversions.
*   **Adaptive Labeling Engine:** Runs rolling EMA baseline computations and maps standard deviation ($\sigma$) boundaries to separate environmental anomalies from human safety risk thresholds.
*   **FastAPI Engine:** Serves pipeline data dynamically via REST endpoints using Pydantic models.
*   **React Dashboard:** Renders charts, telemetry indices, and health panels using TanStack Query automatic polling.

---

## 2. Folder Structure

```
.
├── api/                           # FastAPI serving layer
│   ├── __init__.py                # Package marker
│   └── main.py                    # Main API server & routes
├── src/                           # Core data science modules
│   ├── adaptive_hazard_labeling.py# Scenario E rolling baseline & Z-score rules
│   ├── atmospheric_correction.py  # Physics-based correction algorithms
│   ├── composite_hazard.py        # Composite hazard index (CHI) equations
│   ├── hazard_labeling.py         # Standard WHO / NIOSH threshold rules
│   └── training.py                # ML ablation & classifier training utilities
├── web-dashboard/                 # React frontend client
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.tsx      # Main dashboard containing TanStack Query hooks
│   │   │   └── Sidebar.tsx        # Application navigation panel
│   │   ├── App.tsx                # Layout and tab controller
│   │   └── main.tsx               # QueryClient provider setup
│   └── Dockerfile                 # Multi-stage production Nginx dockerfile
├── Dockerfile                     # Backend API server dockerfile
├── docker-compose.yml             # Container orchestration config
├── requirements.txt               # Locked python dependencies
├── all_data_ts.csv                # Raw IoT telemetry dataset
└── expanded_24H_all_data.csv      # 24h expanded corrected reference dataset
```

---

## 3. Developer Guide & Setup

### Prerequisites
*   Python 3.10+
*   Node.js 20+

### Local Execution Setup

1.  **Backend Environment Setup:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
    pip install -r requirements.txt
    ```
2.  **Frontend Environment Setup:**
    ```bash
    cd web-dashboard
    npm install
    ```

### Running the System
1.  **Launch the Backend API Server:**
    ```bash
    # Run from repository root
    python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
    ```
2.  **Launch the Frontend Dev Server:**
    ```bash
    cd web-dashboard
    npm run dev
    ```
    Access the dashboard at `http://localhost:5173`.

---

## 4. API Guide

The FastAPI backend exposes the following REST endpoints on `http://localhost:8000`:

*   **`GET /api/v1/health`**  
    Checks pipeline loading state, model availability, and active monitoring nodes.
*   **`GET /api/v1/status/current?node_id={id}`**  
    Fetches the latest reading, rolling baselines, $\sigma$ deviations, and dual-track risk statuses (WHO/NIOSH vs Scenario E).
*   **`GET /api/v1/timeline?node_id={id}&points={count}`**  
    Returns an evenly-sampled series of chronological points for chart rendering.
*   **`GET /api/v1/node/stats?node_id={id}`**  
    Fetches 24-hour averages, maximums, and hazard class percentage distributions.
*   **`GET /api/v1/frameworks/comparison`**  
    Returns class distribution comparison stats for WHO, NIOSH, and Adaptive Volcanic frameworks.

---

## 5. Configuration Guide

System parameters are managed dynamically in code to preserve mathematical stability:

*   **Baseline Window:** Configured as `PERIODS_2H = 1800` (representing 2 hours of 4-second telemetry intervals).
*   **Minimum Variance Floor:** Set to `mean * 0.1` inside `calculate_rolling_stats` to prevent background sensor noise in calm intervals from inflating Z-scores.
*   **Diurnal Inversion Peak:** Diurnal temperature inversion peaks at 02:00 AM and hits its minimum at 14:00 PM (defined via cosine cycle in `apply_atmospheric_physics_correction`).

---

## 6. Troubleshooting Guide

#### Error: "Pipeline data not loaded" (503 Service Unavailable)
*   **Cause:** The FastAPI startup lifecycle hook failed to find `expanded_24H_all_data.csv` in the working directory.
*   **Solution:** Ensure you execute the API server from the root of the repository, or that the file is copied to the backend root directory.

#### Error: Browser CORS Fetch Failure
*   **Cause:** Frontend is attempting to access the backend on a different port/IP, and CORS is blocking it.
*   **Solution:** Check that `allow_credentials=False` is set in `api/main.py` since origins use wildcard bindings `*`.

#### Issue: Chart Loading State Spins Infinitely
*   **Cause:** React Query cannot establish an HTTP socket to port 8000.
*   **Solution:** Verify that the FastAPI backend console shows `Uvicorn running on http://0.0.0.0:8000`. If you run on a custom port, update the `API_BASE` constant in `Dashboard.tsx`.