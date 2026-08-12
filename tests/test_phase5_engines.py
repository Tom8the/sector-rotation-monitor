import pandas as pd

from src.engines.backtest_engine import run_topn_rotation_backtest
from src.engines.market_structure_engine import summarize_margin_detail
from src.engines.risk_engine import build_rotation_signals


def test_risk_signals_mark_confirmation_and_overheat():
    scores = pd.DataFrame(
        [{"industry_name": "电子", "price_trend_score": 85, "heat_score": 70, "etf_score": 60, "sentiment_score": 95, "excess_20d": 0.05, "rsi_14": 76, "relative_rsi_14": 65}]
    )
    result = build_rotation_signals(scores)
    assert result.iloc[0]["signal_state"] == "趋势启动"
    assert "技术过热" in result.iloc[0]["risk_flags"]
    assert "情绪拥挤" in result.iloc[0]["risk_flags"]


def test_backtest_enters_after_snapshot_and_deducts_cost():
    scores = pd.DataFrame([{"snapshot_date": "20240101", "rank": 1, "industry_name": "电子"}])
    prices = pd.DataFrame(
        [
            {"trade_date": "20240101", "industry_name": "电子", "close": 10},
            {"trade_date": "20240102", "industry_name": "电子", "close": 11},
            {"trade_date": "20240103", "industry_name": "电子", "close": 12},
        ]
    )
    trades, _ = run_topn_rotation_backtest(scores, prices, top_n=1, hold_days=1, cost_bps=10)
    assert trades.iloc[0]["entry_date"] == "20240102"
    assert abs(trades.iloc[0]["period_return"] - (12 / 11 - 1 - 0.001)) < 1e-9


def test_backtest_prefers_next_open_when_available():
    scores = pd.DataFrame([{"snapshot_date": "20240101", "rank": 1, "industry_name": "电子"}])
    prices = pd.DataFrame(
        [
            {"trade_date": "20240101", "industry_name": "电子", "open": 10, "close": 10},
            {"trade_date": "20240102", "industry_name": "电子", "open": 11, "close": 12},
            {"trade_date": "20240103", "industry_name": "电子", "open": 13, "close": 14},
        ]
    )
    trades, _ = run_topn_rotation_backtest(scores, prices, top_n=1, hold_days=1, cost_bps=0)
    assert trades.iloc[0]["entry_price_source"] == "next_open"
    assert abs(trades.iloc[0]["period_return"] - (14 / 11 - 1)) < 1e-9


def test_backtest_tracks_turnover_cap_and_external_benchmark():
    scores = pd.DataFrame([{"snapshot_date": "20240101", "rank": 1, "industry_name": "电子"}])
    prices = pd.DataFrame(
        [
            {"trade_date": "20240101", "industry_name": "电子", "open": 10, "close": 10},
            {"trade_date": "20240102", "industry_name": "电子", "open": 10, "close": 11},
            {"trade_date": "20240103", "industry_name": "电子", "open": 11, "close": 12},
        ]
    )
    benchmark = pd.DataFrame(
        [
            {"trade_date": "20240102", "open": 100, "close": 101},
            {"trade_date": "20240103", "open": 101, "close": 102},
        ]
    )
    trades, _ = run_topn_rotation_backtest(scores, prices, top_n=1, hold_days=1, benchmark_daily=benchmark, max_industry_weight=0.25, cost_bps=0)
    assert trades.iloc[0]["turnover"] == 1
    assert trades.iloc[0]["invested_weight"] == 0.25
    assert abs(trades.iloc[0]["benchmark_return"] - 0.02) < 1e-9


def test_margin_summary_handles_missing_short_columns():
    result = summarize_margin_detail(pd.DataFrame([{"rzmre": 20, "rzche": 5}]))
    assert result.iloc[0]["net_margin_change"] == 15
    assert result.iloc[0]["net_short_change"] == 0
