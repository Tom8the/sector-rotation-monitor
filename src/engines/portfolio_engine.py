from __future__ import annotations

import pandas as pd


def build_portfolio_plan(
    scores: pd.DataFrame,
    style_groups: dict[str, list[str]],
    *,
    max_industry_weight: float = 0.25,
    max_positions: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    """Create a constrained research allocation from confirmed sector signals."""
    if scores.empty:
        return pd.DataFrame(), pd.DataFrame(), {"gross_exposure": 0.0, "hhi": 0.0}
    df = scores.copy()
    df["rotation_score"] = pd.to_numeric(df["rotation_score"], errors="coerce").fillna(0)
    confidence = df["data_confidence"] if "data_confidence" in df.columns else pd.Series(1.0, index=df.index)
    df["data_confidence"] = pd.to_numeric(confidence, errors="coerce").fillna(0)
    risk_penalty = df.get("risk_flags", pd.Series("无", index=df.index)).astype(str).map(lambda value: 0.55 if value not in {"无", "", "nan"} else 1.0)
    df["allocation_signal"] = df["rotation_score"] * df["data_confidence"] * risk_penalty
    if "signal_state" in df.columns:
        allocation_candidates = df[df["signal_state"].isin(["趋势确认", "趋势启动"])].copy()
        watch_candidates = df[df["signal_state"].eq("观察等待")].copy()
    else:
        allocation_candidates = df.copy()
        watch_candidates = pd.DataFrame(columns=df.columns)
    allocation_candidates = allocation_candidates.sort_values("allocation_signal", ascending=False).head(max_positions).copy()
    allocation_candidates["portfolio_role"] = "配置候选"
    remaining_slots = max(0, int(max_positions) - len(allocation_candidates))
    watch_candidates = watch_candidates.sort_values("allocation_signal", ascending=False).head(remaining_slots).copy()
    watch_candidates["portfolio_role"] = "观察候选"
    df = pd.concat([allocation_candidates, watch_candidates], ignore_index=True)
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), {"gross_exposure": 0.0, "cash_weight": 1.0, "hhi": 0.0, "max_industry_weight": 0.0}
    df["suggested_weight"] = 0.0
    allocation_mask = df["portfolio_role"].eq("配置候选")
    allocation_total = df.loc[allocation_mask, "allocation_signal"].sum()
    if allocation_total > 0:
        df.loc[allocation_mask, "suggested_weight"] = df.loc[allocation_mask, "allocation_signal"] / allocation_total
        df.loc[allocation_mask, "suggested_weight"] = df.loc[allocation_mask, "suggested_weight"].clip(upper=max_industry_weight)
    # Keep any residual as cash rather than forcing it into a capped industry.
    df["cash_weight"] = 1 - df["suggested_weight"].sum()
    exposure_rows = []
    for style_name, industries in style_groups.items():
        exposure_rows.append({"style_name": style_name, "style_weight": float(df.loc[df["industry_name"].isin(industries), "suggested_weight"].sum())})
    style_exposure = pd.DataFrame(exposure_rows).sort_values("style_weight", ascending=False) if exposure_rows else pd.DataFrame()
    metrics = {
        "gross_exposure": float(df["suggested_weight"].sum()),
        "cash_weight": float(1 - df["suggested_weight"].sum()),
        "hhi": float((df["suggested_weight"] ** 2).sum()),
        "max_industry_weight": float(df["suggested_weight"].max()),
    }
    return df, style_exposure, metrics
