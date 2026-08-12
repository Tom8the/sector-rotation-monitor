"""Create time-consistent, price-only research snapshots for historical study.

This intentionally excludes current ETF, intraday flow, and limit-up data.  It
must not overwrite the live daily score history because those inputs cannot be
reconstructed faithfully from a current spot endpoint.
"""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.engines.score_engine import compute_rotation_scores
from src.engines.trend_engine import compute_trend_scores, normalize_industry_daily
from src.fetchers.tushare_fetcher import TushareFetcher
from src.utils.config import load_settings, project_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build price-only historical sector scores without future data.")
    parser.add_argument("--start", required=True, help="Start date in YYYYMMDD")
    parser.add_argument("--end", required=True, help="End date in YYYYMMDD")
    parser.add_argument("--output", default="data/research/price_rotation_history.csv")
    parser.add_argument("--prices-output", default="data/research/industry_daily_history.csv")
    parser.add_argument("--request-interval", type=float, default=0.1, help="Manual backfill request interval in seconds")
    parser.add_argument("--chunk-months", type=int, default=12, help="Maximum date range per provider request")
    parser.add_argument("--workers", type=int, default=3, help="Concurrent historical requests")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    source = settings["data_sources"]["tushare"]
    fetcher = TushareFetcher(source["base_url"], source["token_env"], max(0.05, args.request_interval))
    if not os.getenv(source["token_env"]):
        raise RuntimeError(f"{source['token_env']} is required")
    industries = fetcher.sw_industries(settings["market"]["sw_source"], settings["market"]["industry_level"])
    ranges = date_ranges(args.start, args.end, args.chunk_months)
    requests = [(row.index_code, range_start, range_end) for row in industries.itertuples(index=False) for range_start, range_end in ranges]
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        daily_frames = list(executor.map(lambda item: fetcher.sw_daily(*item), requests))
    industry_daily = normalize_industry_daily(pd.concat([frame for frame in daily_frames if not frame.empty], ignore_index=True), industries)
    benchmark_frames = [fetcher.index_daily(settings["market"]["benchmark_index"], range_start, range_end) for range_start, range_end in ranges]
    benchmark = pd.concat([frame for frame in benchmark_frames if not frame.empty], ignore_index=True)
    dates = sorted(industry_daily["trade_date"].astype(str).unique())
    snapshots: list[pd.DataFrame] = []
    for snapshot_date in dates:
        score = compute_trend_scores(industry_daily[industry_daily["trade_date"].astype(str).le(snapshot_date)], benchmark[benchmark["trade_date"].astype(str).le(snapshot_date)])
        if score.empty or score["ret_20d"].notna().sum() < len(score):
            continue
        score = compute_rotation_scores(score, weights={"price_trend_score": 0.7, "heat_score": 0.3, "etf_score": 0, "sentiment_score": 0})
        score["snapshot_date"] = snapshot_date
        score["research_mode"] = "price_only_time_consistent"
        snapshots.append(score)
    output = project_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(snapshots, ignore_index=True).to_csv(output, index=False, encoding="utf-8-sig") if snapshots else pd.DataFrame().to_csv(output, index=False, encoding="utf-8-sig")
    prices_output = project_path(args.prices_output)
    prices_output.parent.mkdir(parents=True, exist_ok=True)
    industry_daily.to_csv(prices_output, index=False, encoding="utf-8-sig")
    print(f"Wrote {len(snapshots)} research snapshots to {output}")


def date_ranges(start: str, end: str, chunk_months: int) -> list[tuple[str, str]]:
    ranges: list[tuple[str, str]] = []
    cursor = pd.to_datetime(start)
    final = pd.to_datetime(end)
    while cursor <= final:
        chunk_end = min(cursor + pd.DateOffset(months=max(1, chunk_months)) - pd.Timedelta(days=1), final)
        ranges.append((cursor.strftime("%Y%m%d"), chunk_end.strftime("%Y%m%d")))
        cursor = chunk_end + pd.Timedelta(days=1)
    return ranges


if __name__ == "__main__":
    main()
