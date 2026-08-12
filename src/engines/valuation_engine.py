from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_industry_valuation(daily_basic: pd.DataFrame, stock_map: pd.DataFrame, trade_date: str, processed_dir: Path | None = None) -> pd.DataFrame:
    if daily_basic.empty or stock_map.empty:
        return pd.DataFrame()
    df = daily_basic.merge(stock_map[["ts_code", "mapped_industry"]], on="ts_code", how="left")
    df = df[df["mapped_industry"].notna() & df["mapped_industry"].ne("未映射")].copy()
    for column in ["pe_ttm", "pb", "total_mv", "circ_mv"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df["earnings_ttm_proxy"] = df["total_mv"] / df["pe_ttm"].where(df["pe_ttm"] > 0)
    df["book_value_proxy"] = df["total_mv"] / df["pb"].where(df["pb"] > 0)
    summary = (
        df.groupby("mapped_industry", as_index=False)
        .agg(
            stock_count=("ts_code", "nunique"),
            total_mv=("total_mv", "sum"),
            positive_earnings_proxy=("earnings_ttm_proxy", "sum"),
            book_value_proxy=("book_value_proxy", "sum"),
            median_pe_ttm=("pe_ttm", "median"),
            median_pb=("pb", "median"),
        )
    )
    summary["pe_ttm"] = summary["total_mv"] / summary["positive_earnings_proxy"].where(summary["positive_earnings_proxy"] > 0)
    summary["pb"] = summary["total_mv"] / summary["book_value_proxy"].where(summary["book_value_proxy"] > 0)
    summary["trade_date"] = trade_date
    summary = summary.drop(columns=["positive_earnings_proxy", "book_value_proxy"])
    return add_valuation_percentiles(summary, processed_dir)


def add_valuation_percentiles(current: pd.DataFrame, processed_dir: Path | None) -> pd.DataFrame:
    result = current.copy()
    if processed_dir is None:
        result["pe_percentile"] = pd.NA
        result["pb_percentile"] = pd.NA
        result["valuation_state"] = "样本不足"
        return result
    frames = []
    for path in sorted(processed_dir.glob("valuation_summary_*.csv")):
        try:
            frames.append(pd.read_csv(path, dtype={"trade_date": str}))
        except Exception:
            continue
    if frames:
        history = pd.concat(frames + [current], ignore_index=True)
    else:
        history = current.copy()
    pe_values = []
    pb_values = []
    states = []
    for row in result.itertuples(index=False):
        group = history[history["mapped_industry"].eq(row.mapped_industry)]
        pe_pct = _percentile_rank(group["pe_ttm"], row.pe_ttm)
        pb_pct = _percentile_rank(group["pb"], row.pb)
        pe_values.append(pe_pct)
        pb_values.append(pb_pct)
        states.append(_valuation_state(pe_pct, pb_pct, len(group)))
    result["pe_percentile"] = pe_values
    result["pb_percentile"] = pb_values
    result["valuation_state"] = states
    return result


def _percentile_rank(series: pd.Series, value: float) -> float | pd.NA:
    data = pd.to_numeric(series, errors="coerce").dropna()
    if pd.isna(value) or len(data) < 20:
        return pd.NA
    return float((data <= value).mean())


def _valuation_state(pe_percentile: float | pd.NA, pb_percentile: float | pd.NA, sample_count: int) -> str:
    if sample_count < 20 or pd.isna(pe_percentile) or pd.isna(pb_percentile):
        return "样本不足"
    avg = (float(pe_percentile) + float(pb_percentile)) / 2
    if avg >= 0.70:
        return "偏贵"
    if avg <= 0.30:
        return "偏低"
    return "适中"
