from __future__ import annotations

import pandas as pd


def build_style_summary(rotation_scores: pd.DataFrame, style_groups: dict[str, list[str]]) -> pd.DataFrame:
    if rotation_scores.empty or not style_groups:
        return pd.DataFrame()
    rows = []
    for style_name, industries in style_groups.items():
        group = rotation_scores[rotation_scores["industry_name"].isin(industries)].copy()
        if group.empty:
            continue
        rows.append(
            {
                "style_name": style_name,
                "industry_count": int(group["industry_name"].nunique()),
                "avg_rotation_score": _mean(group, "rotation_score"),
                "avg_ret_20d": _mean(group, "ret_20d"),
                "avg_excess_20d": _mean(group, "excess_20d"),
                "avg_heat_score": _mean(group, "heat_score"),
                "top_industry": str(group.sort_values("rotation_score", ascending=False).iloc[0]["industry_name"]),
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values("avg_rotation_score", ascending=False).reset_index(drop=True)


def _mean(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[column], errors="coerce").mean())
