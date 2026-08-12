from __future__ import annotations

import pandas as pd


def build_event_candidate_pool(
    rotation_scores: pd.DataFrame,
    stock_map: pd.DataFrame,
    daily_basic: pd.DataFrame,
    zt_detail: pd.DataFrame | None = None,
    dragon_detail: pd.DataFrame | None = None,
    northbound_detail: pd.DataFrame | None = None,
    *,
    top_industries: int | None = 5,
) -> pd.DataFrame:
    """Build a research queue from observable event data, not a buy list."""
    if rotation_scores.empty or stock_map.empty:
        return pd.DataFrame()
    ranked_scores = rotation_scores.sort_values("rotation_score", ascending=False)
    industries = ranked_scores[["industry_name", "rotation_score"]] if top_industries is None else ranked_scores.head(top_industries)[["industry_name", "rotation_score"]]
    base = stock_map.merge(industries, left_on="mapped_industry", right_on="industry_name", how="inner")
    if base.empty:
        return pd.DataFrame()
    if "ts_code" in daily_basic.columns:
        basic_columns = [column for column in ["ts_code", "pe_ttm", "pb", "total_mv"] if column in daily_basic.columns]
        base = base.merge(daily_basic[basic_columns], on="ts_code", how="left")
    base["event_score"] = 0.0
    base["event_tags"] = ""
    for detail, tag, amount_column in [
        (zt_detail, "涨停", "seal_amount"),
        (dragon_detail, "龙虎榜", "net_amount"),
        (northbound_detail, "北向活跃", "amount"),
    ]:
        if detail is None or detail.empty or "ts_code" not in detail.columns:
            continue
        frame = detail.copy()
        raw_value = frame[amount_column] if amount_column in frame.columns else pd.Series(0.0, index=frame.index)
        value = pd.to_numeric(raw_value, errors="coerce").fillna(0).abs()
        frame["_event_value"] = value
        event = frame.groupby("ts_code", as_index=False).agg(_event_value=("_event_value", "sum"))
        event["_event_rank"] = event["_event_value"].rank(pct=True) * 100
        base = base.merge(event[["ts_code", "_event_rank"]], on="ts_code", how="left")
        matched = base["_event_rank"].notna()
        base.loc[matched, "event_score"] += base.loc[matched, "_event_rank"].fillna(0) / 3
        base.loc[matched, "event_tags"] = base.loc[matched, "event_tags"] + tag + "、"
        base = base.drop(columns=["_event_rank"])
    base["candidate_score"] = pd.to_numeric(base["rotation_score"], errors="coerce").fillna(0) * 0.7 + base["event_score"] * 0.3
    base["event_tags"] = base["event_tags"].str.rstrip("、").replace("", "行业趋势候选")
    base["risk_flag"] = base["name"].astype(str).str.contains("ST", case=False, na=False).map({True: "ST风险", False: "需个股复核"})
    return base.sort_values("candidate_score", ascending=False).reset_index(drop=True)
