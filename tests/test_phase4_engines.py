import pandas as pd

from src.engines.backtest_engine import run_topn_rotation_backtest
from src.engines.style_engine import build_style_summary


def test_build_style_summary_groups_industries():
    scores = pd.DataFrame(
        [
            {"industry_name": "电子", "rotation_score": 90.0, "ret_20d": 0.1, "excess_20d": 0.03, "heat_score": 80.0},
            {"industry_name": "通信", "rotation_score": 70.0, "ret_20d": 0.0, "excess_20d": -0.01, "heat_score": 60.0},
            {"industry_name": "银行", "rotation_score": 50.0, "ret_20d": -0.02, "excess_20d": 0.01, "heat_score": 40.0},
        ]
    )

    result = build_style_summary(scores, {"科技成长": ["电子", "通信"], "金融地产": ["银行"]})

    assert result.iloc[0]["style_name"] == "科技成长"
    assert result.iloc[0]["industry_count"] == 2
    assert result.iloc[0]["top_industry"] == "电子"


def test_run_topn_rotation_backtest_returns_trades_and_summary():
    history = pd.DataFrame(
        [
            {"snapshot_date": "20260701", "industry_name": "电子", "rank": 1},
            {"snapshot_date": "20260701", "industry_name": "银行", "rank": 2},
            {"snapshot_date": "20260702", "industry_name": "电子", "rank": 2},
            {"snapshot_date": "20260702", "industry_name": "银行", "rank": 1},
        ]
    )
    daily = pd.DataFrame(
        [
            {"trade_date": "20260701", "industry_name": "电子", "close": 100.0},
            {"trade_date": "20260702", "industry_name": "电子", "close": 110.0},
            {"trade_date": "20260703", "industry_name": "电子", "close": 121.0},
            {"trade_date": "20260701", "industry_name": "银行", "close": 100.0},
            {"trade_date": "20260702", "industry_name": "银行", "close": 90.0},
            {"trade_date": "20260703", "industry_name": "银行", "close": 99.0},
        ]
    )

    trades, summary = run_topn_rotation_backtest(history, daily, top_n=1, hold_days=1)

    # Scores are known at the snapshot close, so the final snapshot has no
    # following trading day and must not be traded.
    assert len(trades) == 1
    assert summary.iloc[0]["trade_count"] == 1
    assert summary.iloc[0]["win_rate"] == 1.0
