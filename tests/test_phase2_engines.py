from pathlib import Path

import pandas as pd

from src.engines.dragon_tiger_engine import add_limit_up_ratio, build_dragon_tiger_summary
from src.engines.northbound_engine import build_northbound_summary
from src.engines.stock_mapping_engine import build_industry_stock_counts, build_stock_industry_map
from src.engines.valuation_engine import build_industry_valuation


def test_stock_mapping_and_counts_use_keyword_map():
    stock_basic = pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "name": "A", "industry": "电气设备"},
            {"ts_code": "000002.SZ", "name": "B", "industry": "元器件"},
            {"ts_code": "000003.SZ", "name": "C", "industry": "未知"},
        ]
    )
    keyword_map = {"电力设备": ["电气设备"], "电子": ["元器件"]}

    stock_map = build_stock_industry_map(stock_basic, keyword_map)
    counts = build_industry_stock_counts(stock_map)

    assert stock_map["mapped_industry"].tolist() == ["电力设备", "电子", "未映射"]
    assert counts.set_index("mapped_industry").loc["电力设备", "stock_count"] == 1
    assert counts.set_index("mapped_industry").loc["电子", "stock_count"] == 1


def test_valuation_summary_aggregates_by_industry(tmp_path: Path):
    daily_basic = pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "pe_ttm": 10.0, "pb": 1.0, "total_mv": 100.0, "circ_mv": 80.0},
            {"ts_code": "000002.SZ", "pe_ttm": 20.0, "pb": 2.0, "total_mv": 100.0, "circ_mv": 70.0},
            {"ts_code": "000003.SZ", "pe_ttm": 30.0, "pb": 3.0, "total_mv": 100.0, "circ_mv": 60.0},
        ]
    )
    stock_map = pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "mapped_industry": "电子"},
            {"ts_code": "000002.SZ", "mapped_industry": "电子"},
            {"ts_code": "000003.SZ", "mapped_industry": "未映射"},
        ]
    )

    result = build_industry_valuation(daily_basic, stock_map, "20260708", tmp_path)

    row = result.iloc[0]
    assert row["mapped_industry"] == "电子"
    assert row["stock_count"] == 2
    assert round(row["pe_ttm"], 2) == 13.33
    assert row["valuation_state"] == "样本不足"


def test_northbound_summary_aggregates_active_amount_and_net():
    hsgt_top10 = pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "name": "A", "amount": 100.0, "net_amount": 10.0},
            {"ts_code": "000002.SZ", "name": "B", "amount": 200.0, "buy": 90.0, "sell": 50.0},
        ]
    )
    stock_map = pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "mapped_industry": "电子", "stock_industry": "元器件"},
            {"ts_code": "000002.SZ", "mapped_industry": "电子", "stock_industry": "半导体"},
        ]
    )

    detail, summary = build_northbound_summary(hsgt_top10, stock_map)

    assert len(detail) == 2
    assert summary.iloc[0]["mapped_industry"] == "电子"
    assert summary.iloc[0]["hsgt_active_amount"] == 300.0
    assert summary.iloc[0]["hsgt_net_amount"] == 50.0


def test_dragon_tiger_summary_and_limit_up_ratio():
    top_list = pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "name": "A", "amount": 100.0, "net_amount": 10.0, "l_buy": 70.0, "l_sell": 60.0},
            {"ts_code": "000002.SZ", "name": "B", "amount": 200.0, "net_amount": -5.0, "l_buy": 80.0, "l_sell": 85.0},
        ]
    )
    stock_map = pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "mapped_industry": "计算机", "stock_industry": "软件"},
            {"ts_code": "000002.SZ", "mapped_industry": "计算机", "stock_industry": "IT服务"},
        ]
    )

    _, summary = build_dragon_tiger_summary(top_list, stock_map)
    with_ratio = add_limit_up_ratio(
        pd.DataFrame([{"mapped_industry": "计算机", "limit_up_count": 2}]),
        pd.DataFrame([{"mapped_industry": "计算机", "stock_count": 100}]),
    )

    assert summary.iloc[0]["top_list_count"] == 2
    assert summary.iloc[0]["top_list_net_amount"] == 5.0
    assert with_ratio.iloc[0]["limit_up_ratio"] == 0.02
