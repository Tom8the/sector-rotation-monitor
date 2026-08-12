from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


DATASET_TABLES = {
    "industry_daily": "industry_daily",
    "rotation_scores": "rotation_score_daily",
    "trend_scores": "trend_score_daily",
    "comparison_series": "comparison_series_daily",
    "etf_summary": "etf_summary_daily",
    "etf_detail": "etf_detail_daily",
    "zt_summary": "zt_summary_daily",
    "zt_detail": "zt_detail_daily",
    "valuation_summary": "valuation_summary_daily",
    "northbound_summary": "northbound_summary_daily",
    "northbound_detail": "northbound_detail_daily",
    "dragon_tiger_summary": "dragon_tiger_summary_daily",
    "dragon_tiger_detail": "dragon_tiger_detail_daily",
    "sector_flow_summary": "sector_flow_summary_daily",
    "risk_signals": "risk_signal_daily",
    "margin_summary": "margin_summary_daily",
    "block_trade_summary": "block_trade_summary_daily",
    "block_trade_detail": "block_trade_detail_daily",
    "style_index_summary": "style_index_summary_daily",
    "mapping_audit": "mapping_audit_daily",
    "candidate_pool": "candidate_pool_daily",
    "benchmark_daily": "benchmark_daily_history",
    "data_quality": "data_quality_log",
    "source_health": "source_health_log",
}


def sync_processed_outputs(db_path: str | Path, processed_dir: str | Path, snapshot_date: str) -> list[str]:
    processed = Path(processed_dir)
    written: list[str] = []
    with connect(db_path) as connection:
        for dataset, table in DATASET_TABLES.items():
            path = processed / f"{dataset}_{snapshot_date}.csv"
            if not path.exists():
                continue
            try:
                frame = pd.read_csv(path, dtype={"trade_date": str, "snapshot_date": str})
            except pd.errors.EmptyDataError:
                continue
            if frame.empty:
                continue
            write_snapshot(connection, table, frame, snapshot_date)
            written.append(table)
    return written


def write_snapshot(connection: duckdb.DuckDBPyConnection, table: str, frame: pd.DataFrame, snapshot_date: str) -> None:
    df = frame.copy()
    df["snapshot_date"] = str(snapshot_date)
    connection.register("_snapshot_frame", df)
    quoted_table = quote_identifier(table)
    snapshot_literal = sql_literal(str(snapshot_date))
    if table_exists(connection, table):
        connection.execute(
            f"""
            CREATE OR REPLACE TABLE {quoted_table} AS
            SELECT * FROM {quoted_table}
            WHERE CAST(snapshot_date AS VARCHAR) <> {snapshot_literal}
            UNION ALL BY NAME
            SELECT * FROM _snapshot_frame
            """
        )
    else:
        connection.execute(f"CREATE TABLE {quoted_table} AS SELECT * FROM _snapshot_frame")
    connection.unregister("_snapshot_frame")


def table_exists(connection: duckdb.DuckDBPyConnection, table: str) -> bool:
    rows = connection.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        [table],
    ).fetchone()
    return bool(rows and rows[0])


def read_table(db_path: str | Path, table: str) -> pd.DataFrame:
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame()
    with connect(path) as connection:
        if not table_exists(connection, table):
            return pd.DataFrame()
        return connection.execute(f"SELECT * FROM {quote_identifier(table)}").fetchdf()


def available_snapshots(db_path: str | Path, table: str = "rotation_score_daily") -> list[str]:
    path = Path(db_path)
    if not path.exists():
        return []
    with connect(path) as connection:
        if not table_exists(connection, table):
            return []
        rows = connection.execute(
            f"""
            SELECT DISTINCT CAST(snapshot_date AS VARCHAR) AS snapshot_date
            FROM {quote_identifier(table)}
            ORDER BY snapshot_date DESC
            """
        ).fetchall()
    return [str(row[0]) for row in rows]


def connect(db_path: str | Path) -> duckdb.DuckDBPyConnection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
