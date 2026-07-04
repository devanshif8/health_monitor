"""Build the synthetic patient dataset the app runs on.

Writes three things under data/:
    patients_manifest.csv        one row per patient
    patients/{id}_readings.csv   90 days of hourly vitals
    patients/{id}_forecast.csv   28-day hourly forecast

Patients fall into three risk profiles, chosen deterministically from SEED:
healthy (60%, normal + younger), at_risk (25%, mildly elevated, middle-aged),
and chronic (15%, hypertension / pre-diabetes, older). Each profile drifts
upward over the last 10 days at a different rate.

The signals are deliberately not clean sine waves. Every metric carries a
circadian swing, AR(1) noise so it drifts smoothly rather than jumping around,
glucose meal spikes, the odd exercise bump on heart rate, and an age-dependent
baseline. On top of that, realistic "dirty data" - missing cells, sensor
dropouts, outliers, the occasional typo - is layered onto the recorded history
only. The trend the forecast is built from stays clean, and the last 24h are
left untouched so the dashboard's current-vitals panel always has something to
show.
"""

import os
import shutil
import uuid

import numpy as np
import pandas as pd

N_PATIENTS = int(os.environ.get("N_PATIENTS", 1000))  # override for quick demos (e.g. Docker)
DAYS_HISTORY = 90
DAYS_FORECAST = 28
READINGS_PER_DAY = 24
TREND_START_DAY = 80  # last 10 days of history get the drift
SEED = 42

# Anchor the history so it ends at the current hour. Keeping the data current
# means a reading a doctor enters "now" lines up with the end of the history,
# instead of landing months after it and collapsing the dashboard's rolling
# windows. Values are still deterministic (SEED); only the dates float.
HISTORY_END = pd.Timestamp.now().floor("h")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PATIENTS_DIR = os.path.join(DATA_DIR, "patients")
MANIFEST_FILE = os.path.join(DATA_DIR, "patients_manifest.csv")

METRICS = ["heart_rate_bpm", "systolic_bp_mmhg", "diastolic_bp_mmhg", "glucose_mg_dl"]

# Healthy ranges (must match app/models/healthy_range.py defaults)
HEALTHY = {
    "heart_rate_bpm":     (60, 100),
    "systolic_bp_mmhg":   (90, 120),
    "diastolic_bp_mmhg":  (60, 80),
    "glucose_mg_dl":      (70, 140),
}

# Physiological hard limits - a sensor never legitimately reports outside these.
CLIP = {
    "heart_rate_bpm":    (45, 150),
    "systolic_bp_mmhg":  (80, 200),
    "diastolic_bp_mmhg": (50, 130),
    "glucose_mg_dl":     (50, 300),
}

# dirty-data knobs
CLEAN_TAIL_HOURS = 24            # keep the most recent day pristine
MISSING_CELL_RATE = 0.015        # isolated NaNs, per metric per hour
N_DROPOUTS = (0, 4)              # contiguous "device disconnected" gaps per patient
DROPOUT_LEN_HOURS = (2, 12)      # length of each dropout
OUTLIER_RATE = 0.002             # motion-artifact glitches, per metric per hour
N_ENTRY_ERRORS = (0, 3)          # order-of-magnitude typos per patient

# Motion-artifact ranges: (low-glitch band, high-glitch band). Alarming but a real
# sensor could report them, so they bypass the normal clip.
OUTLIER_RANGES = {
    "heart_rate_bpm":    ((30, 44), (155, 230)),
    "systolic_bp_mmhg":  ((60, 78), (185, 235)),
    "diastolic_bp_mmhg": ((38, 48), (115, 140)),
    "glucose_mg_dl":     ((40, 55), (320, 480)),
}

