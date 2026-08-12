from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.history_store import sync_processed_outputs
from src.utils.config import load_settings, project_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync processed CSV outputs into DuckDB history store.")
    parser.add_argument("--date", dest="snapshot_date", default=None, help="Only sync one snapshot date in YYYYMMDD.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    processed_dir = project_path(settings["paths"]["processed_data_dir"])
    db_path = project_path(settings["paths"].get("duckdb_path", "data/sector_rotation.duckdb"))
    if args.snapshot_date:
        dates = [args.snapshot_date]
    else:
        dates = sorted(
            {
                path.stem.replace("rotation_scores_", "")
                for path in processed_dir.glob("rotation_scores_*.csv")
            }
        )
    for snapshot_date in dates:
        tables = sync_processed_outputs(db_path, processed_dir, snapshot_date)
        print(f"{snapshot_date}: synced {len(tables)} tables")
    print(f"DuckDB: {db_path}")


if __name__ == "__main__":
    main()
