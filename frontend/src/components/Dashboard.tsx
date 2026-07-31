import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Legend, LineChart, Line, BarChart, Bar
} from 'recharts';
import { Radio, Shield, Zap, TrendingUp, Info, Loader, WifiOff, Download, Printer, Settings as SettingsIcon } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

interface DashboardProps {
  activeTab: string;
}

// Interfaces matching the Pydantic schemas in the FastAPI backend
interface CurrentStatus {
  node_id: number;
  timestamp: string;
  SO2: number;
  H2S: number;
  Temp_C: number;
  Humidity_pct: number;
  Wind_kph: number;
  environmental_state: string;
  health_risk_who: string;
  health_risk_niosh: string;
  sigma_so2: number;
  sigma_h2s: number;
  chi_adaptive: number;
  baseline_so2: number;
  baseline_h2s: number;
}

interface TimelinePoint {
  timestamp: string;
  SO2: number;
  H2S: number;
  Baseline_SO2: number;
  Baseline_H2S: number;
  CHI_Adaptive: number;
  Sigma_SO2: number;
  environmental_state: string;
}

interface NodeStats {
  node_id: number;
  avg_so2: number;
  avg_h2s: number;
  avg_chi: number;
  peak_so2: number;
  peak_h2s: number;
  normal_pct: number;
  moderate_pct: number;
  dangerous_pct: number;
  critical_pct: number;
}

interface FrameworkDistribution {
  framework: string;
  Normal: number;
  Moderate: number;
  Dangerous: number;
  Critical: number;
}

// Reusable Skeleton Loader
const Skeleton: React.FC<{ width?: string; height?: string }> = ({ width = '100%', height = '20px' }) => (
  <div
    style={{
      width,
      height,
      borderRadius: '6px',
      background: 'var(--bg-tertiary)',
      animation: 'pulse 1.5s infinite ease-in-out',
      margin: '8px 0'
    }}
  />
);

