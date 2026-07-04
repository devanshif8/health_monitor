import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { fetchModelPerformance } from "../api";

export default function ModelPerformanceCard() {
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchModelPerformance()
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (!data || !data.validated) return null;

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <div style={styles.iconWrap}>
          <ShieldCheck size={16} color="#059669" />
        </div>
        <div>
          <p style={styles.title}>Model Performance</p>
          <p style={styles.sub}>
            {data.model} forecast validated on {data.n_patients.toLocaleString()} patients
            &nbsp;·&nbsp; {data.horizon_days}-day horizon
          </p>
        </div>
      </div>

      <div style={styles.grid}>
        {data.metrics.map((m) => (
          <div key={m.metric} style={styles.cell}>
            <p style={styles.cellLabel}>{m.label}</p>
            <p style={styles.cellValue}>
              {m.mae} <span style={styles.unit}>{m.unit}</span>
            </p>
            <p style={styles.cellSub}>
              MAPE {m.mape}% &nbsp;·&nbsp;
              <span style={styles.improvement}>+{m.improvement_pct}% vs naive</span>
            </p>
          </div>
        ))}
      </div>

      <p style={styles.footer}>
        MAE = mean absolute error on held-out 10-day window.
        Lower is better. "vs naive" compares MAPE against a last-value baseline.
      </p>
    </div>
  );
}

const styles = {
  card: {
    background: "white",
    border: "1px solid var(--border, #e2e8f0)",
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    marginBottom: 14,
  },
  iconWrap: {
    width: 32,
    height: 32,
    borderRadius: 8,
    background: "#ecfdf5",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  title: {
    fontSize: 14,
    fontWeight: 600,
    color: "var(--text-primary, #0f172a)",
    margin: 0,
  },
  sub: {
    fontSize: 12,
    color: "var(--text-muted, #64748b)",
    margin: "2px 0 0 0",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: 10,
  },
  cell: {
    background: "var(--blue-soft, #f0f9ff)",
    borderRadius: 10,
    padding: "10px 12px",
  },
  cellLabel: {
    fontSize: 11,
    fontWeight: 500,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    color: "var(--text-muted, #64748b)",
    margin: 0,
  },
  cellValue: {
    fontSize: 20,
    fontWeight: 700,
    color: "var(--text-primary, #0f172a)",
    margin: "4px 0 2px 0",
  },
  unit: {
    fontSize: 12,
    fontWeight: 500,
    color: "var(--text-muted, #64748b)",
  },
  cellSub: {
    fontSize: 11,
    color: "var(--text-muted, #64748b)",
    margin: 0,
  },
  improvement: {
    color: "#059669",
    fontWeight: 600,
  },
  footer: {
    fontSize: 11,
    color: "var(--text-muted, #64748b)",
    marginTop: 12,
    marginBottom: 0,
    lineHeight: 1.4,
  },
};
