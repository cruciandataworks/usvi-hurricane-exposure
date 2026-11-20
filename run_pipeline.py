"""Run every step in order. This is what the 3-hourly schedule calls.

    python run_pipeline.py            # full run: check NOAA and NHC, rebuild, export, alerts
    python run_pipeline.py --from 4   # skip downloading, rebuild from the lake

Step 3 (NHC's active storms) may fail - NHC's servers are busiest exactly when a storm is
coming. That is recorded (the dashboard shows it, and three failed runs in a row raise an
alert) and the rest still runs. Any failure from step 4 on stops the run, so bad data never
reaches the dashboard.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable
STEPS = [
    (1, "HURDAT2 best tracks (NOAA NHC)", [PY, "pipeline/step1_hurdat.py"], False),
    (2, "Census 2020 estates", [PY, "pipeline/step2_census.py"], False),
    (3, "Active storms (NHC)", [PY, "pipeline/step3_active.py"], True),
    (4, "Load DuckDB", [PY, "pipeline/step4_load.py"], False),
    (5, "dbt build (models + tests)", ["dbt", "build", "--profiles-dir", "."], False),
    (6, "Export dashboard data", [PY, "pipeline/step5_export.py"], False),
    (7, "Sync alert issues", [PY, "pipeline/step6_alerts.py"], False),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", type=int, default=1)
    args = ap.parse_args()
    if os.environ.get("TEST_FAILURE") == "true":
        print("TEST_FAILURE is set - failing on purpose to test the failure alert.")
        sys.exit(1)
    for n, label, cmd, tolerant in STEPS:
        if n < args.start:
            continue
        print(f"\n=== Step {n}: {label} ===", flush=True)
        cwd = ROOT / "dbt" if cmd[0] == "dbt" else ROOT
        result = subprocess.run(cmd, cwd=cwd, env=os.environ.copy())
        if result.returncode != 0:
            if tolerant:
                print(f"Step {n} failed - carrying on; the failure is recorded in source health.")
            else:
                print(f"Step {n} failed - stopping so bad data never reaches the dashboard.")
                sys.exit(result.returncode)
    print("\nAll steps finished.")


if __name__ == "__main__":
    main()
