import { Heart, Activity, Droplets } from "lucide-react";

const METRIC_CONFIG = {
  systolic_bp_mmhg: {
    label: "Systolic BP",
    icon: Heart,
    color: "#fb7185",
    bg: "#ffe4e6",
  },
  heart_rate_bpm: {
    label: "Heart Rate",
    icon: Activity,
    color: "#38bdf8",
    bg: "#e0f2fe",
  },
  glucose_mg_dl: {
    label: "Glucose",
    icon: Droplets,
    color: "#4ade80",
    bg: "#dcfce7",
  },
};

function CircularProgress({ pct, size = 140, stroke = 10, color }) {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;

  const getColor = () => {
    if (color) return color;
    if (pct >= 70) return "#4ade80";
    if (pct >= 45) return "#fbbf24";
    return "#fb7185";
  };

  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="#f1f5f9"
        strokeWidth={stroke}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={getColor()}
        strokeWidth={stroke}
        strokeDasharray={circ}
        strokeDashoffset={offset}
        strokeLinecap="round"
        style={{ transition: "stroke-dashoffset 1s ease" }}
      />
    </svg>
  );
}

export default function TIHRCard({ tihr }) {
  if (!tihr || !tihr.per_metric) return null;

  const simPct = tihr.simultaneous_tihr_pct || 0;

  return (
    <div style={styles.container}>
      {/* Main TIHR ring */}
      <div style={styles.mainCard}>
        <div style={styles.ringWrapper}>
          <CircularProgress pct={simPct} size={160} stroke={12} />
          <div style={styles.ringLabel}>
            <span style={styles.pctValue}>{simPct.toFixed(1)}</span>
            <span style={styles.pctSign}>%</span>
          </div>
        </div>
        <div style={styles.mainInfo}>
          <h2 style={styles.mainTitle}>Time in Healthy Range</h2>
          <p style={styles.mainSub}>
            All metrics simultaneously within safe limits
          </p>
          <p style={styles.readings}>
            {tihr.simultaneous_in_range} / {tihr.total_readings} readings
          </p>
        </div>
      </div>

      {/* Per-metric mini cards */}
      <div style={styles.metricsRow}>
        {Object.entries(tihr.per_metric).map(([key, data]) => {
          const cfg = METRIC_CONFIG[key];
          if (!cfg) return null;
          const Icon = cfg.icon;

          return (
            <div key={key} style={styles.metricCard}>
              <div style={{ ...styles.iconCircle, background: cfg.bg }}>
                <Icon size={18} color={cfg.color} />
              </div>
              <div>
                <p style={styles.metricLabel}>{cfg.label}</p>
                <p style={styles.metricPct}>{data.tihr_pct}%</p>
                <p style={styles.metricRange}>{data.healthy_range}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  mainCard: {
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    padding: "32px",
    display: "flex",
    alignItems: "center",
    gap: 32,
    boxShadow: "var(--shadow-md)",
  },
  ringWrapper: {
    position: "relative",
    flexShrink: 0,
    width: 160,
    height: 160,
  },
  ringLabel: {
    position: "absolute",
    top: "50%",
    left: "50%",
    transform: "translate(-50%, -50%) rotate(0deg)",
    display: "flex",
    alignItems: "baseline",
    gap: 2,
  },
  pctValue: {
    fontSize: 36,
    fontWeight: 700,
    color: "var(--text-primary)",
  },
  pctSign: {
    fontSize: 18,
    fontWeight: 500,
    color: "var(--text-muted)",
  },
  mainInfo: {
    textAlign: "left",
  },
  mainTitle: {
    fontSize: 22,
    fontWeight: 600,
    color: "var(--text-primary)",
    marginBottom: 6,
  },
  mainSub: {
    fontSize: 14,
    color: "var(--text-secondary)",
    marginBottom: 8,
  },
  readings: {
    fontSize: 13,
    color: "var(--text-muted)",
    fontWeight: 500,
  },
  metricsRow: {
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: 12,
  },
  metricCard: {
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    padding: "16px",
    display: "flex",
    alignItems: "center",
    gap: 12,
    boxShadow: "var(--shadow-sm)",
  },
  iconCircle: {
    width: 38,
    height: 38,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  metricLabel: {
    fontSize: 12,
    color: "var(--text-muted)",
    fontWeight: 500,
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  metricPct: {
    fontSize: 20,
    fontWeight: 700,
    color: "var(--text-primary)",
    lineHeight: 1.2,
  },
  metricRange: {
    fontSize: 12,
    color: "var(--text-secondary)",
  },
};
