"""Backfill time-consistent margin and block-trade research summaries."""

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

from src.engines.market_structure_engine import summarize_block_trade, summarize_margin_detail
from src.engines.stock_mapping_engine import build_stock_industry_map
from src.fetchers.tushare_fetcher import TushareFetcher
from src.utils.config import load_settings, project_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill margin and block-trade research summaries.")
    parser.add_argument("--start", required=True, help="Start date in YYYYMMDD")
    parser.add_argument("--end", required=True, help="End date in YYYYMMDD")
    parser.add_argument("--output-dir", default="data/research")
    parser.add_argument("--request-interval", type=float, default=0.1)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--append", action="store_true", help="Merge this date range with existing research history")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    source = settings["data_sources"]["tushare"]
    if not os.getenv(source["token_env"]):
        raise RuntimeError(f"{source['token_env']} is required")
    fetcher = TushareFetcher(source["base_url"], source["token_env"], max(0.05, args.request_interval))
    calendar = fetcher.trade_cal(args.start, args.end)
    dates = calendar[calendar["is_open"].astype(str).eq("1")]["cal_date"].astype(str).tolist()
    overrides_path = settings.get("mapping_files", {}).get("stock_industry_overrides")
    overrides_config = load_settings(project_path(overrides_path)) if overrides_path else {}
    stock_map = build_stock_industry_map(fetcher.stock_basic(), settings.get("zt_industry_mapping_keywords", {}), overrides_config.get("overrides", {}))

    def fetch_date(trade_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        margin_frame = pd.DataFrame()
        block_frame = pd.DataFrame()
        try:
            margin = summarize_margin_detail(fetcher.margin_detail(trade_date))
            if not margin.empty:
                margin_frame = margin.groupby("trade_date", as_index=False).agg(
                        margin_balance=("rzye", "sum"),
                        margin_net_change=("net_margin_change", "sum"),
                        short_balance=("rqye", "sum"),
                        short_net_change=("net_short_change", "sum"),
                    )
        except Exception as exc:
            print(f"margin {trade_date} skipped: {exc}")
        try:
            _, block = summarize_block_trade(fetcher.block_trade(trade_date), stock_map)
            if not block.empty:
                block["trade_date"] = trade_date
                block_frame = block
        except Exception as exc:
            print(f"block trade {trade_date} skipped: {exc}")
        return margin_frame, block_frame

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        fetched = list(executor.map(fetch_date, dates))
    margin_rows = [margin for margin, _ in fetched if not margin.empty]
    block_rows = [block for _, block in fetched if not block.empty]
    output_dir = project_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_history(output_dir / "margin_market_history.csv", pd.concat(margin_rows, ignore_index=True) if margin_rows else pd.DataFrame(), ["trade_date"], args.append)
    write_history(output_dir / "block_trade_industry_history.csv", pd.concat(block_rows, ignore_index=True) if block_rows else pd.DataFrame(), ["trade_date", "mapped_industry"], args.append)
    print(f"Wrote {len(margin_rows)} margin dates and {len(block_rows)} block-trade dates to {output_dir}")


def write_history(path: Path, frame: pd.DataFrame, keys: list[str], append: bool) -> None:
    if append and path.exists() and not frame.empty:
        frame = pd.concat([pd.read_csv(path, dtype={"trade_date": str}), frame], ignore_index=True)
    if not frame.empty:
        frame.drop_duplicates(keys, keep="last").sort_values(keys).to_csv(path, index=False, encoding="utf-8-sig")
    elif not path.exists():
        pd.DataFrame().to_csv(path, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
