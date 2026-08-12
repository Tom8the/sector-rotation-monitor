import pandas as pd

from src.core.history_store import read_table, sync_processed_outputs
from src.engines.history_engine import load_rotation_history


def test_sync_processed_outputs_writes_and_replaces_snapshot(tmp_path):
    processed = tmp_path / "processed"
    processed.mkdir()
    db_path = tmp_path / "history.duckdb"
    snapshot = "20260708"
    path = processed / f"rotation_scores_{snapshot}.csv"
    pd.DataFrame(
        [
            {"trade_date": snapshot, "industry_name": "电子", "rotation_score": 80.0},
            {"trade_date": snapshot, "industry_name": "银行", "rotation_score": 70.0},
        ]
    ).to_csv(path, index=False, encoding="utf-8-sig")

    tables = sync_processed_outputs(db_path, processed, snapshot)
    assert tables == ["rotation_score_daily"]

    pd.DataFrame(
        [
            {"trade_date": snapshot, "industry_name": "电子", "rotation_score": 90.0},
        ]
    ).to_csv(path, index=False, encoding="utf-8-sig")
    sync_processed_outputs(db_path, processed, snapshot)

    stored = read_table(db_path, "rotation_score_daily")
    assert len(stored) == 1
    assert stored.iloc[0]["rotation_score"] == 90.0
    assert str(stored.iloc[0]["snapshot_date"]) == snapshot


def test_load_rotation_history_prefers_duckdb(tmp_path):
    processed = tmp_path / "processed"
    processed.mkdir()
    db_path = tmp_path / "history.duckdb"
    snapshot = "20260708"
    pd.DataFrame(
        [
            {"trade_date": snapshot, "industry_name": "电子", "rotation_score": 80.0},
            {"trade_date": snapshot, "industry_name": "银行", "rotation_score": 90.0},
        ]
    ).to_csv(processed / f"rotation_scores_{snapshot}.csv", index=False, encoding="utf-8-sig")
    sync_processed_outputs(db_path, processed, snapshot)

    history = load_rotation_history(processed, db_path)

    assert history.iloc[0]["industry_name"] == "银行"
    assert history.iloc[0]["rank"] == 1
