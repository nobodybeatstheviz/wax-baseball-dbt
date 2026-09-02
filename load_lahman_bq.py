"""Load the Lahman tables the dbt project declares as sources into BigQuery.

The SABR Lahman CSVs are not kept in any repo (ruled 2026-09-02 — the engines
hold the data and SABR republishes each winter). Download the bundle from
https://sabr.org/lahman-database/, unzip to ~/Downloads/lahman_1871-2025_csv
(or set LAHMAN_DIR), and verify against the release pin
wax-system/wax-baseball/lahman-2025/MANIFEST.sha256 (`sha256sum -c` inside the
dir). This script places the two tables the semantic layer needs — People (the
retroID bridge to Retrosheet ids) and HallOfFame — into the `lahman` dataset.
Rerunnable: each load is --replace, so a refreshed Lahman drop just reruns this.

NOTE: the CI docs pipeline reads every source dataset as the
dbt-docs-publisher service account. The lahman dataset carries a READER
grant for it (added 2026-08-31 after the first post-Lahman docs run failed
on lahman.INFORMATION_SCHEMA). If this dataset is ever dropped and
recreated, re-grant via the legacy ACL pattern in
wax-system/wax-baseball/baseball-dbt-learning-doc.md (bq add-iam-policy-binding
is allowlist-gated on this project).

Usage:  py load_lahman_bq.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

BQ = shutil.which("bq") or sys.exit("bq CLI not found on PATH")
PROJECT = "augmented-world-262319"
DATASET = "lahman"
SABR_URL = "https://sabr.org/lahman-database/"
MANIFEST = r"wax-system\wax-baseball\lahman-2025\MANIFEST.sha256"
SOURCE_DIR = Path(os.environ.get("LAHMAN_DIR") or Path.home() / "Downloads" / "lahman_1871-2025_csv")
if not SOURCE_DIR.is_dir():
    sys.exit(
        f"Lahman CSVs not found at {SOURCE_DIR}. Download the bundle from {SABR_URL}, unzip it there "
        f"(or set LAHMAN_DIR), and verify with `sha256sum -c` against {MANIFEST} before loading."
    )

# CSV file -> BigQuery table. Extend here if the semantic layer ever needs more
# of the 27 tables; Batting/Pitching stay in Snowflake/Databricks (full Lahman
# lives there) unless a BigQuery metric actually calls for them.
TABLES = {
    "People.csv": "people",
    "HallOfFame.csv": "hall_of_fame",
}


def run(cmd: list[str]) -> None:
    print(">", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"FAILED: {result.stderr.strip()}")
    if result.stdout.strip():
        print(result.stdout.strip())


def main() -> None:
    for csv in TABLES:
        if not (SOURCE_DIR / csv).exists():
            sys.exit(f"Missing source file: {SOURCE_DIR / csv}")

    # Idempotent dataset create (bq mk fails politely if it exists; ignore that).
    subprocess.run(
        [BQ, "mk", "--dataset",
         "--description", "SABR Lahman 2025 (CC BY-SA) - loaded by load_lahman_bq.py from wax-system's pinned copy",
         f"{PROJECT}:{DATASET}"],
        capture_output=True, text=True,
    )

    for csv, table in TABLES.items():
        run([
            BQ, "load", "--replace",
            "--source_format=CSV", "--autodetect", "--skip_leading_rows=1",
            f"{PROJECT}:{DATASET}.{table}",
            str(SOURCE_DIR / csv),
        ])
        run([BQ, "query", "--use_legacy_sql=false", "--format=csv",
             f"SELECT COUNT(*) AS n FROM `{PROJECT}.{DATASET}.{table}`"])

    print("done")


if __name__ == "__main__":
    main()
