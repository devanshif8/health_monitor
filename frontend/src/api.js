const BASE = "/api";
const TOKEN_KEY = "hm_token";
const DOCTOR_KEY = "hm_doctor";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredDoctor() {
  const raw = localStorage.getItem(DOCTOR_KEY);
  return raw ? JSON.parse(raw) : null;
}

function saveAuth(token, doctor) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(DOCTOR_KEY, JSON.stringify(doctor));
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(DOCTOR_KEY);
}

async function authedFetch(url, opts = {}) {
  const token = getToken();
  const headers = { ...(opts.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(url, { ...opts, headers });

  // A 401 on an authenticated call means the token is missing, expired, or
  // points at a doctor that no longer exists. Drop it and send the user back
  // to the login screen instead of leaving the app wedged on a stale session.
  if (res.status === 401 && token) {
    logout();
    window.location.reload();
  }
  return res;
}

async function jsonOrThrow(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data?.detail || `Request failed (${res.status})`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

export async function registerDoctor({ email, full_name, password }) {
  const res = await fetch(`${BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, full_name, password }),
  });
  const data = await jsonOrThrow(res);
  saveAuth(data.access_token, data.doctor);
  return data.doctor;
}

export async function loginDoctor({ email, password }) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await jsonOrThrow(res);
  saveAuth(data.access_token, data.doctor);
  return data.doctor;
}

export async function fetchPatients() {
  const res = await authedFetch(`${BASE}/patients/`);
  return jsonOrThrow(res);
}

export async function createQuickReading(patientId, payload) {
  const res = await authedFetch(`${BASE}/patients/${patientId}/readings/quick`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return jsonOrThrow(res);
}

export async function fetchHistorical(patientId, lastDays = 30) {
  const res = await authedFetch(
    `${BASE}/dashboard/historical?patient_id=${patientId}&last_days=${lastDays}`
  );
  return jsonOrThrow(res);
}

export async function fetchForecast(patientId) {
  const res = await authedFetch(`${BASE}/dashboard/forecast-data?patient_id=${patientId}`);
  return jsonOrThrow(res);
}

export async function fetchTIHR(patientId, lastDays = 30) {
  const res = await authedFetch(
    `${BASE}/dashboard/tihr?patient_id=${patientId}&last_days=${lastDays}`
  );
  return jsonOrThrow(res);
}

export async function fetchModelPerformance() {
  const res = await authedFetch(`${BASE}/dashboard/model-performance`);
  return jsonOrThrow(res);
}

export async function fetchHealthyRanges(patientId) {
  const res = await authedFetch(`${BASE}/patients/${patientId}/healthy-ranges`);
  return jsonOrThrow(res);
}

export async function updateHealthyRanges(patientId, payload) {
  const res = await authedFetch(`${BASE}/patients/${patientId}/healthy-ranges`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return jsonOrThrow(res);
}
