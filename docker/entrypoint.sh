#!/bin/sh
set -e

# Generate a synthetic cohort on first boot if the data volume is empty.
# N_PATIENTS defaults to 1000 but Docker sets it low for a quick demo.
if [ ! -f data/patients_manifest.csv ]; then
  echo ">> No patient data found — generating synthetic cohort (N_PATIENTS=${N_PATIENTS:-1000})..."
  python scripts/generate_synthetic_patients.py
else
  echo ">> Patient data present — skipping generation."
fi

echo ">> Starting API on :8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
