import { useState, useEffect } from "react";
import { X, Save, RotateCcw } from "lucide-react";
import { fetchHealthyRanges, updateHealthyRanges } from "../api";

const CLINICAL_DEFAULTS = {
  heart_rate:     { min: 60, max: 100 },
  blood_pressure: { min: 90, max: 120, min_secondary: 60, max_secondary: 80 },
  glucose:        { min: 70, max: 140 },
};

export default function EditRangesModal({ patient, onClose, onSaved }) {
  const [ranges, setRanges] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchHealthyRanges(patient.id)
      .then((r) => {
        if (!cancelled) {
          setRanges(r);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e.message || "Could not load ranges");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [patient.id]);

  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function setField(metric, key, value) {
    setRanges((prev) => ({
      ...prev,
      [metric]: { ...prev[metric], [key]: value === "" ? "" : parseFloat(value) },
    }));
  }

  function resetDefaults() {
    setRanges(CLINICAL_DEFAULTS);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    for (const [metric, vals] of Object.entries(ranges)) {
      const numbersOk = Object.values(vals).every((v) => Number.isFinite(v));
      if (!numbersOk) {
        setError(`All values for ${metric.replace("_", " ")} must be numeric.`);
        return;
      }
      if (vals.min >= vals.max) {
        setError(`${metric.replace("_", " ")}: min must be less than max.`);
        return;
      }
      if (metric === "blood_pressure" && vals.min_secondary >= vals.max_secondary) {
        setError("Diastolic min must be less than diastolic max.");
        return;
      }
    }

    setBusy(true);
    try {
      await updateHealthyRanges(patient.id, ranges);
      onSaved();
    } catch (err) {
      setError(err.message || "Could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={styles.backdrop} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <header style={styles.header}>
          <div>
            <h2 style={styles.title}>Edit healthy ranges</h2>
            <p style={styles.subtitle}>For {patient.full_name}</p>
          </div>
          <button type="button" onClick={onClose} style={styles.closeBtn} title="Close">
            <X size={18} />
          </button>
        </header>

        {loading ? (
          <p style={{ color: "var(--text-muted)" }}>Loading…</p>
        ) : (
          <form onSubmit={handleSubmit} style={styles.form}>
            <RangeRow
              label="Heart rate"
              unit="bpm"
              minVal={ranges.heart_rate.min}
              maxVal={ranges.heart_rate.max}
              onMin={(v) => setField("heart_rate", "min", v)}
              onMax={(v) => setField("heart_rate", "max", v)}
            />

            <RangeRow
              label="Systolic BP"
              unit="mmHg"
              minVal={ranges.blood_pressure.min}
              maxVal={ranges.blood_pressure.max}
              onMin={(v) => setField("blood_pressure", "min", v)}
              onMax={(v) => setField("blood_pressure", "max", v)}
            />

            <RangeRow
              label="Diastolic BP"
              unit="mmHg"
              minVal={ranges.blood_pressure.min_secondary}
              maxVal={ranges.blood_pressure.max_secondary}
              onMin={(v) => setField("blood_pressure", "min_secondary", v)}
              onMax={(v) => setField("blood_pressure", "max_secondary", v)}
            />

            <RangeRow
              label="Glucose"
              unit="mg/dL"
              minVal={ranges.glucose.min}
              maxVal={ranges.glucose.max}
              onMin={(v) => setField("glucose", "min", v)}
              onMax={(v) => setField("glucose", "max", v)}
            />

            {error && <div style={styles.error}>{error}</div>}

            <div style={styles.actions}>
              <button type="button" onClick={resetDefaults} style={styles.resetBtn}>
                <RotateCcw size={14} />
                Clinical defaults
              </button>
              <div style={{ display: "flex", gap: 10 }}>
                <button type="button" onClick={onClose} style={styles.cancelBtn}>
                  Cancel
                </button>
                <button type="submit" disabled={busy} style={styles.saveBtn}>
                  <Save size={15} />
                  {busy ? "Saving…" : "Save ranges"}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

function RangeRow({ label, unit, minVal, maxVal, onMin, onMax }) {
  return (
    <div style={styles.rangeRow}>
      <span style={styles.rangeLabel}>
        {label} <em style={styles.unit}>{unit}</em>
      </span>
      <div style={styles.rangeInputs}>
        <label style={styles.miniField}>
          <span style={styles.miniLabel}>min</span>
          <input
            type="number"
            step="0.1"
            value={minVal ?? ""}
            onChange={(e) => onMin(e.target.value)}
            style={styles.input}
          />
        </label>
        <span style={styles.dash}>–</span>
        <label style={styles.miniField}>
          <span style={styles.miniLabel}>max</span>
          <input
            type="number"
            step="0.1"
            value={maxVal ?? ""}
            onChange={(e) => onMax(e.target.value)}
            style={styles.input}
          />
        </label>
      </div>
    </div>
  );
}

const styles = {
  backdrop: {
    position: "fixed", inset: 0,
    background: "rgba(15, 23, 42, 0.45)",
    display: "flex", alignItems: "center", justifyContent: "center",
    padding: 16, zIndex: 100,
  },
  modal: {
    width: "100%", maxWidth: 480,
    background: "white", borderRadius: 16,
    padding: 24,
    boxShadow: "0 20px 50px rgba(15, 23, 42, 0.25)",
    maxHeight: "90vh", overflowY: "auto",
  },
  header: {
    display: "flex", justifyContent: "space-between",
    alignItems: "flex-start", marginBottom: 18,
  },
  title: { fontSize: 18, fontWeight: 700, color: "var(--text-primary)", margin: 0 },
  subtitle: { fontSize: 13, color: "var(--text-muted)", margin: "2px 0 0 0" },
  closeBtn: {
    border: "none", background: "var(--border-light, #f1f5f9)",
    width: 32, height: 32, borderRadius: 8,
    display: "flex", alignItems: "center", justifyContent: "center",
    cursor: "pointer", color: "var(--text-secondary)",
  },
  form: { display: "flex", flexDirection: "column", gap: 14 },
  rangeRow: {
    display: "flex", flexDirection: "column", gap: 6,
    paddingBottom: 12, borderBottom: "1px solid var(--border-light, #f1f5f9)",
  },
  rangeLabel: { fontSize: 13, fontWeight: 600, color: "var(--text-secondary)" },
  unit: { fontStyle: "normal", fontWeight: 400, color: "var(--text-muted)", fontSize: 12, marginLeft: 4 },
  rangeInputs: { display: "flex", alignItems: "flex-end", gap: 8 },
  miniField: { display: "flex", flexDirection: "column", gap: 4, flex: 1 },
  miniLabel: { fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" },
  dash: { color: "var(--text-muted)", paddingBottom: 9 },
  input: {
    border: "1px solid var(--border)", borderRadius: 8,
    padding: "8px 12px", fontSize: 14,
    color: "var(--text-primary)", background: "white", outline: "none",
  },
  error: {
    background: "var(--red-soft)", border: "1px solid var(--red-mid)",
    borderRadius: 8, padding: "10px 12px", color: "#be123c", fontSize: 13,
  },
  actions: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    marginTop: 6, gap: 10, flexWrap: "wrap",
  },
  resetBtn: {
    display: "inline-flex", alignItems: "center", gap: 6,
    border: "1px solid var(--border)", background: "white",
    padding: "8px 12px", borderRadius: 10,
    fontSize: 12, fontWeight: 500, color: "var(--text-secondary)",
    cursor: "pointer",
  },
  cancelBtn: {
    border: "1px solid var(--border)", background: "white",
    padding: "9px 16px", borderRadius: 10,
    fontSize: 13, fontWeight: 500, color: "var(--text-secondary)",
    cursor: "pointer",
  },
  saveBtn: {
    display: "inline-flex", alignItems: "center", gap: 6,
    border: "none", background: "var(--blue-accent, #38bdf8)",
    color: "white", fontWeight: 600, fontSize: 13,
    padding: "9px 16px", borderRadius: 10, cursor: "pointer",
  },
};
