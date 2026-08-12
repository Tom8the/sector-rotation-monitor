import pandas as pd

from src.engines.mapping_audit_engine import build_mapping_audit
from src.engines.research_engine import run_walk_forward_grid


def test_mapping_audit_marks_uncovered_industries():
    industries = pd.DataFrame({"industry_name": ["电子", "银行"]})
    stock_map = pd.DataFrame({"mapped_industry": ["电子"], "ts_code": ["000001.SZ"]})
    result = build_mapping_audit(industries, stock_map)
    assert result.set_index("industry_name").loc["电子", "mapping_status"] == "已覆盖"
    assert result.set_index("industry_name").loc["银行", "mapping_status"] == "需维护"


def test_walk_forward_grid_returns_train_and_test_metrics():
    history = pd.DataFrame(
        [
            {"snapshot_date": f"2024010{day}", "industry_name": "电子", "rank": 1}
            for day in range(1, 6)
        ]
    )
    prices = pd.DataFrame(
        [{"trade_date": f"2024010{day}", "industry_name": "电子", "close": 100 + day} for day in range(1, 10)]
    )
    result = run_walk_forward_grid(history, prices, top_n_values=[1], hold_days_values=[1], split_date="20240103")
    assert len(result) == 1
    assert result.iloc[0]["train_trades"] > 0
    assert result.iloc[0]["test_trades"] > 0
