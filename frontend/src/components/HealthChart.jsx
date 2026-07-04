import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from "recharts";

const CHART_CONFIG = {
  heart_rate: {
    label: "Heart Rate",
    unit: "bpm",
    color: "#38bdf8",
    colorLight: "#e0f2fe",
    lo: 60,
    hi: 100,
    domain: [45, 130],
    riskZoneColor: "rgba(251, 113, 133, 0.08)",
    safeZoneColor: "rgba(134, 239, 172, 0.10)",
  },
  systolic_bp: {
    label: "Systolic BP",
    unit: "mmHg",
    color: "#f472b6",
    colorLight: "#fce7f3",
    lo: 90,
    hi: 120,
    domain: [80, 160],
    riskZoneColor: "rgba(251, 113, 133, 0.08)",
    safeZoneColor: "rgba(134, 239, 172, 0.10)",
  },
  glucose: {
    label: "Blood Glucose",
    unit: "mg/dL",
    color: "#4ade80",
    colorLight: "#dcfce7",
    lo: 70,
    hi: 140,
    domain: [50, 180],
    riskZoneColor: "rgba(251, 113, 133, 0.08)",
    safeZoneColor: "rgba(134, 239, 172, 0.10)",
  },
};

function formatDate(ts) {
  const d = new Date(ts);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function CustomTooltip({ active, payload, label, metricKey }) {
  if (!active || !payload?.length) return null;
  const cfg = CHART_CONFIG[metricKey];
  const val = payload[0]?.value;
  const isForecast = payload[0]?.payload?._isForecast;

  return (
    <div style={tooltipStyles.container}>
      <p style={tooltipStyles.date}>{formatDate(label)}</p>
      <p style={tooltipStyles.value}>
        {val?.toFixed(1)} {cfg.unit}
      </p>
      {isForecast && <p style={tooltipStyles.tag}>Forecast</p>}
    </div>
  );
}

const tooltipStyles = {
  container: {
    background: "white",
    border: "1px solid #e8eef3",
    borderRadius: 10,
    padding: "10px 14px",
    boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
  },
  date: { fontSize: 12, color: "#94a3b8", marginBottom: 2 },
  value: { fontSize: 16, fontWeight: 600, color: "#1e293b" },
  tag: {
    fontSize: 11,
    color: "#7dd3fc",
    fontWeight: 500,
    marginTop: 2,
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
};

export default function HealthChart({ historical, forecast, metricKey }) {
  const cfg = CHART_CONFIG[metricKey];
  if (!cfg) return null;

  // Merge historical + forecast, marking forecast points
  const histPoints = (historical || []).map((d) => ({
    timestamp: d.timestamp,
    actual: d[metricKey],
    _isForecast: false,
  }));

  const forecastPoints = (forecast || []).map((d) => ({
    timestamp: d.timestamp,
    forecast: d[metricKey],
    _isForecast: true,
  }));

  // Bridge: last historical point also starts forecast line
  if (histPoints.length > 0 && forecastPoints.length > 0) {
    const bridge = { ...histPoints[histPoints.length - 1] };
    bridge.forecast = bridge.actual;
    histPoints[histPoints.length - 1] = bridge;
  }

  const data = [...histPoints, ...forecastPoints];

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <div>
          <h3 style={styles.title}>{cfg.label}</h3>
          <p style={styles.subtitle}>
            Safe range: {cfg.lo}–{cfg.hi} {cfg.unit}
          </p>
        </div>
        <div style={styles.legend}>
          <span style={styles.legendItem}>
            <span
              style={{ ...styles.legendLine, background: cfg.color }}
            ></span>
            Actual
          </span>
          <span style={styles.legendItem}>
            <span
              style={{
                ...styles.legendLine,
                background: cfg.color,
                opacity: 0.5,
                borderStyle: "dashed",
              }}
            ></span>
            Forecast
          </span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
          <defs>
            <linearGradient id={`grad-${metricKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={cfg.color} stopOpacity={0.15} />
              <stop offset="100%" stopColor={cfg.color} stopOpacity={0.02} />
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />

          {/* Healthy zone background */}
          <ReferenceArea
            y1={cfg.lo}
            y2={cfg.hi}
            fill={cfg.safeZoneColor}
            fillOpacity={1}
          />

          <XAxis
            dataKey="timestamp"
            tickFormatter={formatDate}
            tick={{ fontSize: 11, fill: "#94a3b8" }}
            axisLine={{ stroke: "#e8eef3" }}
            tickLine={false}
            interval="preserveStartEnd"
            minTickGap={60}
          />
          <YAxis
            domain={cfg.domain}
            tick={{ fontSize: 11, fill: "#94a3b8" }}
            axisLine={false}
            tickLine={false}
            width={45}
          />

          <Tooltip content={<CustomTooltip metricKey={metricKey} />} />

          {/* Threshold lines */}
          <ReferenceLine
            y={cfg.hi}
            stroke="#fda4af"
            strokeDasharray="6 4"
            strokeWidth={1}
            label={{ value: `${cfg.hi}`, position: "right", fontSize: 10, fill: "#fda4af" }}
          />
          <ReferenceLine
            y={cfg.lo}
            stroke="#fda4af"
            strokeDasharray="6 4"
            strokeWidth={1}
            label={{ value: `${cfg.lo}`, position: "right", fontSize: 10, fill: "#fda4af" }}
          />

          {/* Actual data: solid line with area fill */}
          <Area
            type="monotone"
            dataKey="actual"
            stroke="none"
            fill={`url(#grad-${metricKey})`}
            connectNulls={false}
          />
          <Line
            type="monotone"
            dataKey="actual"
            stroke={cfg.color}
            strokeWidth={2.5}
            dot={false}
            connectNulls={false}
          />

          {/* Forecast: dashed line */}
          <Line
            type="monotone"
            dataKey="forecast"
            stroke={cfg.color}
            strokeWidth={2.5}
            strokeDasharray="8 6"
            strokeOpacity={0.6}
            dot={false}
            connectNulls={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

const styles = {
  card: {
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    padding: "24px",
    boxShadow: "var(--shadow-md)",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 16,
  },
  title: {
    fontSize: 16,
    fontWeight: 600,
    color: "var(--text-primary)",
    margin: 0,
  },
  subtitle: {
    fontSize: 13,
    color: "var(--text-muted)",
    marginTop: 2,
  },
  legend: {
    display: "flex",
    gap: 16,
    fontSize: 12,
    color: "var(--text-secondary)",
  },
  legendItem: {
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  legendLine: {
    display: "inline-block",
    width: 18,
    height: 3,
    borderRadius: 2,
  },
};
