import pandas as pd

from src.engines.history_engine import (
    build_breadth_series,
    build_rotation_heatmap,
    enrich_rotation_history,
    latest_rank_changes,
)


def test_enrich_rotation_history_computes_rank_and_score_changes():
    history = pd.DataFrame(
        [
            {"snapshot_date": "20260701", "industry_name": "电子", "history_score": 80.0, "rank": 2},
            {"snapshot_date": "20260701", "industry_name": "银行", "history_score": 90.0, "rank": 1},
            {"snapshot_date": "20260702", "industry_name": "电子", "history_score": 95.0, "rank": 1},
            {"snapshot_date": "20260702", "industry_name": "银行", "history_score": 70.0, "rank": 2},
        ]
    )

    result = enrich_rotation_history(history)
    latest = latest_rank_changes(result)
    electronic = latest[latest["industry_name"].eq("电子")].iloc[0]
    bank = latest[latest["industry_name"].eq("银行")].iloc[0]

    assert electronic["rank"] == 1
    assert electronic["previous_rank"] == 2
    assert electronic["rank_change"] == 1
    assert electronic["score_change"] == 15.0
    assert electronic["top10_streak"] == 2
    assert bank["rank_change"] == -1


def test_enrich_rotation_history_resets_top10_streak_when_industry_drops_out():
    history = pd.DataFrame(
        [
            {"snapshot_date": "20260701", "industry_name": "电子", "history_score": 80.0, "rank": 8},
            {"snapshot_date": "20260702", "industry_name": "电子", "history_score": 60.0, "rank": 12},
            {"snapshot_date": "20260703", "industry_name": "电子", "history_score": 85.0, "rank": 9},
        ]
    )

    result = enrich_rotation_history(history).sort_values("snapshot_date")

    assert result["top10_streak"].tolist() == [1, 0, 1]


def test_build_rotation_heatmap_uses_latest_top_industries():
    history = enrich_rotation_history(
        pd.DataFrame(
            [
                {"snapshot_date": "20260701", "industry_name": "电子", "history_score": 80.0, "rank": 1},
                {"snapshot_date": "20260701", "industry_name": "银行", "history_score": 70.0, "rank": 2},
                {"snapshot_date": "20260702", "industry_name": "电子", "history_score": 85.0, "rank": 2},
                {"snapshot_date": "20260702", "industry_name": "银行", "history_score": 90.0, "rank": 1},
            ]
        )
    )

    heatmap = build_rotation_heatmap(history, "history_score", top_n=1)

    assert heatmap.index.tolist() == ["银行"]
    assert heatmap.loc["银行", "20260702"] == 90.0


def test_build_breadth_series_counts_rising_and_falling_industries():
    history = enrich_rotation_history(
        pd.DataFrame(
            [
                {"snapshot_date": "20260701", "industry_name": "电子", "history_score": 80.0, "rank": 1},
                {"snapshot_date": "20260701", "industry_name": "银行", "history_score": 70.0, "rank": 2},
                {"snapshot_date": "20260702", "industry_name": "电子", "history_score": 85.0, "rank": 1},
                {"snapshot_date": "20260702", "industry_name": "银行", "history_score": 60.0, "rank": 2},
            ]
        )
    )

    breadth = build_breadth_series(history)
    latest = breadth[breadth["snapshot_date"].eq("20260702")].iloc[0]

    assert latest["rising_count"] == 1
    assert latest["falling_count"] == 1
    assert latest["rising_ratio"] == 0.5