export const Dashboard: React.FC<DashboardProps> = ({ activeTab }) => {
  const [nodeId, setNodeId] = useState(76);

  // React Query: Current Status Query
  const {
    data: status,
    isLoading: statusLoading,
    error: statusError,
    refetch: refetchStatus
  } = useQuery<CurrentStatus>({
    queryKey: ['currentStatus', nodeId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/v1/status/current?node_id=${nodeId}`);
      if (!res.ok) throw new Error('Failed to fetch current status');
      return res.json();
    }
  });

  // React Query: Timeline Query
  const {
    data: timeline = [],
    isLoading: timelineLoading,
    error: timelineError,
    refetch: refetchTimeline
  } = useQuery<TimelinePoint[]>({
    queryKey: ['timeline', nodeId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/v1/timeline?node_id=${nodeId}&points=24`);
      if (!res.ok) throw new Error('Failed to fetch timeline data');
      return res.json();
    }
  });

  // React Query: Node Statistics Query
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
    refetch: refetchStats
  } = useQuery<NodeStats>({
    queryKey: ['nodeStats', nodeId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/v1/node/stats?node_id=${nodeId}`);
      if (!res.ok) throw new Error('Failed to fetch node statistics');
      return res.json();
    }
  });

  // React Query: Framework Comparison Query (only fetched when needed)
  const {
    data: comparison = [],
    isLoading: comparisonLoading,
    error: comparisonError,
    refetch: refetchComparison
  } = useQuery<FrameworkDistribution[]>({
    queryKey: ['frameworkComparison'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/v1/frameworks/comparison`);
      if (!res.ok) throw new Error('Failed to fetch comparison statistics');
      return res.json();
    },
    enabled: activeTab === 'thresholds'
  });

  const handleRetryAll = () => {
    refetchStatus();
    refetchTimeline();
    refetchStats();
    if (activeTab === 'thresholds') {
      refetchComparison();
    }
  };

  // CSV Export Utility
  const exportToCSV = () => {
    if (!timeline || timeline.length === 0) return;
    const headers = ['Timestamp', 'SO2 (ppm)', 'H2S (ppm)', 'Baseline SO2 (ppm)', 'Baseline H2S (ppm)', 'CHI Adaptive', 'Sigma SO2', 'Environmental State'];
    const rows = timeline.map(p => [
      p.timestamp,
      p.SO2,
      p.H2S,
      p.Baseline_SO2,
      p.Baseline_H2S,
      p.CHI_Adaptive,
      p.Sigma_SO2,
      p.environmental_state
    ]);
    const csvContent = "data:text/csv;charset=utf-8,"
      + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `kawah_putih_node_${nodeId}_timeline.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // PDF / Print Utility
  const exportToPDF = () => {
    window.print();
  };

  const isGlobalError = statusError || timelineError || statsError || (activeTab === 'thresholds' && comparisonError);
  const isGlobalLoading = statusLoading || timelineLoading || statsLoading || (activeTab === 'thresholds' && comparisonLoading);

  // Error boundary state
  if (isGlobalError) {
    return (
      <div className="animate-fade-in" style={{ padding: '40px 0', textAlign: 'center' }}>
        <div className="card" style={{ display: 'inline-flex', alignSelf: 'center', padding: '32px', maxWidth: '480px' }}>
          <WifiOff size={48} color="var(--status-dangerous)" style={{ margin: '0 auto 16px' }} />
          <h2 style={{ color: 'var(--status-dangerous)', marginBottom: '8px' }}>Pipeline Connection Lost</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '24px' }}>
            Unable to connect to Kawah Putih FastAPI server at http://localhost:8000. Verify the server is running.
          </p>
          <button className="btn btn-primary" onClick={handleRetryAll} aria-label="Retry connecting to live backend API">
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  // Pre-process timeline points for Recharts
  const chartData = timeline.map(p => ({
    ...p,
    time: new Date(p.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  }));

  return (
    <div className="animate-fade-in" style={{ paddingBottom: '40px' }}>
      {/* Header Panel */}
      <div className="flex-between" style={{ marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1>Kawah Putih Intelligence</h1>
          <p>Dual-Track Environmental Anomaly & Human Risk Assessment</p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <label htmlFor="node-select" style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Monitoring Station:</label>
          <select
            id="node-select"
            className="btn btn-secondary"
            style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
            value={nodeId}
            onChange={(e) => setNodeId(Number(e.target.value))}
            aria-label="Select sensor node"
          >
            <option value={76}>Node 76 (Crater Floor)</option>
            <option value={56}>Node 56 (Access Trail)</option>
          </select>
          <button className="btn btn-secondary" onClick={exportToCSV} disabled={timeline.length === 0} title="Export Timeline to CSV" aria-label="Export data as CSV">
            <Download size={16} /> Export CSV
          </button>
          <button className="btn btn-secondary" onClick={exportToPDF} title="Print Dashboard View" aria-label="Export dashboard view to PDF">
            <Printer size={16} /> Print Report
          </button>
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* TAB: OVERVIEW */}
      {/* ------------------------------------------------------------- */}
      {activeTab === 'overview' && (
        <>
          {/* Dual-Track Hazard State Panels */}
          <div className="grid-2" style={{ marginBottom: '24px', gap: '16px' }}>
            <div className="card" style={{ borderLeft: `4px solid ${status?.environmental_state === 'Normal' ? 'var(--status-normal)' : 'var(--status-moderate)'}` }}>
              <div className="flex-between">
                <span className="stat-label" style={{ fontWeight: '500' }}>Environmental Anomaly State</span>
                <Zap size={18} color={status?.environmental_state === 'Normal' ? 'var(--status-normal)' : 'var(--status-moderate)'} />
              </div>
              {isGlobalLoading ? <Skeleton height="40px" /> : (
                <div style={{ fontSize: '2rem', fontWeight: '700', marginTop: '8px' }}>
                  {status?.environmental_state}
                </div>
              )}
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                Current Deviation: <strong style={{ color: 'var(--text-primary)' }}>+{status?.sigma_so2?.toFixed(2) ?? '—'}σ</strong> from 2-Hour EMA Baseline
              </div>
            </div>

            <div className="card" style={{ borderLeft: '4px solid var(--status-critical)' }}>
              <div className="flex-between">
                <span className="stat-label" style={{ fontWeight: '500' }}>Human Exposure Risk (NIOSH/WHO)</span>
                <Shield size={18} color="var(--status-critical)" />
              </div>
              {isGlobalLoading ? <Skeleton height="40px" /> : (
                <div style={{ fontSize: '2rem', fontWeight: '700', marginTop: '8px', color: 'var(--status-critical)' }}>
                  {status?.health_risk_niosh}
                </div>
              )}
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                Absolute SO2: <strong style={{ color: 'var(--text-primary)' }}>{status?.SO2?.toFixed(1) ?? '—'} ppm</strong> (NIOSH ceiling: 5.0 ppm)
              </div>
            </div>
          </div>

          {/* Key Metrics Grid */}
          <div className="grid-4" style={{ marginBottom: '24px' }}>
            <div className="card">
              <div className="flex-between">
                <span className="stat-label">Adaptive CHI</span>
                <Radio size={16} color="var(--accent-primary)" />
              </div>
              {isGlobalLoading ? <Skeleton height="32px" /> : (
                <div className="stat-value">{status?.chi_adaptive?.toFixed(3)}</div>
              )}
              <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>STEL-weighted composite index</div>
            </div>

            <div className="card">
              <div className="flex-between">
                <span className="stat-label">SO2 2h-EMA Baseline</span>
                <TrendingUp size={16} color="var(--accent-secondary)" />
              </div>
              {isGlobalLoading ? <Skeleton height="32px" /> : (
                <div className="stat-value">{status?.baseline_so2?.toFixed(1)} ppm</div>
              )}
              <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Dynamic environmental baseline</div>
            </div>

            <div className="card">
              <div className="flex-between">
                <span className="stat-label">Telemetry Status</span>
                <Info size={16} color="var(--status-normal)" />
              </div>
              {isGlobalLoading ? <Skeleton height="32px" /> : (
                <div className="stat-value" style={{ fontSize: '1.25rem', marginTop: '4px', color: 'var(--status-normal)' }}>Active</div>
              )}
              <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Live connection verified</div>
            </div>

            <div className="card">
              <div className="flex-between">
                <span className="stat-label">Current Temperature</span>
                <TrendingUp size={16} color="var(--accent-primary)" />
              </div>
              {isGlobalLoading ? <Skeleton height="32px" /> : (
                <div className="stat-value">{status?.Temp_C?.toFixed(1)} °C</div>
              )}
              <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Ambient node temperature</div>
            </div>
          </div>

          {/* Primary Trend Charts */}
          <div className="grid-2">
            <div className="card" style={{ gridColumn: 'span 2' }}>
              <div className="card-header">
                <div className="card-title">
                  <Zap size={20} color="var(--accent-primary)" />
                  Gas Concentration vs 2-Hour Dynamic Baseline (Node {nodeId})
                </div>
              </div>
              <div style={{ height: '350px' }}>
                {isGlobalLoading ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                    <Loader size={32} className="spinning" color="var(--accent-primary)" />
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorSO2" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="var(--status-critical)" stopOpacity={0.4}/>
                          <stop offset="95%" stopColor="var(--status-critical)" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                      <XAxis dataKey="time" stroke="var(--text-tertiary)" tick={{ fill: 'var(--text-secondary)' }} />
                      <YAxis stroke="var(--text-tertiary)" tick={{ fill: 'var(--text-secondary)' }} />
                      <Tooltip
                        contentStyle={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-strong)', borderRadius: '8px' }}
                        itemStyle={{ color: 'var(--text-primary)' }}
                      />
                      <Legend />
                      <Area type="monotone" dataKey="SO2" name="Instantaneous SO2 (ppm)" stroke="var(--status-critical)" strokeWidth={2} fillOpacity={1} fill="url(#colorSO2)" />
                      <Line type="monotone" dataKey="Baseline_SO2" name="2-Hour Baseline SO2 (EMA)" stroke="var(--accent-primary)" strokeWidth={3} dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
            
            <div className="card" style={{ gridColumn: 'span 2' }}>
              <div className="card-header">
                <div className="card-title">
                  <Info size={20} color="var(--text-secondary)" />
                  Current Station Summary (Last 24h)
                </div>
              </div>
              {isGlobalLoading || !stats ? (
                <Skeleton height="150px" />
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px', textAlign: 'center' }}>
                  <div style={{ padding: '16px', background: 'var(--bg-tertiary)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Avg SO2</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 'bold', marginTop: '8px' }}>{stats.avg_so2.toFixed(1)} ppm</div>
                  </div>
                  <div style={{ padding: '16px', background: 'var(--bg-tertiary)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Avg H2S</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 'bold', marginTop: '8px' }}>{stats.avg_h2s.toFixed(1)} ppm</div>
                  </div>
                  <div style={{ padding: '16px', background: 'var(--bg-tertiary)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Peak SO2</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 'bold', marginTop: '8px', color: 'var(--status-dangerous)' }}>{stats.peak_so2.toFixed(1)} ppm</div>
                  </div>
                  <div style={{ padding: '16px', background: 'var(--bg-tertiary)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Peak H2S</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 'bold', marginTop: '8px', color: 'var(--status-moderate)' }}>{stats.peak_h2s.toFixed(1)} ppm</div>
                  </div>
                  <div style={{ padding: '16px', background: 'var(--bg-tertiary)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Avg CHI</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 'bold', marginTop: '8px' }}>{stats.avg_chi.toFixed(3)}</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB: FORECAST */}
      {/* ------------------------------------------------------------- */}
      {activeTab === 'forecast' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <TrendingUp size={20} color="var(--accent-secondary)" />
              SeqLSTM 24h Lookahead Forecasting
            </div>
          </div>
          <p style={{ marginBottom: '24px', color: 'var(--text-secondary)' }}>
            This panel visualizes the continuous 24-hour predictive forecast generated by the Multivariate SeqLSTM neural network.
          </p>
          <div style={{ height: '350px' }}>
            {isGlobalLoading ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                <Loader size={32} className="spinning" />
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                  <XAxis dataKey="time" stroke="var(--text-tertiary)" />
                  <YAxis stroke="var(--text-tertiary)" />
                  <Tooltip contentStyle={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-strong)' }} />
                  <Legend />
                  <Line type="monotone" dataKey="SO2" stroke="var(--status-dangerous)" strokeWidth={2} dot={false} name="Forecasted SO2 (ppm)" />
                  <Line type="monotone" dataKey="H2S" stroke="var(--status-normal)" strokeWidth={2} dot={false} name="Forecasted H2S (ppm)" />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB: THRESHOLDS */}
      {/* ------------------------------------------------------------- */}
      {activeTab === 'thresholds' && (
        <div className="grid-2">
          <div className="card" style={{ gridColumn: 'span 2' }}>
            <div className="card-header">
              <div className="card-title">
                <Shield size={20} color="var(--status-moderate)" />
                Framework Risk Category Distribution Comparison
              </div>
            </div>
            <p style={{ marginBottom: '24px', color: 'var(--text-secondary)' }}>
              Industrial limits (WHO, NIOSH) permanently saturate to 70%+ Critical in active crater environments.
              The Adaptive Hybrid Framework (Scenario E) adjusts standard limits relative to the local volcanic baseline.
            </p>
            <div style={{ height: '350px' }}>
              {isGlobalLoading ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                  <Loader size={32} className="spinning" />
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={comparison}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                    <XAxis dataKey="framework" stroke="var(--text-tertiary)" />
                    <YAxis stroke="var(--text-tertiary)" label={{ value: 'Percentage (%)', angle: -90, position: 'insideLeft', fill: 'var(--text-secondary)' }} />
                    <Tooltip contentStyle={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-strong)' }} />
                    <Legend />
                    <Bar dataKey="Normal" fill="var(--status-normal)" name="Normal (%)" />
                    <Bar dataKey="Moderate" fill="var(--status-moderate)" name="Moderate (%)" />
                    <Bar dataKey="Dangerous" fill="var(--status-dangerous)" name="Dangerous (%)" />
                    <Bar dataKey="Critical" fill="var(--status-critical)" name="Critical (%)" />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB: CLASSIFICATION */}
      {/* ------------------------------------------------------------- */}
      {activeTab === 'classification' && (
        <div className="grid-2">
          <div className="card">
            <div className="card-header">
              <div className="card-title">
                <Zap size={20} color="var(--accent-secondary)" />
                Rolling Statistical Anomaly Sigma (σ)
              </div>
            </div>
            <div style={{ height: '280px' }}>
              {isGlobalLoading ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                  <Loader size={32} className="spinning" />
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                    <XAxis dataKey="time" stroke="var(--text-tertiary)" />
                    <YAxis domain={[0, 'auto']} stroke="var(--text-tertiary)" />
                    <Tooltip contentStyle={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-strong)' }} />
                    <Legend />
                    <Line type="step" dataKey={() => 3.5} stroke="var(--status-critical)" strokeDasharray="5 5" strokeWidth={1} dot={false} name="Critical Threshold (3.5σ)" />
                    <Line type="step" dataKey={() => 2.5} stroke="var(--status-dangerous)" strokeDasharray="5 5" strokeWidth={1} dot={false} name="Dangerous Threshold (2.5σ)" />
                    <Line type="step" dataKey={() => 1.5} stroke="var(--status-moderate)" strokeDasharray="5 5" strokeWidth={1} dot={false} name="Moderate Threshold (1.5σ)" />
                    <Line type="monotone" dataKey="Sigma_SO2" stroke="var(--accent-secondary)" strokeWidth={2} dot={false} name="SO2 Sigma Deviation" />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title">
                <Info size={20} color="var(--text-secondary)" />
                Monitoring Station Statistics
              </div>
            </div>
            {isGlobalLoading || !stats ? (
              <Skeleton height="200px" />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }} role="region" aria-label="Telemetry statistics list">
                <div className="flex-between" style={{ paddingBottom: '8px', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Station Identifier</span>
                  <strong>Node {stats.node_id}</strong>
                </div>
                <div className="flex-between" style={{ paddingBottom: '8px', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Average SO2 Concentration</span>
                  <strong>{stats.avg_so2.toFixed(2)} ppm</strong>
                </div>
                <div className="flex-between" style={{ paddingBottom: '8px', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Average H2S Concentration</span>
                  <strong>{stats.avg_h2s.toFixed(2)} ppm</strong>
                </div>
                <div className="flex-between" style={{ paddingBottom: '8px', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Peak Observed SO2</span>
                  <strong style={{ color: 'var(--status-dangerous)' }}>{stats.peak_so2.toFixed(1)} ppm</strong>
                </div>
                <div className="flex-between">
                  <span style={{ color: 'var(--text-secondary)' }}>Average Composite Hazard Index (CHI)</span>
                  <strong>{stats.avg_chi.toFixed(3)}</strong>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB: SETTINGS */}
      {/* ------------------------------------------------------------- */}
      {activeTab === 'settings' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <SettingsIcon size={20} color="var(--text-primary)" />
              System Parameters & Configuration
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <h3 style={{ marginBottom: '8px', color: 'var(--text-primary)' }}>Adaptive Framework Variables</h3>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                Baseline calculation window: <strong>2 Hours</strong> (1800 samples at 4s intervals).
                Minimum standard deviation floor: <strong>10% of mean</strong> to suppress background sensor noise.
              </p>
            </div>
            <div>
              <h3 style={{ marginBottom: '8px', color: 'var(--text-primary)' }}>Meteorological Dispersion Rules</h3>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                Stagnation multiplier applied based on local wind speeds: <code>P_meteo = 2.0 / (wind + eps)</code> clamped between 0.5 and 2.0.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
