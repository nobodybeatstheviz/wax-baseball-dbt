"""Load the Lahman tables the dbt project declares as sources into BigQuery.

The wax-system repo holds the pinned SABR Lahman 2025 CSVs (content-hashed in
MANIFEST.sha256 after the upstream Chadwick repo was deleted). This script places
the two tables the semantic layer needs — People (the retroID bridge to
Retrosheet ids) and HallOfFame — into the `lahman` dataset. Rerunnable: each
load is --replace, so a refreshed Lahman drop just reruns this.

Usage:  py load_lahman_bq.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

BQ = shutil.which("bq") or sys.exit("bq CLI not found on PATH")
PROJECT = "augmented-world-262319"
DATASET = "lahman"
SOURCE_DIR = Path(r"C:\Users\georg\wax-system\wax-baseball\lahman-2025\lahman_1871-2025_csv")

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
