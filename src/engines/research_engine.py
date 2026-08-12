from __future__ import annotations

from itertools import product

import pandas as pd

from src.engines.backtest_engine import run_topn_rotation_backtest
from src.engines.history_engine import enrich_rotation_history


def load_price_research_history(path: str) -> pd.DataFrame:
    try:
        frame = pd.read_csv(path, dtype={"snapshot_date": str, "trade_date": str})
    except FileNotFoundError:
        return pd.DataFrame()
    if frame.empty or "snapshot_date" not in frame.columns:
        return pd.DataFrame()
    score_column = "rotation_score" if "rotation_score" in frame.columns else "trend_score"
    if score_column not in frame.columns:
        return pd.DataFrame()
    frame["snapshot_date"] = frame["snapshot_date"].astype(str)
    frame["snapshot_display_date"] = pd.to_datetime(frame["snapshot_date"], format="%Y%m%d", errors="coerce")
    frame["history_score"] = pd.to_numeric(frame[score_column], errors="coerce")
    frame["rank"] = frame.groupby("snapshot_date")["history_score"].rank(method="first", ascending=False).astype(int)
    return enrich_rotation_history(frame)


def run_walk_forward_grid(
    history: pd.DataFrame,
    industry_daily: pd.DataFrame,
    *,
    top_n_values: list[int],
    hold_days_values: list[int],
    split_date: str,
    cost_bps: float = 10.0,
) -> pd.DataFrame:
    """Evaluate parameter sets separately before and after a fixed split date."""
    if history.empty or industry_daily.empty:
        return pd.DataFrame()
    split = str(split_date)
    rows: list[dict[str, object]] = []
    for top_n, hold_days in product(top_n_values, hold_days_values):
        trades, _ = run_topn_rotation_backtest(history, industry_daily, top_n=top_n, hold_days=hold_days, cost_bps=cost_bps)
        if trades.empty:
            continue
        train = trades[trades["snapshot_date"].astype(str).lt(split)]
        test = trades[trades["snapshot_date"].astype(str).ge(split)]
        if train.empty or test.empty:
            continue
        rows.append(
            {
                "top_n": top_n,
                "hold_days": hold_days,
                "train_trades": len(train),
                "train_avg_return": float(train["period_return"].mean()),
                "train_win_rate": float((train["period_return"] > 0).mean()),
                "test_trades": len(test),
                "test_avg_return": float(test["period_return"].mean()),
                "test_win_rate": float((test["period_return"] > 0).mean()),
                "test_total_return": float((1 + test["period_return"]).prod() - 1),
                "test_excess_return": float((test["period_return"] - test["industry_equal_weight_return"]).dropna().mean()),
                "split_date": split,
            }
        )
    return pd.DataFrame(rows).sort_values(["test_excess_return", "test_total_return"], ascending=False, na_position="last").reset_index(drop=True) if rows else pd.DataFrame()