FIRST_NAMES_M = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
    "Thomas", "Charles", "Christopher", "Daniel", "Matthew", "Anthony", "Mark", "Donald",
    "Steven", "Paul", "Andrew", "Joshua", "Kenneth", "Kevin", "Brian", "George", "Edward",
    "Ronald", "Timothy", "Jason", "Jeffrey", "Ryan", "Jacob", "Gary", "Nicholas", "Eric",
    "Jonathan", "Stephen", "Larry", "Justin", "Scott", "Brandon", "Frank", "Benjamin",
    "Gregory", "Samuel", "Raymond", "Patrick", "Alexander", "Jack", "Dennis", "Jerry",
    "Tyler", "Aaron", "Henry", "Adam", "Douglas", "Nathan", "Peter", "Zachary", "Kyle", "Walter",
    "Arjun", "Rohan", "Vikram", "Aditya", "Karan", "Rahul", "Vivek", "Sanjay", "Amit", "Rohit",
    "Wei", "Jian", "Hao", "Liang", "Chen", "Yusuf", "Omar", "Hassan", "Tariq", "Ibrahim",
]

FIRST_NAMES_F = [
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica",
    "Sarah", "Karen", "Lisa", "Nancy", "Betty", "Sandra", "Margaret", "Ashley", "Kimberly",
    "Emily", "Donna", "Michelle", "Carol", "Amanda", "Melissa", "Deborah", "Stephanie",
    "Rebecca", "Laura", "Sharon", "Cynthia", "Kathleen", "Amy", "Shirley", "Angela", "Helen",
    "Anna", "Brenda", "Pamela", "Nicole", "Samantha", "Katherine", "Christine", "Debra",
    "Rachel", "Catherine", "Carolyn", "Janet", "Ruth", "Maria", "Heather", "Diane",
    "Priya", "Anjali", "Kavita", "Neha", "Pooja", "Riya", "Sneha", "Divya", "Meera", "Lakshmi",
    "Mei", "Lin", "Xia", "Yan", "Hui", "Aisha", "Fatima", "Layla", "Zara", "Noor",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas",
    "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris",
    "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson", "Baker",
    "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts",
    "Patel", "Sharma", "Singh", "Kumar", "Reddy", "Gupta", "Mehta", "Iyer", "Joshi", "Verma",
    "Wang", "Li", "Zhang", "Liu", "Chen", "Yang", "Khan", "Ahmed", "Ali", "Hussain",
]


def _circadian(hours: np.ndarray) -> np.ndarray:
    """Sin curve: trough ~4 AM, peak ~4 PM. Range ≈ [-1, 1]."""
    return np.sin((hours - 10) * np.pi / 12)


def _ar1_noise(rng: np.random.Generator, n: int, std: float, phi: float = 0.6) -> np.ndarray:
    """Autocorrelated (AR(1)) noise so the series drifts smoothly instead of
    jumping around a line. Marginal std stays ≈ `std`."""
    innov = rng.normal(0, std * np.sqrt(1 - phi**2), n)
    out = np.empty(n)
    out[0] = rng.normal(0, std)
    for i in range(1, n):
        out[i] = phi * out[i - 1] + innov[i]
    return out


def _meal_spikes(hours: np.ndarray, amp: float, clear_rate: float) -> np.ndarray:
    """Post-prandial glucose bumps at breakfast (7h), lunch (13h), dinner (19h).
    `amp` scales peak height; `clear_rate` (hours) how fast it decays - larger for
    impaired glucose tolerance (at_risk / chronic)."""
    hod = hours % 24
    total = np.zeros_like(hours, dtype=float)
    for meal_h in (7, 13, 19):
        lag = (hod - (meal_h + 1))  # peak ~1 h after the meal
        total += amp * np.exp(-(lag ** 2) / (2 * clear_rate ** 2))
    return total


def _build_metric(
    rng: np.random.Generator,
    hours: np.ndarray,
    base: float,
    amplitude: float,
    noise_std: float,
    trend_per_hour: float,
    trend_start_idx: int,
    clip: tuple[float, float],
) -> np.ndarray:
    n = len(hours)
    values = base + amplitude * _circadian(hours) + _ar1_noise(rng, n, noise_std)
    if trend_per_hour != 0:
        ramp = np.arange(n) - trend_start_idx
        ramp[ramp < 0] = 0
        values += trend_per_hour * ramp
    return np.clip(values, *clip)


