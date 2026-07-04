"""
Train a real Prophet forecast per patient and overwrite the synthetic
{id}_forecast.csv files the dashboard reads.

Usage:
  python scripts/train_real_forecasts.py                # all patients
  python scripts/train_real_forecasts.py --limit 10     # first 10 patients
  python scripts/train_real_forecasts.py --patient <id> # one specific patient

Uses app.services.forecaster.refit_patient_forecast so the per-patient
logic is identical to the in-app auto-retrain trigger (FastAPI
BackgroundTasks on POST /patients/{id}/readings/quick).
"""

import argparse
import os
import sys
import time

# Make `app.*` importable when running this script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from app.services.forecaster import METRICS, refit_patient_forecast

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MANIFEST_FILE = os.path.join(DATA_DIR, "patients_manifest.csv")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                        help="Only forecast the first N patients (handy for testing).")
    parser.add_argument("--patient", type=str, default=None,
                        help="Forecast one specific patient_id (UUID).")
    args = parser.parse_args()

    if not os.path.exists(MANIFEST_FILE):
        print(f"Manifest not found at {MANIFEST_FILE}")
        return 1

    manifest = pd.read_csv(MANIFEST_FILE)

    if args.patient:
        manifest = manifest[manifest["id"] == args.patient]
        if manifest.empty:
            print(f"Patient {args.patient} not in manifest")
            return 1
    elif args.limit:
        manifest = manifest.head(args.limit)

    total = len(manifest)
    print(f"Training Prophet forecasts for {total} patient(s), "
          f"{len(METRICS)} metrics each. Output -> data/patients/{{id}}_forecast.csv")

    t0 = time.time()
    done = 0
    for i, (_, row) in enumerate(manifest.iterrows(), start=1):
        pid = row["id"]
        start = time.time()
        ok = refit_patient_forecast(pid)
        elapsed = time.time() - start
        status = "ok " if ok else "FAIL"
        print(f"  [{i}/{total}] {status} {pid}  ({elapsed:.1f}s)")
        if ok:
            done += 1

    total_elapsed = time.time() - t0
    print(f"\nDone: {done}/{total} patients in {total_elapsed:.1f}s "
          f"(avg {total_elapsed/max(total,1):.1f}s/patient)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
