import { useState } from "react";
import { Activity, Stethoscope } from "lucide-react";
import { loginDoctor, registerDoctor } from "../api";

export default function AuthPage({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const doctor =
        mode === "login"
          ? await loginDoctor({ email, password })
          : await registerDoctor({ email, full_name: fullName, password });
      onAuth(doctor);
    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  function switchMode(next) {
    setMode(next);
    setError(null);
  }

  return (
    <div style={styles.wrap}>
      <div style={styles.card}>
        <div style={styles.brand}>
          <div style={styles.logo}>
            <Activity size={22} color="#38bdf8" />
          </div>
          <div>
            <h1 style={styles.title}>Health Monitor</h1>
            <p style={styles.subtitle}>
              <Stethoscope size={13} style={{ verticalAlign: "-2px", marginRight: 4 }} />
              Doctor portal
            </p>
          </div>
        </div>

        <div style={styles.tabs}>
          <button
            type="button"
            onClick={() => switchMode("login")}
            style={{ ...styles.tab, ...(mode === "login" ? styles.tabActive : {}) }}
          >
            Sign in
          </button>
          <button
            type="button"
            onClick={() => switchMode("register")}
            style={{ ...styles.tab, ...(mode === "register" ? styles.tabActive : {}) }}
          >
            Create account
          </button>
        </div>

        <form onSubmit={handleSubmit} style={styles.form}>
          {mode === "register" && (
            <label style={styles.field}>
              <span style={styles.label}>Full name</span>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Dr. Jane Doe"
                required
                style={styles.input}
              />
            </label>
          )}

          <label style={styles.field}>
            <span style={styles.label}>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@clinic.com"
              required
              style={styles.input}
            />
          </label>

          <label style={styles.field}>
            <span style={styles.label}>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === "register" ? "At least 6 characters" : "••••••••"}
              required
              minLength={6}
              style={styles.input}
            />
          </label>

          {error && <div style={styles.error}>{error}</div>}

          <button type="submit" disabled={busy} style={styles.submit}>
            {busy
              ? mode === "login"
                ? "Signing in..."
                : "Creating account..."
              : mode === "login"
              ? "Sign in"
              : "Create account"}
          </button>
        </form>

        <p style={styles.footer}>
          {mode === "login" ? (
            <>
              No account?{" "}
              <button type="button" onClick={() => switchMode("register")} style={styles.link}>
                Create one
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button type="button" onClick={() => switchMode("login")} style={styles.link}>
                Sign in
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}

const styles = {
  wrap: {
    minHeight: "calc(100vh - 64px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 16,
  },
  card: {
    width: "100%",
    maxWidth: 420,
    background: "white",
    border: "1px solid var(--border)",
    borderRadius: 16,
    padding: 32,
    boxShadow: "0 4px 24px rgba(15, 23, 42, 0.06)",
  },
  brand: {
    display: "flex",
    alignItems: "center",
    gap: 14,
    marginBottom: 24,
  },
  logo: {
    width: 44,
    height: 44,
    borderRadius: 12,
    background: "var(--blue-soft)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  title: {
    fontSize: 20,
    fontWeight: 700,
    color: "var(--text-primary)",
    margin: 0,
    lineHeight: 1.2,
  },
  subtitle: {
    fontSize: 13,
    color: "var(--text-muted)",
    margin: "2px 0 0 0",
  },
  tabs: {
    display: "flex",
    gap: 4,
    background: "var(--border-light)",
    borderRadius: 10,
    padding: 3,
    marginBottom: 20,
  },
  tab: {
    flex: 1,
    border: "none",
    background: "transparent",
    padding: "8px 14px",
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 500,
    color: "var(--text-secondary)",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  tabActive: {
    background: "white",
    color: "var(--text-primary)",
    boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: 14,
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
  input: {
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: "10px 12px",
    fontSize: 14,
    color: "var(--text-primary)",
    background: "white",
    outline: "none",
    transition: "border-color 0.15s",
  },
  error: {
    background: "var(--red-soft)",
    border: "1px solid var(--red-mid)",
    borderRadius: 8,
    padding: "10px 12px",
    color: "#be123c",
    fontSize: 13,
  },
  submit: {
    marginTop: 4,
    border: "none",
    background: "var(--blue-accent, #38bdf8)",
    color: "white",
    fontWeight: 600,
    fontSize: 14,
    padding: "11px 14px",
    borderRadius: 10,
    cursor: "pointer",
    transition: "opacity 0.15s",
  },
  footer: {
    marginTop: 18,
    textAlign: "center",
    fontSize: 13,
    color: "var(--text-muted)",
  },
  link: {
    border: "none",
    background: "transparent",
    color: "var(--blue-accent, #38bdf8)",
    fontWeight: 600,
    fontSize: 13,
    cursor: "pointer",
    padding: 0,
  },
};
