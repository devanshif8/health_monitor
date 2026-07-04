import { useState, useEffect } from "react";
import { Activity, LogOut, User, Plus, SlidersHorizontal } from "lucide-react";
import HealthChart from "./components/HealthChart";
import TIHRCard from "./components/TIHRCard";
import AuthPage from "./components/AuthPage";
import NewReadingModal from "./components/NewReadingModal";
import EditRangesModal from "./components/EditRangesModal";
import ModelPerformanceCard from "./components/ModelPerformanceCard";
import {
  fetchHistorical,
  fetchForecast,
  fetchTIHR,
  fetchPatients,
  getStoredDoctor,
  logout as logoutApi,
} from "./api";

export default function App() {
  const [doctor, setDoctor] = useState(getStoredDoctor());
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState(null);
  const [historical, setHistorical] = useState([]);
  const [forecast, setForecast] = useState([]);
  const [tihr, setTihr] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [days, setDays] = useState(30);
  const [showReadingModal, setShowReadingModal] = useState(false);
  const [showRangesModal, setShowRangesModal] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  // Load patient list once the doctor is signed in
  useEffect(() => {
    if (!doctor) return;
    let cancelled = false;
    fetchPatients()
      .then((list) => {
        if (cancelled) return;
        setPatients(list);
        if (list.length > 0) setSelectedPatientId(list[0].id);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load patient list.");
      });
    return () => {
      cancelled = true;
    };
  }, [doctor]);

  // Load patient health data whenever selection or window changes
  useEffect(() => {
    if (!doctor || !selectedPatientId) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [hist, fore, t] = await Promise.all([
          fetchHistorical(selectedPatientId, days),
          fetchForecast(selectedPatientId),
          fetchTIHR(selectedPatientId, days),
        ]);
        if (cancelled) return;
        setHistorical(hist);
        setForecast(fore);
        setTihr(t);
      } catch {
        if (!cancelled)
          setError("Could not connect to the API. Make sure the backend is running on port 8000.");
      }
      if (!cancelled) setLoading(false);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [days, doctor, selectedPatientId, reloadKey]);

  function handleLogout() {
    logoutApi();
    setDoctor(null);
    setPatients([]);
    setSelectedPatientId(null);
  }

  if (!doctor) {
    return <AuthPage onAuth={setDoctor} />;
  }

  const selectedPatient = patients.find((p) => p.id === selectedPatientId);

  return (
    <div>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <div style={styles.logo}>
            <Activity size={22} color="#38bdf8" />
          </div>
          <div>
            <h1 style={styles.headerTitle}>Health Monitor</h1>
            <p style={styles.headerSub}>Welcome, {doctor.full_name}</p>
          </div>
        </div>
        <div style={styles.headerRight}>
          <div style={styles.periodSelector}>
            {[7, 14, 30, 60, 90].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                style={{
                  ...styles.periodBtn,
                  ...(days === d ? styles.periodBtnActive : {}),
                }}
              >
                {d}d
              </button>
            ))}
          </div>
          <button onClick={handleLogout} style={styles.logoutBtn} title="Sign out">
            <LogOut size={15} />
            <span>Sign out</span>
          </button>
        </div>
      </header>

      {/* Patient bar */}
      <div style={styles.patientBar}>
        <div style={styles.patientLeft}>
          <div style={styles.patientIcon}>
            <User size={18} color="#0284c7" />
          </div>
          <div>
            <p style={styles.patientLabel}>Viewing patient</p>
            <p style={styles.patientName}>
              {selectedPatient ? selectedPatient.full_name : "—"}
            </p>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          {patients.length > 0 && (
            <select
              value={selectedPatientId || ""}
              onChange={(e) => setSelectedPatientId(e.target.value)}
              style={styles.patientSelect}
            >
              {patients.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.full_name} — {p.email}
                </option>
              ))}
            </select>
          )}
          {selectedPatient && (
            <>
              <button
                onClick={() => setShowRangesModal(true)}
                style={styles.editRangesBtn}
                title="Edit healthy ranges for this patient"
              >
                <SlidersHorizontal size={14} />
                <span>Edit ranges</span>
              </button>
              <button
                onClick={() => setShowReadingModal(true)}
                style={styles.addReadingBtn}
                title="Add a new reading for this patient"
              >
                <Plus size={15} />
                <span>Add reading</span>
              </button>
            </>
          )}
        </div>
      </div>

      {showReadingModal && selectedPatient && (
        <NewReadingModal
          patient={selectedPatient}
          onClose={() => setShowReadingModal(false)}
          onSaved={() => {
            setShowReadingModal(false);
            setReloadKey((k) => k + 1);
          }}
        />
      )}

      {showRangesModal && selectedPatient && (
        <EditRangesModal
          patient={selectedPatient}
          onClose={() => setShowRangesModal(false)}
          onSaved={() => {
            setShowRangesModal(false);
            setReloadKey((k) => k + 1);
          }}
        />
      )}

      {error && (
        <div style={styles.error}>
          <p>{error}</p>
        </div>
      )}

      {loading ? (
        <div style={styles.loading}>
          <div style={styles.spinner}></div>
          <p>Loading health data...</p>
        </div>
      ) : (
        <>
          {/* TIHR Section */}
          <section style={{ marginBottom: 24 }}>
            <TIHRCard tihr={tihr} />
          </section>

          {/* Model accuracy (backtest validation) */}
          <ModelPerformanceCard />

          {/* Charts */}
          <section>
            <h2 style={styles.sectionTitle}>Health Forecast Timeline</h2>
            <p style={styles.sectionSub}>
              Solid line = historical &nbsp;|&nbsp; Dashed line = 7-day Prophet forecast
              &nbsp;|&nbsp; Green zone = healthy range
            </p>
            <div style={styles.chartsGrid}>
              <HealthChart
                historical={historical}
                forecast={forecast}
                metricKey="heart_rate"
              />
              <HealthChart
                historical={historical}
                forecast={forecast}
                metricKey="systolic_bp"
              />
              <HealthChart
                historical={historical}
                forecast={forecast}
                metricKey="glucose"
              />
            </div>
          </section>
        </>
      )}
    </div>
  );
}

