"""Backfill or incrementally update representative industry ETF histories."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.data_service import DataService
from src.core.database import CsvCache
from src.engines.etf_history_engine import update_etf_history
from src.fetchers.akshare_fetcher import AkshareFetcher
from src.fetchers.tushare_fetcher import TushareFetcher
from src.utils.config import load_settings, project_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Update representative industry ETF histories.")
    parser.add_argument("--date", required=True, help="Snapshot date in YYYYMMDD; used to select ETF representatives.")
    args = parser.parse_args()
    settings = load_settings()
    processed_dir = project_path(settings["paths"]["processed_data_dir"])
    raw_dir = project_path(settings["paths"]["raw_data_dir"])
    detail_path = processed_dir / f"etf_detail_{args.date}.csv"
    if not detail_path.exists():
        raise FileNotFoundError(f"ETF snapshot not found: {detail_path}")
    etf_detail = pd.read_csv(detail_path, dtype={"code": str})
    tushare_settings = settings["data_sources"]["tushare"]
    service = DataService(
        tushare=TushareFetcher(tushare_settings["base_url"], tushare_settings["token_env"], float(tushare_settings["request_interval_seconds"])),
        akshare=AkshareFetcher(),
        cache=CsvCache(raw_dir),
    )
    options = settings.get("etf_history", {})
    detail, series, errors = update_etf_history(
        etf_detail,
        service.get_etf_history,
        project_path("data/research/etf_history_detail.csv"),
        args.date,
        int(options.get("lookback_days", 180)),
        int(options.get("max_etfs_per_industry", 1)),
    )
    if not series.empty:
        output = project_path("data/research/etf_industry_series.csv")
        series.to_csv(output, index=False, encoding="utf-8-sig")
        print(f"ETF history: {len(detail)} rows; industry series: {len(series)} rows; {output}")
    if errors:
        print(f"ETF history failures: {len(errors)}")
        for error in errors:
            print(error)


if __name__ == "__main__":
    main()
