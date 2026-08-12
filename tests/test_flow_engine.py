import pandas as pd

from src.engines.flow_engine import build_etf_mapping_quality, build_etf_observation, classify_etf


MAPPING = {
    "exclude_keywords": ["沪深300", "货币"],
    "industry_keywords": {
        "电子": ["芯片", "半导体"],
        "汽车": ["智能驾驶", "汽车"],
    },
}


def test_classify_etf_splits_industry_non_industry_and_unmapped():
    assert classify_etf("芯片ETF", MAPPING) == ("电子", "行业映射")
    assert classify_etf("沪深300ETF", MAPPING) == ("非行业ETF", "非行业")
    assert classify_etf("主题ETF", MAPPING) == ("未映射", "未映射")


def test_build_etf_observation_only_summarizes_industry_mapped_rows():
    raw = pd.DataFrame(
        [
            {"代码": "1", "名称": "芯片ETF", "涨跌幅": 2.0, "成交额": 100.0, "主力净流入-净额": 10.0, "最新份额": 1000.0},
            {"代码": "2", "名称": "智能驾驶ETF", "涨跌幅": 1.0, "成交额": 80.0, "主力净流入-净额": 5.0, "最新份额": 800.0},
            {"代码": "3", "名称": "沪深300ETF", "涨跌幅": 0.5, "成交额": 500.0, "主力净流入-净额": 20.0, "最新份额": 5000.0},
            {"代码": "4", "名称": "主题ETF", "涨跌幅": -1.0, "成交额": 20.0, "主力净流入-净额": -1.0, "最新份额": 200.0},
        ]
    )

    detail, summary = build_etf_observation(raw, MAPPING)
    quality = build_etf_mapping_quality(detail)

    assert detail["mapping_status"].tolist() == ["行业映射", "行业映射", "非行业", "未映射"]
    assert set(summary["mapped_industry"]) == {"电子", "汽车"}
    assert summary["total_amount"].sum() == 180.0
    assert set(quality["mapping_status"]) == {"行业映射", "非行业", "未映射"}
