from __future__ import annotations

from bisect import bisect_right

import pandas as pd


def run_topn_rotation_backtest(
    rotation_history: pd.DataFrame,
    industry_daily: pd.DataFrame,
    *,
    top_n: int = 5,
    hold_days: int = 5,
    cost_bps: float = 10.0,
    entry_price_preference: str = "open",
    benchmark_daily: pd.DataFrame | None = None,
    max_industry_weight: float = 1.0,
    max_entry_gap: float | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if rotation_history.empty or industry_daily.empty:
        return pd.DataFrame(), pd.DataFrame()
    prices = industry_daily.copy()
    prices["trade_date"] = prices["trade_date"].astype(str)
    prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
    prices = prices.dropna(subset=["industry_name", "trade_date", "close"]).drop_duplicates(["industry_name", "trade_date"], keep="last")
    close_wide = prices.pivot(index="trade_date", columns="industry_name", values="close").sort_index()
    entry_field = "open" if entry_price_preference == "open" and "open" in prices.columns and pd.to_numeric(prices["open"], errors="coerce").notna().any() else "close"
    if entry_field == "open":
        prices["open"] = pd.to_numeric(prices["open"], errors="coerce")
        entry_wide = prices.pivot(index="trade_date", columns="industry_name", values="open").sort_index()
    else:
        entry_wide = close_wide
    price_wide = close_wide
    trade_dates = price_wide.index.astype(str).tolist()
    scores = rotation_history.copy()
    scores["snapshot_date"] = scores["snapshot_date"].astype(str)
    trades = []
    previous_selected: set[str] = set()
    benchmark = _prepare_benchmark(benchmark_daily, entry_price_preference)
    for snapshot_date, group in scores.groupby("snapshot_date"):
        selected = group.sort_values("rank").head(top_n)["industry_name"].dropna().astype(str).tolist()
        # The score includes the snapshot close.  Entering at that same close
        # would use information unavailable at execution time, so entry starts
        # on the next trading day.
        entry_position = bisect_right(trade_dates, snapshot_date)
        exit_position = entry_position + hold_days
        if exit_position >= len(trade_dates):
            continue
        entry_date = trade_dates[entry_position]
        exit_date = trade_dates[exit_position]
        entry_prices = entry_wide.loc[entry_date].reindex(price_wide.columns)
        close_entry_prices = close_wide.loc[entry_date]
        exit_prices = close_wide.loc[exit_date]
        available = [industry for industry in selected if industry in price_wide.columns]
        selected_entry = entry_prices[available].fillna(close_entry_prices[available])
        constrained_out: list[str] = []
        if max_entry_gap is not None and entry_field == "open" and entry_position > 0:
            prior_close = close_wide.loc[trade_dates[entry_position - 1], available]
            entry_gap = selected_entry / prior_close - 1
            constrained_out = entry_gap[entry_gap > max_entry_gap].index.astype(str).tolist()
            available = [industry for industry in available if industry not in constrained_out]
            selected_entry = selected_entry.reindex(available)
        selected_returns = (exit_prices[available] / selected_entry - 1).replace([float("inf"), -float("inf")], pd.NA).dropna()
        returns = selected_returns.tolist()
        benchmark_entry = entry_prices.fillna(close_entry_prices)
        benchmark_returns = (exit_prices / benchmark_entry - 1).replace([float("inf"), -float("inf")], pd.NA).dropna().tolist()
        if not returns:
            continue
        selected_set = set(selected_returns.index.astype(str).tolist())
        turnover = 1.0 if not previous_selected else 1 - len(previous_selected.intersection(selected_set)) / max(len(previous_selected), len(selected_set))
        invested_weight = min(1.0, len(selected_returns) * max_industry_weight)
        external_benchmark_return = _benchmark_return(benchmark, entry_date, exit_date)
        gross_return = float(selected_returns.mean()) * invested_weight
        cost = turnover * float(cost_bps) / 10_000
        trades.append(
            {
                "snapshot_date": snapshot_date,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "top_n": top_n,
                "hold_days": hold_days,
                "industry_count": len(selected_returns),
                "selected_industries": ",".join(selected_returns.index.astype(str).tolist()),
                "entry_price_source": "next_open" if entry_field == "open" and entry_prices[available].notna().all() else "next_close_fallback",
                "constrained_exclusions": ",".join(constrained_out) if constrained_out else "无",
                "turnover": turnover,
                "invested_weight": invested_weight,
                "gross_return": gross_return,
                "cost": cost,
                "period_return": gross_return - cost,
                "industry_equal_weight_return": float(pd.Series(benchmark_returns).mean()) if benchmark_returns else pd.NA,
                "benchmark_return": external_benchmark_return,
            }
        )
        previous_selected = selected_set
    trades_df = pd.DataFrame(trades)
    if trades_df.empty:
        return trades_df, pd.DataFrame()
    trades_df["equity_curve"] = (1 + trades_df["period_return"]).cumprod()
    summary = pd.DataFrame(
        [
            {
                "trade_count": len(trades_df),
                "win_rate": float((trades_df["period_return"] > 0).mean()),
                "avg_return": float(trades_df["period_return"].mean()),
                "total_return": float(trades_df["equity_curve"].iloc[-1] - 1),
                "max_drawdown": max_drawdown(trades_df["equity_curve"]),
                "avg_excess_return": float((trades_df["period_return"] - trades_df["industry_equal_weight_return"]).dropna().mean()) if "industry_equal_weight_return" in trades_df else pd.NA,
                "avg_benchmark_excess_return": float((trades_df["period_return"] - trades_df["benchmark_return"]).dropna().mean()) if "benchmark_return" in trades_df else pd.NA,
                "avg_turnover": float(trades_df["turnover"].mean()),
                "avg_invested_weight": float(trades_df["invested_weight"].mean()),
                "top_n": top_n,
                "hold_days": hold_days,
                "cost_bps": cost_bps,
                "entry_price_preference": entry_price_preference,
                "max_industry_weight": max_industry_weight,
                "max_entry_gap": max_entry_gap,
            }
        ]
    )
    return trades_df, summary


def max_drawdown(equity_curve: pd.Series) -> float:
    curve = pd.to_numeric(equity_curve, errors="coerce").dropna()
    if curve.empty:
        return 0.0
    peak = curve.cummax()
    drawdown = curve / peak - 1
    return float(drawdown.min())


def _prepare_benchmark(raw: pd.DataFrame | None, preference: str) -> pd.DataFrame:
    if raw is None or raw.empty or not {"trade_date", "close"}.issubset(raw.columns):
        return pd.DataFrame()
    df = raw.copy()
    df["trade_date"] = df["trade_date"].astype(str)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["open"] = pd.to_numeric(df["open"], errors="coerce") if "open" in df.columns else df["close"]
    if preference != "open":
        df["open"] = df["close"]
    return df.dropna(subset=["close"]).drop_duplicates("trade_date", keep="last").set_index("trade_date").sort_index()


def _benchmark_return(benchmark: pd.DataFrame, entry_date: str, exit_date: str) -> float | pd.NA:
    if benchmark.empty or entry_date not in benchmark.index or exit_date not in benchmark.index:
        return pd.NA
    entry = benchmark.loc[entry_date, "open"]
    exit_ = benchmark.loc[exit_date, "close"]
    return float(exit_ / entry - 1) if pd.notna(entry) and entry > 0 and pd.notna(exit_) else pd.NA
