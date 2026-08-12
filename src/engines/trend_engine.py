from __future__ import annotations

import pandas as pd


WINDOWS = (5, 20, 60)
MA_WINDOWS = (5, 10, 20, 60)


def normalize_industry_daily(raw: pd.DataFrame, industries: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return raw
    df = raw.copy()
    df["trade_date"] = df["trade_date"].astype(str)
    for column in ["open", "high", "low", "close", "pct_change", "vol", "amount"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.merge(
        industries[["index_code", "industry_name"]],
        left_on="ts_code",
        right_on="index_code",
        how="left",
    ).drop(columns=["index_code"])


def normalize_index_daily(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["trade_date"] = df["trade_date"].astype(str)
    for column in ["open", "high", "low", "close", "pct_chg", "vol", "amount"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.sort_values("trade_date").reset_index(drop=True)


def compute_trend_scores(industry_daily: pd.DataFrame, benchmark_daily: pd.DataFrame) -> pd.DataFrame:
    if industry_daily.empty:
        return pd.DataFrame()

    benchmark = normalize_index_daily(benchmark_daily)[["trade_date", "close"]].rename(columns={"close": "benchmark_close"})
    rows = []
    for (ts_code, industry_name), group in industry_daily.groupby(["ts_code", "industry_name"], dropna=False):
        group = group.sort_values("trade_date").reset_index(drop=True)
        if group.empty:
            continue
        latest = group.iloc[-1]
        row = {
            "ts_code": ts_code,
            "industry_name": industry_name,
            "trade_date": latest["trade_date"],
            "close": latest["close"],
            "amount": latest.get("amount"),
        }
        for window in WINDOWS:
            row[f"ret_{window}d"] = _period_return(group["close"], window)
        row["ma_score"] = _ma_score(group)

        merged = group[["trade_date", "close"]].merge(benchmark, on="trade_date", how="inner")
        row["excess_20d"] = _excess_return(merged, 20)
        row["excess_60d"] = _excess_return(merged, 60)
        row["rsi_14"] = _rsi(group["close"], 14)
        row["relative_rsi_14"] = _relative_rsi(merged, 14)
        row["rsi_state"] = rsi_state(row["rsi_14"])
        row["relative_rsi_state"] = rsi_state(row["relative_rsi_14"])
        rows.append(row)

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    total_amount = result["amount"].sum(skipna=True)
    result["amount_share"] = result["amount"] / total_amount if total_amount else 0
    trend_component = (
        _rank_score(result["ret_5d"]) * 0.25
        + _rank_score(result["ret_20d"]) * 0.30
        + _rank_score(result["excess_20d"]) * 0.30
        + result["ma_score"] / 4 * 100 * 0.15
    )
    heat_component = _rank_score(result["amount_share"])
    result["price_trend_score"] = trend_component
    result["heat_score"] = heat_component
    result["trend_score"] = trend_component * 0.70 + heat_component * 0.30
    return result.sort_values("trend_score", ascending=False).reset_index(drop=True)


def build_comparison_series(industry_daily: pd.DataFrame, benchmark_daily: pd.DataFrame, industry_names: list[str]) -> pd.DataFrame:
    frames = []
    selected = industry_daily[industry_daily["industry_name"].isin(industry_names)].copy()
    for name, group in selected.groupby("industry_name"):
        group = group.sort_values("trade_date")
        if group.empty:
            continue
        base = group["close"].iloc[0]
        frame = group[["trade_date", "close"]].copy()
        frame["name"] = name
        frame["cum_return"] = group["close"] / base - 1
        frames.append(frame)

    benchmark = normalize_index_daily(benchmark_daily)
    if not benchmark.empty:
        base = benchmark["close"].iloc[0]
        frame = benchmark[["trade_date", "close"]].copy()
        frame["name"] = "沪深300"
        frame["cum_return"] = benchmark["close"] / base - 1
        frames.append(frame)

    if not frames:
        return pd.DataFrame(columns=["trade_date", "name", "close", "cum_return"])
    return pd.concat(frames, ignore_index=True)


def _period_return(close: pd.Series, window: int) -> float | None:
    close = close.dropna()
    if len(close) <= window:
        return None
    return float(close.iloc[-1] / close.iloc[-window - 1] - 1)


def _excess_return(merged: pd.DataFrame, window: int) -> float | None:
    if len(merged) <= window:
        return None
    industry_ret = merged["close"].iloc[-1] / merged["close"].iloc[-window - 1] - 1
    benchmark_ret = merged["benchmark_close"].iloc[-1] / merged["benchmark_close"].iloc[-window - 1] - 1
    return float(industry_ret - benchmark_ret)


def _ma_score(group: pd.DataFrame) -> int:
    close = group["close"]
    latest = close.iloc[-1]
    score = 0
    for window in MA_WINDOWS:
        if len(close) >= window and latest > close.rolling(window).mean().iloc[-1]:
            score += 1
    return score


def _rsi(close: pd.Series, window: int = 14) -> float | None:
    close = pd.to_numeric(close, errors="coerce").dropna()
    if len(close) <= window:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    latest_loss = loss.iloc[-1]
    latest_gain = gain.iloc[-1]
    if pd.isna(latest_gain) or pd.isna(latest_loss):
        return None
    if latest_loss == 0:
        return 100.0 if latest_gain > 0 else 50.0
    rs = latest_gain / latest_loss
    return float(100 - 100 / (1 + rs))


def _relative_rsi(merged: pd.DataFrame, window: int = 14) -> float | None:
    if len(merged) <= window:
        return None
    relative = pd.to_numeric(merged["close"], errors="coerce") / pd.to_numeric(merged["benchmark_close"], errors="coerce")
    return _rsi(relative, window)


def rsi_state(value: float | int | None) -> str:
    if pd.isna(value):
        return "缺失"
    number = float(value)
    if number >= 70:
        return "过热"
    if number >= 55:
        return "强势"
    if number >= 45:
        return "平衡"
    if number >= 30:
        return "弱势"
    return "超卖"


def _rank_score(series: pd.Series) -> pd.Series:
    return series.rank(pct=True, na_option="bottom") * 100
