import pandas as pd

from src.engines.etf_history_engine import build_industry_etf_series, normalize_etf_history, select_representative_etfs


def test_select_representative_etfs_keeps_most_liquid_per_industry():
    detail = pd.DataFrame(
        [
            {"code": "1", "name": "芯片ETF A", "mapped_industry": "电子", "mapping_status": "行业映射", "amount": 100},
            {"code": "2", "name": "芯片ETF B", "mapped_industry": "电子", "mapping_status": "行业映射", "amount": 200},
            {"code": "3", "name": "宽基ETF", "mapped_industry": "非行业ETF", "mapping_status": "非行业", "amount": 1000},
        ]
    )

    selected = select_representative_etfs(detail)

    assert selected[["code", "mapped_industry"]].to_dict("records") == [{"code": "000002", "mapped_industry": "电子"}]


def test_build_industry_etf_series_compounds_returns_and_computes_liquidity_ratio():
    raw = pd.DataFrame(
        {
            "日期": ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04", "2026-07-05"],
            "收盘": [1, 1.01, 1.00, 1.02, 1.03],
            "成交额": [100, 120, 140, 160, 180],
            "涨跌幅": [0, 1, -1, 2, 1],
        }
    )
    detail = normalize_etf_history(raw, "512000", "芯片ETF", "电子")

    series = build_industry_etf_series(detail)

    assert len(series) == 5
    assert series.iloc[-1]["cum_return"] == pytest.approx((1.01 * 0.99 * 1.02 * 1.01) - 1)
    assert series.iloc[-1]["amount_ma_5"] == 140


def test_normalize_etf_history_accepts_tushare_fund_daily_and_normalizes_amount():
    raw = pd.DataFrame({"ts_code": ["512000.SH"], "trade_date": ["20260710"], "close": [1.2], "pct_chg": [2.0], "vol": [100], "amount": [12.5]})

    detail = normalize_etf_history(raw, "512000", "ETF", "电子")

    assert detail.iloc[0]["pct_change"] == 2.0
    assert detail.iloc[0]["amount"] == 12500


import pytest