def _classify_risk(value: float, low: float, high: float) -> str:
    """Low (within range), Medium (slight breach), High (>20% past bound)."""
    if low <= value <= high:
        return "Low"
    pct_low = (low - value) / low if low > 0 else 0
    pct_high = (value - high) / high if high > 0 else 0
    breach = max(pct_low, pct_high)
    return "High" if breach > 0.20 else "Medium"


def _make_profile(rng: np.random.Generator, profile: str, age: int) -> dict:
    """Return per-patient baseline parameters keyed by profile and age."""
    age_drift_hr = (age - 50) * -0.05  # older patients trend slightly lower resting HR
    age_drift_bp = (age - 50) * 0.4    # systolic creeps up with age
    age_drift_glu = (age - 50) * 0.25  # mild glucose creep with age

    if profile == "healthy":
        return {
            "hr_base":   72 + age_drift_hr + rng.normal(0, 3),
            "sbp_base": 115 + age_drift_bp + rng.normal(0, 4),
            "glu_base":  92 + age_drift_glu + rng.normal(0, 4),
            "meal_amp":  22, "meal_clear": 1.3,
            "activity_hr": (12, 22),   # (prob-hours/day scaling, peak bump)
            "trend_hr":  rng.uniform(-0.005, 0.010),
            "trend_bp":  rng.uniform(-0.005, 0.010),
            "trend_glu": rng.uniform(-0.010, 0.015),
        }
    if profile == "at_risk":
        return {
            "hr_base":   80 + age_drift_hr + rng.normal(0, 3),
            "sbp_base": 125 + age_drift_bp + rng.normal(0, 5),
            "glu_base": 112 + age_drift_glu + rng.normal(0, 5),
            "meal_amp":  38, "meal_clear": 1.9,
            "activity_hr": (10, 18),
            "trend_hr":  rng.uniform(0.010, 0.030),
            "trend_bp":  rng.uniform(0.020, 0.045),
            "trend_glu": rng.uniform(0.030, 0.060),
        }
    # chronic
    return {
        "hr_base":   85 + age_drift_hr + rng.normal(0, 4),
        "sbp_base": 140 + age_drift_bp + rng.normal(0, 6),
        "glu_base": 148 + age_drift_glu + rng.normal(0, 8),
        "meal_amp":  55, "meal_clear": 2.6,
        "activity_hr": (7, 14),
        "trend_hr":  rng.uniform(0.020, 0.045),
        "trend_bp":  rng.uniform(0.040, 0.070),
        "trend_glu": rng.uniform(0.060, 0.110),
    }


