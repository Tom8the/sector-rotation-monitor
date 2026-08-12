import pandas as pd

from src.engines.score_engine import compute_rotation_scores


def test_compute_rotation_scores_applies_component_weights_and_sorts():
    trend_scores = pd.DataFrame(
        [
            {"industry_name": "电子", "price_trend_score": 80.0, "heat_score": 90.0, "amount_share": 0.6},
            {"industry_name": "银行", "price_trend_score": 60.0, "heat_score": 50.0, "amount_share": 0.4},
        ]
    )
    etf_summary = pd.DataFrame(
        [
            {"mapped_industry": "电子", "total_amount": 200.0, "total_main_net_inflow": 20.0},
            {"mapped_industry": "银行", "total_amount": 100.0, "total_main_net_inflow": 10.0},
        ]
    )
    zt_summary = pd.DataFrame(
        [
            {"mapped_industry": "电子", "limit_up_count": 3, "max_limit_up_days": 2, "total_seal_amount": 30.0},
            {"mapped_industry": "银行", "limit_up_count": 1, "max_limit_up_days": 1, "total_seal_amount": 10.0},
        ]
    )

    result = compute_rotation_scores(trend_scores, etf_summary, zt_summary)

    assert result.iloc[0]["industry_name"] == "电子"
    assert result.iloc[0]["rotation_score"] > result.iloc[1]["rotation_score"]
    expected = 80.0 * 0.50 + 90.0 * 0.20 + 100.0 * 0.15 + 100.0 * 0.15
    assert result.iloc[0]["rotation_score"] == expected


def test_compute_rotation_scores_fills_missing_optional_sources_with_zero():
    trend_scores = pd.DataFrame([{"industry_name": "电子", "trend_score": 70.0, "amount_share": 0.5}])

    result = compute_rotation_scores(trend_scores)

    assert result.iloc[0]["price_trend_score"] == 70.0
    assert result.iloc[0]["etf_score"] == 0
    assert result.iloc[0]["sentiment_score"] == 0


def test_compute_rotation_scores_accepts_configurable_weights():
    trend_scores = pd.DataFrame(
        [
            {"industry_name": "电子", "price_trend_score": 100.0, "heat_score": 0.0, "amount_share": 0.6},
            {"industry_name": "银行", "price_trend_score": 0.0, "heat_score": 100.0, "amount_share": 0.4},
        ]
    )

    result = compute_rotation_scores(trend_scores, weights={"price_trend_score": 0.0, "heat_score": 1.0, "etf_score": 0.0, "sentiment_score": 0.0})

    assert result.iloc[0]["industry_name"] == "银行"
    assert result.iloc[0]["rotation_score"] == 100.0


def test_compute_rotation_scores_reweights_missing_etf_coverage():
    trend_scores = pd.DataFrame([{"industry_name": "电子", "price_trend_score": 80.0, "heat_score": 60.0, "amount_share": 1.0}])
    zt_summary = pd.DataFrame([{"mapped_industry": "电子", "limit_up_count": 1, "max_limit_up_days": 1, "total_seal_amount": 1.0}])

    result = compute_rotation_scores(trend_scores, etf_summary=pd.DataFrame(), zt_summary=zt_summary)

    # ETF is unavailable, therefore its 15% is excluded rather than scored as zero.
    assert result.iloc[0]["score_completeness"] == 0.85
    assert result.iloc[0]["effective_etf_score_weight"] == 0
    assert result.iloc[0]["rotation_score"] > 70
