from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core.history_store import read_table


def load_rotation_history(processed_dir: str | Path, db_path: str | Path | None = None) -> pd.DataFrame:
    if db_path is not None:
        db_history = load_rotation_history_from_db(db_path)
        if not db_history.empty:
            return db_history

    processed = Path(processed_dir)
    frames = []
    for path in sorted(processed.glob("rotation_scores_*.csv")):
        date_value = path.stem.replace("rotation_scores_", "")
        df = pd.read_csv(path, dtype={"trade_date": str})
        if df.empty:
            continue
        df = df.copy()
        df["snapshot_date"] = date_value
        df["snapshot_display_date"] = pd.to_datetime(date_value, format="%Y%m%d")
        score_column = "rotation_score" if "rotation_score" in df.columns else "trend_score"
        df["history_score"] = pd.to_numeric(df[score_column], errors="coerce")
        df["rank"] = df["history_score"].rank(method="first", ascending=False).astype(int)
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return enrich_rotation_history(pd.concat(frames, ignore_index=True))


def load_rotation_history_from_db(db_path: str | Path) -> pd.DataFrame:
    df = read_table(db_path, "rotation_score_daily")
    if df.empty:
        return df
    if "snapshot_date" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["snapshot_date"] = df["snapshot_date"].astype(str)
    df["snapshot_display_date"] = pd.to_datetime(df["snapshot_date"], format="%Y%m%d", errors="coerce")
    score_column = "rotation_score" if "rotation_score" in df.columns else "trend_score"
    df["history_score"] = pd.to_numeric(df[score_column], errors="coerce")
    df["rank"] = df.groupby("snapshot_date")["history_score"].rank(method="first", ascending=False).astype(int)
    return enrich_rotation_history(df)


def enrich_rotation_history(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return history

    result = history.sort_values(["industry_name", "snapshot_date"]).copy()
    result["previous_rank"] = result.groupby("industry_name")["rank"].shift(1)
    result["rank_change"] = result["previous_rank"] - result["rank"]
    result["previous_score"] = result.groupby("industry_name")["history_score"].shift(1)
    result["score_change"] = result["history_score"] - result["previous_score"]
    result["is_top10"] = result["rank"] <= 10
    result["top10_streak"] = result.groupby("industry_name")["is_top10"].transform(_true_streak)
    return result.sort_values(["snapshot_date", "rank"], ascending=[False, True]).reset_index(drop=True)


def latest_rank_changes(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return history
    latest_date = history["snapshot_date"].max()
    return history[history["snapshot_date"].eq(latest_date)].sort_values("rank").reset_index(drop=True)


def build_rotation_heatmap(history: pd.DataFrame, value_column: str = "history_score", top_n: int = 15) -> pd.DataFrame:
    if history.empty or value_column not in history.columns:
        return pd.DataFrame()
    latest = latest_rank_changes(history)
    top_names = latest.head(top_n)["industry_name"].tolist()
    data = history[history["industry_name"].isin(top_names)].copy()
    if data.empty:
        return pd.DataFrame()
    data[value_column] = pd.to_numeric(data[value_column], errors="coerce")
    heatmap = data.pivot_table(
        index="industry_name",
        columns="snapshot_date",
        values=value_column,
        aggfunc="last",
    )
    ordered_names = [name for name in top_names if name in heatmap.index]
    return heatmap.loc[ordered_names].sort_index(axis=1)


def build_strength_summary(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame()
    latest = latest_rank_changes(history).copy()
    columns = [
        "rank",
        "industry_name",
        "history_score",
        "score_change",
        "rank_change",
        "top10_streak",
        "price_trend_score",
        "heat_score",
        "etf_score",
        "sentiment_score",
    ]
    return latest[[column for column in columns if column in latest.columns]].reset_index(drop=True)


def build_breadth_series(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame()
    df = history.copy()
    df["history_score"] = pd.to_numeric(df["history_score"], errors="coerce")
    if "score_change" not in df.columns:
        df["score_change"] = df.groupby("industry_name")["history_score"].diff()
    result = (
        df.groupby("snapshot_date", as_index=False)
        .agg(
            industries=("industry_name", "nunique"),
            top10_count=("rank", lambda values: int((pd.to_numeric(values, errors="coerce") <= 10).sum())),
            rising_count=("score_change", lambda values: int((pd.to_numeric(values, errors="coerce") > 0).sum())),
            falling_count=("score_change", lambda values: int((pd.to_numeric(values, errors="coerce") < 0).sum())),
            avg_score=("history_score", "mean"),
        )
    )
    result["rising_ratio"] = result["rising_count"] / result["industries"].where(result["industries"] > 0)
    result["snapshot_display_date"] = pd.to_datetime(result["snapshot_date"], format="%Y%m%d", errors="coerce")
    return result.sort_values("snapshot_date")


def _true_streak(values: pd.Series) -> pd.Series:
    streaks = []
    streak = 0
    for value in values.astype(bool):
        streak = streak + 1 if value else 0
        streaks.append(streak)
    return pd.Series(streaks, index=values.index)
