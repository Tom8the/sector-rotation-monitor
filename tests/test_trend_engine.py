import pandas as pd
import pytest

from src.engines.trend_engine import build_comparison_series, compute_trend_scores, normalize_industry_daily, rsi_state


def _dates(count: int) -> list[str]:
    return pd.date_range("2026-01-01", periods=count, freq="D").strftime("%Y%m%d").tolist()


def test_compute_trend_scores_returns_latest_rows_and_components():
    dates = _dates(65)
    industries = pd.DataFrame(
        [
            {"index_code": "801001.SI", "industry_name": "强势行业"},
            {"index_code": "801002.SI", "industry_name": "弱势行业"},
        ]
    )
    raw = pd.DataFrame(
        [{"ts_code": "801001.SI", "trade_date": day, "close": 100 + idx, "amount": 1000 + idx} for idx, day in enumerate(dates)]
        + [{"ts_code": "801002.SI", "trade_date": day, "close": 100 - idx * 0.2, "amount": 500 + idx} for idx, day in enumerate(dates)]
    )
    benchmark = pd.DataFrame([{"trade_date": day, "close": 100 + idx * 0.3} for idx, day in enumerate(dates)])

    industry_daily = normalize_industry_daily(raw, industries)
    result = compute_trend_scores(industry_daily, benchmark)

    assert set(result["industry_name"]) == {"强势行业", "弱势行业"}
    assert result.iloc[0]["industry_name"] == "强势行业"
    assert result["trade_date"].nunique() == 1
    assert result["price_trend_score"].notna().all()
    assert result["heat_score"].notna().all()
    assert result["rsi_14"].between(0, 100).all()
    assert result["relative_rsi_14"].between(0, 100).all()
    assert result["rsi_state"].ne("缺失").all()
    assert result["relative_rsi_state"].ne("缺失").all()


def test_rsi_state_thresholds():
    assert rsi_state(75) == "过热"
    assert rsi_state(60) == "强势"
    assert rsi_state(50) == "平衡"
    assert rsi_state(35) == "弱势"
    assert rsi_state(20) == "超卖"
    assert rsi_state(None) == "缺失"


def test_build_comparison_series_includes_selected_industries_and_benchmark():
    dates = _dates(3)
    industry_daily = pd.DataFrame(
        [
            {"industry_name": "电子", "trade_date": dates[0], "close": 100},
            {"industry_name": "电子", "trade_date": dates[1], "close": 110},
            {"industry_name": "银行", "trade_date": dates[0], "close": 100},
            {"industry_name": "银行", "trade_date": dates[1], "close": 90},
        ]
    )
    benchmark = pd.DataFrame([{"trade_date": dates[0], "close": 100}, {"trade_date": dates[1], "close": 105}])

    result = build_comparison_series(industry_daily, benchmark, ["电子"])

    assert set(result["name"]) == {"电子", "沪深300"}
    electronic = result[result["name"].eq("电子")].sort_values("trade_date")
    assert electronic["cum_return"].iloc[-1] == pytest.approx(0.1)