def _inject_dirty_data(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Corrupt the recorded history in realistic ways. Operates in place on a copy
    and leaves the final CLEAN_TAIL_HOURS untouched."""
    n = len(df)
    protect_from = max(1, n - CLEAN_TAIL_HOURS)
    col_pos = {c: df.columns.get_loc(c) for c in METRICS}

    # 1. Isolated missing cells (brief telemetry gaps).
    for col in METRICS:
        mask = rng.random(n) < MISSING_CELL_RATE
        mask[protect_from:] = False
        df.loc[mask, col] = np.nan

    # 2. Sensor dropouts - whole device offline for a contiguous block.
    for _ in range(int(rng.integers(N_DROPOUTS[0], N_DROPOUTS[1] + 1))):
        length = int(rng.integers(DROPOUT_LEN_HOURS[0], DROPOUT_LEN_HOURS[1] + 1))
        if protect_from - length < 1:
            continue
        start = int(rng.integers(0, protect_from - length))
        for col in METRICS:
            df.iloc[start:start + length, col_pos[col]] = np.nan

    # 3. Motion-artifact outliers - rare, alarming, bypass the clip.
    for col in METRICS:
        lo_band, hi_band = OUTLIER_RANGES[col]
        mask = rng.random(n) < OUTLIER_RATE
        mask[protect_from:] = False
        for i in np.where(mask)[0]:
            band = lo_band if rng.random() < 0.5 else hi_band
            df.iat[i, col_pos[col]] = round(float(rng.uniform(*band)), 1)

    # 4. Data-entry errors - order-of-magnitude "nurse typos".
    for _ in range(int(rng.integers(N_ENTRY_ERRORS[0], N_ENTRY_ERRORS[1] + 1))):
        col = str(rng.choice(METRICS))
        i = int(rng.integers(0, protect_from))
        val = df.iat[i, col_pos[col]]
        if pd.isna(val):
            continue
        # missing decimal point (x10) or a dropped digit (/10)
        df.iat[i, col_pos[col]] = round(float(val) * (10 if rng.random() < 0.5 else 0.1), 1)

    return df


def _generate_patient(
    rng: np.random.Generator, profile_params: dict, hours: np.ndarray,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (history_df, forecast_df) for one patient."""
    n_hist = DAYS_HISTORY * READINGS_PER_DAY
    n_fcst = DAYS_FORECAST * READINGS_PER_DAY
    trend_start = TREND_START_DAY * READINGS_PER_DAY

    # clean underlying signals - the "truth" the forecast is built from
    hr = _build_metric(rng, hours, profile_params["hr_base"], 9, 2.5,
                       profile_params["trend_hr"], trend_start, CLIP["heart_rate_bpm"])
    # occasional daytime exercise: brief HR elevations
    act_scale, act_peak = profile_params["activity_hr"]
    for day in range(DAYS_HISTORY):
        if rng.random() < act_scale / 24:  # roughly a workout every couple of days
            h = day * 24 + int(rng.integers(7, 20))
            if h < n_hist:
                hr[h] = min(CLIP["heart_rate_bpm"][1], hr[h] + rng.uniform(act_peak * 0.6, act_peak))

    sbp = _build_metric(rng, hours, profile_params["sbp_base"], 6, 3,
                        profile_params["trend_bp"], trend_start, CLIP["systolic_bp_mmhg"])
    dbp = sbp * 0.6 + _ar1_noise(rng, n_hist, 2) + 5
    ramp = np.arange(n_hist) - trend_start
    ramp[ramp < 0] = 0
    dbp += 0.5 * profile_params["trend_bp"] * ramp
    dbp = np.clip(dbp, *CLIP["diastolic_bp_mmhg"])

    glu = _build_metric(rng, hours, profile_params["glu_base"], 5, 4,
                        profile_params["trend_glu"], trend_start, CLIP["glucose_mg_dl"])
    glu = glu + _meal_spikes(hours, profile_params["meal_amp"], profile_params["meal_clear"])
    glu = np.clip(glu, *CLIP["glucose_mg_dl"])

    start = HISTORY_END - pd.Timedelta(hours=n_hist - 1)
    timestamps = pd.date_range(start, periods=n_hist, freq="h")
    history = pd.DataFrame({
        "timestamp": timestamps,
        "heart_rate_bpm":    np.round(hr, 1),
        "systolic_bp_mmhg":  np.round(sbp, 1),
        "diastolic_bp_mmhg": np.round(dbp, 1),
        "glucose_mg_dl":     np.round(glu, 1),
    })

    # forecast: continue the trend past the end of the clean history
    fcst_start = timestamps[-1] + pd.Timedelta(hours=1)
    fcst_ts = pd.date_range(fcst_start, periods=n_fcst, freq="h")
    fcst_hours = np.arange(n_hist, n_hist + n_fcst)

    # Use last 168h (week) average per metric as forecast intercept,
    # then continue the late-period trend forward.
    intercept_hr = hr[-168:].mean()
    intercept_sbp = sbp[-168:].mean()
    intercept_dbp = dbp[-168:].mean()
    intercept_glu = glu[-168:].mean()

    pred_hr = intercept_hr + profile_params["trend_hr"] * np.arange(n_fcst) \
              + 9 * _circadian(fcst_hours) + rng.normal(0, 1, n_fcst)
    pred_sbp = intercept_sbp + profile_params["trend_bp"] * np.arange(n_fcst) \
               + 6 * _circadian(fcst_hours) + rng.normal(0, 1.2, n_fcst)
    pred_dbp = pred_sbp * 0.6 + 5 + rng.normal(0, 0.8, n_fcst)
    pred_glu = intercept_glu + profile_params["trend_glu"] * np.arange(n_fcst) \
               + 5 * _circadian(fcst_hours) \
               + _meal_spikes(fcst_hours, profile_params["meal_amp"], profile_params["meal_clear"]) \
               + rng.normal(0, 2.5, n_fcst)

    rows = []
    for metric_col, preds, sigma in [
        ("heart_rate_bpm",    pred_hr,  3.0),
        ("systolic_bp_mmhg",  pred_sbp, 4.0),
        ("diastolic_bp_mmhg", pred_dbp, 3.0),
        ("glucose_mg_dl",     pred_glu, 6.0),
    ]:
        low, high = HEALTHY[metric_col]
        for ts, p in zip(fcst_ts, preds):
            rows.append({
                "timestamp": ts,
                "predicted": round(float(p), 2),
                "lower_bound": round(float(p - 1.96 * sigma), 2),
                "upper_bound": round(float(p + 1.96 * sigma), 2),
                "risk_level": _classify_risk(float(p), low, high),
                "metric": metric_col,
            })
    forecast = pd.DataFrame(rows)

    # corrupt the recorded history; the forecast above stays clean
    history = _inject_dirty_data(history, rng)

    return history, forecast


def _sample_age(rng: np.random.Generator, profile: str) -> int:
    """Age correlated with profile: healthy skews young, chronic skews old."""
    if profile == "healthy":
        age = rng.triangular(20, 32, 70)
    elif profile == "at_risk":
        age = rng.triangular(35, 55, 82)
    else:  # chronic
        age = rng.triangular(48, 68, 90)
    return int(np.clip(round(age), 20, 90))


def main():
    rng = np.random.default_rng(SEED)

    # Reset patient files dir (manifest gets overwritten anyway)
    if os.path.isdir(PATIENTS_DIR):
        shutil.rmtree(PATIENTS_DIR)
    os.makedirs(PATIENTS_DIR, exist_ok=True)

    profiles = rng.choice(
        ["healthy", "at_risk", "chronic"],
        size=N_PATIENTS,
        p=[0.60, 0.25, 0.15],
    )

    n_hist = DAYS_HISTORY * READINGS_PER_DAY
    hours = np.arange(n_hist)

    used_emails: set[str] = set()
    manifest_rows = []

    for i, profile in enumerate(profiles):
        sex = "F" if rng.random() < 0.5 else "M"
        first = rng.choice(FIRST_NAMES_F if sex == "F" else FIRST_NAMES_M)
        last = rng.choice(LAST_NAMES)
        full_name = f"{first} {last}"
        age = _sample_age(rng, profile)

        # unique email
        base_email = f"{first}.{last}".lower().replace(" ", "")
        suffix = 1
        email = f"{base_email}@example.com"
        while email in used_emails:
            suffix += 1
            email = f"{base_email}{suffix}@example.com"
        used_emails.add(email)

        patient_id = uuid.uuid4()
        params = _make_profile(rng, profile, age)
        history, forecast = _generate_patient(rng, params, hours)

        history.to_csv(os.path.join(PATIENTS_DIR, f"{patient_id}_readings.csv"), index=False)
        forecast.to_csv(os.path.join(PATIENTS_DIR, f"{patient_id}_forecast.csv"), index=False)

        manifest_rows.append({
            "id": str(patient_id),
            "full_name": full_name,
            "email": email,
            "age": age,
            "sex": sex,
            "profile": profile,
        })

        if (i + 1) % 100 == 0:
            print(f"  generated {i + 1}/{N_PATIENTS}")

    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(MANIFEST_FILE, index=False)

    print(f"\nWrote manifest: {MANIFEST_FILE}  ({len(manifest)} patients)")
    print(f"Wrote per-patient files to: {PATIENTS_DIR}")
    print("\nProfile distribution:")
    print(manifest["profile"].value_counts().to_string())
    print("\nAge by profile (mean):")
    print(manifest.groupby("profile")["age"].mean().round(1).to_string())


if __name__ == "__main__":
    main()