const styles = {
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 20,
    paddingBottom: 20,
    borderBottom: "1px solid var(--border)",
    gap: 16,
    flexWrap: "wrap",
  },
  headerLeft: {
    display: "flex",
    alignItems: "center",
    gap: 14,
  },
  headerRight: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  logo: {
    width: 44,
    height: 44,
    borderRadius: 12,
    background: "var(--blue-soft)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: 700,
    color: "var(--text-primary)",
    margin: 0,
    lineHeight: 1.2,
  },
  headerSub: {
    fontSize: 13,
    color: "var(--text-muted)",
    margin: 0,
  },
  patientBar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "14px 18px",
    background: "var(--blue-soft, #f0f9ff)",
    border: "1px solid var(--border, #e2e8f0)",
    borderRadius: 12,
    marginBottom: 24,
    gap: 16,
    flexWrap: "wrap",
  },
  patientLeft: {
    display: "flex",
    alignItems: "center",
    gap: 12,
  },
  patientIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    background: "white",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    border: "1px solid var(--border)",
  },
  patientLabel: {
    fontSize: 11,
    fontWeight: 500,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    color: "var(--text-muted)",
    margin: 0,
  },
  patientName: {
    fontSize: 16,
    fontWeight: 600,
    color: "var(--text-primary)",
    margin: "2px 0 0 0",
  },
  patientSelect: {
    border: "1px solid var(--border)",
    background: "white",
    borderRadius: 10,
    padding: "8px 12px",
    fontSize: 13,
    color: "var(--text-primary)",
    cursor: "pointer",
    minWidth: 220,
  },
  addReadingBtn: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    border: "none",
    background: "var(--blue-accent, #38bdf8)",
    color: "white",
    fontWeight: 600,
    fontSize: 13,
    padding: "9px 14px",
    borderRadius: 10,
    cursor: "pointer",
  },
  editRangesBtn: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    border: "1px solid var(--border)",
    background: "white",
    color: "var(--text-secondary)",
    fontWeight: 500,
    fontSize: 13,
    padding: "8px 12px",
    borderRadius: 10,
    cursor: "pointer",
  },
  periodSelector: {
    display: "flex",
    gap: 4,
    background: "var(--border-light)",
    borderRadius: 10,
    padding: 3,
  },
  periodBtn: {
    border: "none",
    background: "transparent",
    padding: "6px 14px",
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 500,
    color: "var(--text-secondary)",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  periodBtnActive: {
    background: "white",
    color: "var(--text-primary)",
    boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
  },
  logoutBtn: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    border: "1px solid var(--border)",
    background: "white",
    padding: "7px 12px",
    borderRadius: 10,
    fontSize: 13,
    fontWeight: 500,
    color: "var(--text-secondary)",
    cursor: "pointer",
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 600,
    color: "var(--text-primary)",
    marginBottom: 4,
  },
  sectionSub: {
    fontSize: 13,
    color: "var(--text-muted)",
    marginBottom: 16,
  },
  chartsGrid: {
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  error: {
    background: "var(--red-soft)",
    border: "1px solid var(--red-mid)",
    borderRadius: "var(--radius-sm)",
    padding: "16px 20px",
    marginBottom: 20,
    color: "#be123c",
    fontSize: 14,
  },
  loading: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    height: 300,
    gap: 16,
    color: "var(--text-muted)",
    fontSize: 15,
  },
  spinner: {
    width: 32,
    height: 32,
    border: "3px solid var(--border)",
    borderTopColor: "var(--blue-accent)",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
};

// Spinner keyframe
const spinnerStyle = document.createElement("style");
spinnerStyle.textContent = `@keyframes spin { to { transform: rotate(360deg); } }`;
document.head.appendChild(spinnerStyle);
