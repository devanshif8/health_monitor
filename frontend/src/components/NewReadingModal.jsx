import { useState, useEffect } from "react";
import { X, Save } from "lucide-react";
import { createQuickReading } from "../api";

function nowLocalIsoMinutes() {
  const d = new Date();
  d.setSeconds(0, 0);
  // toISOString gives UTC; we want a value the <input type=datetime-local> accepts in local time
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function NewReadingModal({ patient, onClose, onSaved }) {
  const [recordedAt, setRecordedAt] = useState(nowLocalIsoMinutes());
  const [heartRate, setHeartRate] = useState("");
  const [systolic, setSystolic] = useState("");
  const [diastolic, setDiastolic] = useState("");
  const [glucose, setGlucose] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  // Close on Escape
  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function num(s) {
    const v = parseFloat(s);
    return Number.isFinite(v) ? v : null;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    const hr = num(heartRate);
    const sbp = num(systolic);
    const dbp = num(diastolic);
    const glu = num(glucose);

    if (hr === null && sbp === null && glu === null) {
      setError("Enter at least one metric.");
      return;
    }
    if ((sbp === null) !== (dbp === null)) {
      setError("Enter both systolic and diastolic together.");
      return;
    }

    const payload = {
      recorded_at: new Date(recordedAt).toISOString(),
      heart_rate_bpm: hr,
      systolic_bp_mmhg: sbp,
      diastolic_bp_mmhg: dbp,
      glucose_mg_dl: glu,
      notes: notes.trim() || null,
    };

    setBusy(true);
    try {
      await createQuickReading(patient.id, payload);
      onSaved();
    } catch (err) {
      setError(err.message || "Could not save reading");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={styles.backdrop} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <header style={styles.header}>
          <div>
            <h2 style={styles.title}>New reading</h2>
            <p style={styles.subtitle}>For {patient.full_name}</p>
          </div>
          <button type="button" onClick={onClose} style={styles.closeBtn} title="Close">
            <X size={18} />
          </button>
        </header>

        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.field}>
            <span style={styles.label}>Recorded at</span>
            <input
              type="datetime-local"
              value={recordedAt}
              onChange={(e) => setRecordedAt(e.target.value)}
              required
              style={styles.input}
            />
          </label>

          <label style={styles.field}>
            <span style={styles.label}>Heart rate <em style={styles.unit}>bpm</em></span>
            <input
              type="number"
              step="0.1"
              min="20"
              max="250"
              placeholder="e.g. 72"
              value={heartRate}
              onChange={(e) => setHeartRate(e.target.value)}
              style={styles.input}
            />
          </label>

          <div style={styles.row}>
            <label style={{ ...styles.field, flex: 1 }}>
              <span style={styles.label}>Systolic <em style={styles.unit}>mmHg</em></span>
              <input
                type="number"
                step="0.1"
                min="50"
                max="250"
                placeholder="e.g. 120"
                value={systolic}
                onChange={(e) => setSystolic(e.target.value)}
                style={styles.input}
              />
            </label>
            <label style={{ ...styles.field, flex: 1 }}>
              <span style={styles.label}>Diastolic <em style={styles.unit}>mmHg</em></span>
              <input
                type="number"
                step="0.1"
                min="30"
                max="160"
                placeholder="e.g. 80"
                value={diastolic}
                onChange={(e) => setDiastolic(e.target.value)}
                style={styles.input}
              />
            </label>
          </div>

          <label style={styles.field}>
            <span style={styles.label}>Glucose <em style={styles.unit}>mg/dL</em></span>
            <input
              type="number"
              step="0.1"
              min="20"
              max="600"
              placeholder="e.g. 105"
              value={glucose}
              onChange={(e) => setGlucose(e.target.value)}
              style={styles.input}
            />
          </label>

          <label style={styles.field}>
            <span style={styles.label}>Notes <em style={styles.unit}>optional</em></span>
            <textarea
              rows={2}
              maxLength={500}
              placeholder="Context, symptoms, post-meal, etc."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              style={{ ...styles.input, resize: "vertical", fontFamily: "inherit" }}
            />
          </label>

          {error && <div style={styles.error}>{error}</div>}

          <div style={styles.actions}>
            <button type="button" onClick={onClose} style={styles.cancelBtn}>
              Cancel
            </button>
            <button type="submit" disabled={busy} style={styles.saveBtn}>
              <Save size={15} />
              {busy ? "Saving..." : "Save reading"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const styles = {
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "rgba(15, 23, 42, 0.45)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 16,
    zIndex: 100,
  },
  modal: {
    width: "100%",
    maxWidth: 460,
    background: "white",
    borderRadius: 16,
    padding: 24,
    boxShadow: "0 20px 50px rgba(15, 23, 42, 0.25)",
    maxHeight: "90vh",
    overflowY: "auto",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 18,
  },
  title: {
    fontSize: 18,
    fontWeight: 700,
    color: "var(--text-primary)",
    margin: 0,
  },
  subtitle: {
    fontSize: 13,
    color: "var(--text-muted)",
    margin: "2px 0 0 0",
  },
  closeBtn: {
    border: "none",
    background: "var(--border-light, #f1f5f9)",
    width: 32,
    height: 32,
    borderRadius: 8,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    color: "var(--text-secondary)",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: 14,
  },
  row: {
    display: "flex",
    gap: 12,
  },
  field: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  label: {
    fontSize: 13,
    fontWeight: 500,
    color: "var(--text-secondary)",
  },
  unit: {
    fontStyle: "normal",
    fontWeight: 400,
    color: "var(--text-muted)",
    fontSize: 12,
    marginLeft: 4,
  },
  input: {
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: "9px 12px",
    fontSize: 14,
    color: "var(--text-primary)",
    background: "white",
    outline: "none",
  },
  error: {
    background: "var(--red-soft)",
    border: "1px solid var(--red-mid)",
    borderRadius: 8,
    padding: "10px 12px",
    color: "#be123c",
    fontSize: 13,
  },
  actions: {
    display: "flex",
    justifyContent: "flex-end",
    gap: 10,
    marginTop: 6,
  },
  cancelBtn: {
    border: "1px solid var(--border)",
    background: "white",
    padding: "9px 16px",
    borderRadius: 10,
    fontSize: 13,
    fontWeight: 500,
    color: "var(--text-secondary)",
    cursor: "pointer",
  },
  saveBtn: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    border: "none",
    background: "var(--blue-accent, #38bdf8)",
    color: "white",
    fontWeight: 600,
    fontSize: 13,
    padding: "9px 16px",
    borderRadius: 10,
    cursor: "pointer",
  },
};
