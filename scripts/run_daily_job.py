from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import load_settings, project_path
from src.utils.dates import yyyymmdd
from src.fetchers.tushare_fetcher import TushareFetcher


def safe_console_text(value: str, encoding: str | None = None) -> str:
    """Keep a completed job from failing while writing Unicode to a GBK console."""
    target_encoding = encoding or sys.stdout.encoding or "utf-8"
    return value.encode(target_encoding, errors="backslashreplace").decode(target_encoding)


def print_process_output(value: str, *, stream: object | None = None) -> None:
    output_stream = stream or sys.stdout
    text = safe_console_text(value, getattr(output_stream, "encoding", None))
    print(text, end="" if text.endswith("\n") else "\n", file=output_stream)


def find_missing_snapshot_dates(
    settings: dict,
    end_date: str,
    *,
    lookback_days: int,
    processed_dir: Path | None = None,
    fetcher: TushareFetcher | None = None,
) -> list[str]:
    """Return recent trading dates without a completed rotation-score snapshot."""
    end = datetime.strptime(end_date, "%Y%m%d").date()
    start = end - timedelta(days=lookback_days)
    output_dir = processed_dir or project_path(settings["paths"].get("processed_data_dir", "data/processed"))
    source = fetcher or TushareFetcher(**settings["data_sources"]["tushare"])
    calendar = source.trade_cal(yyyymmdd(start), yyyymmdd(end - timedelta(days=1)))
    if calendar.empty or not {"cal_date", "is_open"}.issubset(calendar.columns):
        return []
    dates = calendar.copy()
    dates["cal_date"] = dates["cal_date"].astype(str).str.zfill(8)
    dates["is_open"] = pd.to_numeric(dates["is_open"], errors="coerce").fillna(0).astype(int)
    return [
        trade_date
        for trade_date in dates.loc[dates["is_open"].eq(1), "cal_date"].tolist()
        if not (output_dir / f"rotation_scores_{trade_date}.csv").exists()
    ]


def run_daily_command(
    command: list[str],
    *,
    job_log: Path,
    max_retries: int,
    retry_delay: int,
) -> subprocess.CompletedProcess[str] | None:
    last_result: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, max_retries + 2):
        started_at = datetime.now()
        last_result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        finished_at = datetime.now()
        append_scheduler_log(
            job_log,
            started_at=started_at,
            finished_at=finished_at,
            attempt=attempt,
            max_retries=max_retries,
            return_code=last_result.returncode,
            stdout=last_result.stdout,
            stderr=last_result.stderr,
        )
        if last_result.returncode == 0 or attempt > max_retries:
            return last_result
        time.sleep(retry_delay)
    return last_result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the sector rotation daily job with retry.")
    parser.add_argument("--date", dest="end_date", default=yyyymmdd(date.today()), help="End date in YYYYMMDD.")
    parser.add_argument("--refresh", action="store_true", help="Pass --refresh to daily_run.py.")
    parser.add_argument("--max-retries", type=int, default=None, help="Override retry count.")
    parser.add_argument("--retry-delay", type=int, default=None, help="Override retry delay seconds.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings()
    automation = settings.get("automation", {})
    max_retries = args.max_retries if args.max_retries is not None else int(automation.get("max_retries", 2))
    retry_delay = args.retry_delay if args.retry_delay is not None else int(automation.get("retry_delay_seconds", 300))
    logs_dir = project_path(settings["paths"].get("logs_dir", "data/logs"))
    logs_dir.mkdir(parents=True, exist_ok=True)
    job_log = logs_dir / "scheduler_job_log.csv"

    command = [sys.executable, str(PROJECT_ROOT / "scripts" / "daily_run.py"), "--date", args.end_date]
    if args.refresh:
        command.append("--refresh")

    lookback_days = int(automation.get("recovery_lookback_days", 7))
    try:
        missing_dates = find_missing_snapshot_dates(settings, args.end_date, lookback_days=lookback_days)
    except Exception as exc:
        print_process_output(f"Snapshot recovery check skipped: {exc}", stream=sys.stderr)
        missing_dates = []

    for missing_date in missing_dates:
        recovery_command = [sys.executable, str(PROJECT_ROOT / "scripts" / "daily_run.py"), "--date", missing_date, "--refresh"]
        recovery_result = run_daily_command(
            recovery_command,
            job_log=job_log,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
        if recovery_result is None or recovery_result.returncode != 0:
            print_process_output(f"Snapshot recovery failed for {missing_date}; continuing with {args.end_date}.", stream=sys.stderr)
        else:
            print_process_output(f"Recovered missing snapshot: {missing_date}")

    last_result = run_daily_command(
        command,
        job_log=job_log,
        max_retries=max_retries,
        retry_delay=retry_delay,
    )
    if last_result is not None and last_result.returncode == 0:
        print_process_output(last_result.stdout)
        return 0

    if last_result is not None:
        print_process_output(last_result.stdout)
        print_process_output(last_result.stderr, stream=sys.stderr)
        return last_result.returncode
    return 1


def append_scheduler_log(
    path: Path,
    *,
    started_at: datetime,
    finished_at: datetime,
    attempt: int,
    max_retries: int,
    return_code: int,
    stdout: str,
    stderr: str,
) -> None:
    row = {
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": f"{(finished_at - started_at).total_seconds():.2f}",
        "attempt": str(attempt),
        "max_retries": str(max_retries),
        "return_code": str(return_code),
        "stdout_tail": (stdout or "")[-1000:],
        "stderr_tail": (stderr or "")[-1000:],
    }
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)


if __name__ == "__main__":
    raise SystemExit(main())
