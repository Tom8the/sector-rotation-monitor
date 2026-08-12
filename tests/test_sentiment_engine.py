import pandas as pd

from src.engines.sentiment_engine import build_zt_sentiment, map_zt_industry


KEYWORDS = {
    "计算机": ["软件", "IT服务"],
    "医药生物": ["中药"],
}


def test_map_zt_industry_matches_keywords_or_unmapped():
    assert map_zt_industry("软件开发", KEYWORDS) == "计算机"
    assert map_zt_industry("中药Ⅱ", KEYWORDS) == "医药生物"
    assert map_zt_industry("未知行业", KEYWORDS) == "未映射"


def test_build_zt_sentiment_aggregates_by_mapped_industry():
    raw = pd.DataFrame(
        [
            {"代码": "000001", "名称": "A", "成交额": 100.0, "封板资金": 10.0, "炸板次数": 1, "连板数": 2, "所属行业": "软件开发"},
            {"代码": "000002", "名称": "B", "成交额": 200.0, "封板资金": 30.0, "炸板次数": 0, "连板数": 1, "所属行业": "IT服务Ⅱ"},
            {"代码": "000003", "名称": "C", "成交额": 300.0, "封板资金": 20.0, "炸板次数": 2, "连板数": 3, "所属行业": "中药Ⅱ"},
        ]
    )

    detail, summary = build_zt_sentiment(raw, KEYWORDS)
    computer = summary[summary["mapped_industry"].eq("计算机")].iloc[0]
    medicine = summary[summary["mapped_industry"].eq("医药生物")].iloc[0]

    assert detail["mapped_industry"].tolist() == ["计算机", "计算机", "医药生物"]
    assert computer["limit_up_count"] == 2
    assert computer["max_limit_up_days"] == 2
    assert computer["total_seal_amount"] == 40.0
    assert medicine["open_board_count"] == 2
