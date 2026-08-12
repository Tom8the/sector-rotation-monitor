from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pandas as pd


ETF_HISTORY_COLUMN_MAP = {
    "日期": "trade_date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "涨跌幅": "pct_change",
    "涨跌额": "change_amount",
    "换手率": "turnover_rate",
    "pct_chg": "pct_change",
    "vol": "volume",
}


def select_representative_etfs(etf_detail: pd.DataFrame, max_per_industry: int = 1) -> pd.DataFrame:
    """Keep liquid industry ETFs as a tractable proxy for each industry."""
    if etf_detail.empty:
        return pd.DataFrame(columns=["code", "name", "mapped_industry", "amount"])
    columns = [column for column in ["code", "name", "mapped_industry", "mapping_status", "amount"] if column in etf_detail.columns]
    selected = etf_detail[columns].copy()
    if "mapping_status" in selected.columns:
        selected = selected[selected["mapping_status"].eq("行业映射")]
    selected = selected.dropna(subset=["code", "mapped_industry"])
    selected["code"] = selected["code"].map(_normalize_code)
    selected["amount"] = pd.to_numeric(selected.get("amount"), errors="coerce").fillna(0)
    return (
        selected.sort_values(["mapped_industry", "amount"], ascending=[True, False])
        .groupby("mapped_industry", as_index=False, group_keys=False)
        .head(max(1, int(max_per_industry)))
        .reset_index(drop=True)
    )


def normalize_etf_history(raw: pd.DataFrame, code: str, name: str, industry: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    frame = raw.rename(columns={key: value for key, value in ETF_HISTORY_COLUMN_MAP.items() if key in raw.columns}).copy()
    if "trade_date" not in frame.columns:
        return pd.DataFrame()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.strftime("%Y%m%d")
    for column in ["open", "close", "high", "low", "volume", "amount", "pct_change", "change_amount", "turnover_rate"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "ts_code" in raw.columns and "amount" in frame.columns:
        # Tushare fund_daily amount is reported in thousand yuan; the dashboard uses yuan.
        frame["amount"] = frame["amount"] * 1000
    if "pct_change" not in frame.columns:
        frame["pct_change"] = frame.groupby(lambda _: True)["close"].pct_change().mul(100) if "close" in frame.columns else pd.NA
    frame["code"] = _normalize_code(code)
    frame["name"] = str(name)
    frame["mapped_industry"] = str(industry)
    return frame.dropna(subset=["trade_date"]).sort_values("trade_date").reset_index(drop=True)


def update_etf_history(
    etf_detail: pd.DataFrame,
    fetch_history,
    history_path: str | Path,
    end_date: str,
    lookback_days: int = 180,
    max_per_industry: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Incrementally update representative ETF histories and aggregate by industry."""
    path = Path(history_path)
    existing = _read_history(path)
    representatives = select_representative_etfs(etf_detail, max_per_industry)
    frames: list[pd.DataFrame] = [existing] if not existing.empty else []
    errors: list[str] = []
    default_start = (pd.to_datetime(end_date) - timedelta(days=lookback_days)).strftime("%Y%m%d")

    for item in representatives.itertuples(index=False):
        old = existing[existing["code"].astype(str).eq(item.code)] if not existing.empty and "code" in existing.columns else pd.DataFrame()
        start_date = default_start
        if not old.empty and "trade_date" in old.columns:
            last_date = pd.to_datetime(old["trade_date"].max(), errors="coerce")
            if pd.notna(last_date):
                start_date = max(default_start, (last_date - timedelta(days=7)).strftime("%Y%m%d"))
        try:
            raw = fetch_history(item.code, start_date, end_date)
            normalized = normalize_etf_history(raw, item.code, item.name, item.mapped_industry)
            if not normalized.empty:
                frames.append(normalized)
        except Exception as exc:
            errors.append(f"{item.code} {item.name}: {exc}")

    if not frames:
        return pd.DataFrame(), pd.DataFrame(), errors
    detail = pd.concat(frames, ignore_index=True)
    detail["code"] = detail["code"].map(_normalize_code)
    detail = detail.drop_duplicates(["code", "trade_date"], keep="last").sort_values(["code", "trade_date"]).reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(path, index=False, encoding="utf-8-sig")
    return detail, build_industry_etf_series(detail), errors


def build_industry_etf_series(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame()
    frame = detail.copy()
    frame["pct_change"] = pd.to_numeric(frame.get("pct_change"), errors="coerce")
    frame["amount"] = pd.to_numeric(frame.get("amount"), errors="coerce").fillna(0)
    frame["daily_return"] = frame["pct_change"].div(100)
    if "close" in frame.columns:
        fallback = frame.sort_values(["code", "trade_date"]).groupby("code")["close"].pct_change()
        frame["daily_return"] = frame["daily_return"].fillna(fallback)
    series = (
        frame.groupby(["mapped_industry", "trade_date"], as_index=False)
        .agg(
            etf_count=("code", "nunique"),
            daily_return=("daily_return", "mean"),
            total_amount=("amount", "sum"),
            representative_etfs=("name", lambda values: "、".join(pd.unique(values.astype(str)))),
        )
        .sort_values(["mapped_industry", "trade_date"])
        .reset_index(drop=True)
    )
    series["daily_return"] = series["daily_return"].fillna(0)
    group = series.groupby("mapped_industry", group_keys=False)
    series["cum_return"] = group["daily_return"].transform(lambda values: (1 + values).cumprod() - 1)
    series["amount_ma_5"] = group["total_amount"].transform(lambda values: values.rolling(5, min_periods=1).mean())
    series["amount_ma_20"] = group["total_amount"].transform(lambda values: values.rolling(20, min_periods=5).mean())
    series["amount_ratio_5_20"] = series["amount_ma_5"].div(series["amount_ma_20"]).replace([float("inf"), -float("inf")], pd.NA)
    return series


def _read_history(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype={"code": str, "trade_date": str})
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _normalize_code(value: object) -> str:
    code = str(value).split(".")[0]
    return code.zfill(6) if code.isdigit() else code
