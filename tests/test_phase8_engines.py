import pandas as pd

from src.engines.candidate_engine import build_event_candidate_pool
from src.engines.portfolio_engine import build_portfolio_plan


def test_portfolio_plan_caps_industry_weights_and_keeps_cash():
    scores = pd.DataFrame(
        [
            {"industry_name": "电子", "rotation_score": 100, "data_confidence": 1, "signal_state": "趋势确认", "risk_flags": "无"},
            {"industry_name": "通信", "rotation_score": 80, "data_confidence": 1, "signal_state": "趋势启动", "risk_flags": "无"},
        ]
    )
    plan, _, metrics = build_portfolio_plan(scores, {"科技": ["电子", "通信"]}, max_industry_weight=0.25, max_positions=2)
    assert len(plan) == 2
    assert plan["suggested_weight"].max() <= 0.25
    assert metrics["cash_weight"] >= 0.5


def test_portfolio_plan_fills_extra_slots_with_zero_weight_watch_candidates():
    scores = pd.DataFrame(
        [
            {"industry_name": "电子", "rotation_score": 100, "data_confidence": 1, "signal_state": "趋势确认", "risk_flags": "无"},
            {"industry_name": "通信", "rotation_score": 80, "data_confidence": 1, "signal_state": "观察等待", "risk_flags": "无"},
            {"industry_name": "医药", "rotation_score": 70, "data_confidence": 1, "signal_state": "观察等待", "risk_flags": "无"},
        ]
    )

    plan, _, _ = build_portfolio_plan(scores, {}, max_positions=3)

    assert len(plan) == 3
    assert (plan.loc[plan["portfolio_role"].eq("观察候选"), "suggested_weight"] == 0).all()


def test_candidate_pool_uses_events_inside_top_industries():
    scores = pd.DataFrame([{"industry_name": "电子", "rotation_score": 90}])
    stock_map = pd.DataFrame([{"ts_code": "000001.SZ", "name": "样本", "mapped_industry": "电子"}])
    basic = pd.DataFrame([{"ts_code": "000001.SZ", "pe_ttm": 20, "pb": 2, "total_mv": 1000}])
    zt = pd.DataFrame([{"ts_code": "000001.SZ", "seal_amount": 100}])
    result = build_event_candidate_pool(scores, stock_map, basic, zt)
    assert result.iloc[0]["mapped_industry"] == "电子"
    assert "涨停" in result.iloc[0]["event_tags"]


def test_candidate_pool_can_cover_all_industries():
    scores = pd.DataFrame([{"industry_name": "电子", "rotation_score": 90}, {"industry_name": "通信", "rotation_score": 80}])
    stock_map = pd.DataFrame([{"ts_code": "000001.SZ", "name": "样本A", "mapped_industry": "电子"}, {"ts_code": "000002.SZ", "name": "样本B", "mapped_industry": "通信"}])

    result = build_event_candidate_pool(scores, stock_map, pd.DataFrame(), top_industries=None)

    assert set(result["mapped_industry"]) == {"电子", "通信"}
