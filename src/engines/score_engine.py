from __future__ import annotations

import pandas as pd


def compute_rotation_scores(
    trend_scores: pd.DataFrame,
    etf_summary: pd.DataFrame | None = None,
    zt_summary: pd.DataFrame | None = None,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    if trend_scores.empty:
        return pd.DataFrame()

    result = trend_scores.copy()
    if "price_trend_score" not in result.columns:
        result["price_trend_score"] = result["trend_score"]
    if "heat_score" not in result.columns:
        result["heat_score"] = _rank_score(result["amount_share"])

    result = result.merge(
        _etf_score(etf_summary),
        left_on="industry_name",
        right_on="industry_name",
        how="left",
    )
    result = result.merge(
        _sentiment_score(zt_summary),
        left_on="industry_name",
        right_on="industry_name",
        how="left",
    )

    for column in ["etf_score", "sentiment_score", "etf_total_amount", "etf_main_net_inflow", "limit_up_count", "max_limit_up_days"]:
        if column not in result.columns:
            result[column] = pd.NA
    result[["etf_total_amount", "etf_main_net_inflow", "limit_up_count", "max_limit_up_days"]] = result[
        ["etf_total_amount", "etf_main_net_inflow", "limit_up_count", "max_limit_up_days"]
    ].fillna(0)

    score_weights = normalize_score_weights(weights)
    # A missing source is not a bearish signal.  Reweight only the components
    # available for that industry and expose the resulting completeness.
    for column in score_weights:
        result[f"{column}_available"] = result[column].notna()
    available_weight = pd.Series(0.0, index=result.index)
    weighted_score = pd.Series(0.0, index=result.index)
    for column, weight in score_weights.items():
        available = result[f"{column}_available"]
        available_weight += available.astype(float) * weight
        weighted_score += pd.to_numeric(result[column], errors="coerce").fillna(0) * available.astype(float) * weight
    for column, weight in score_weights.items():
        result[f"effective_{column}_weight"] = result[f"{column}_available"].astype(float) * weight / available_weight.replace(0, pd.NA)
    result["score_completeness"] = available_weight
    result["rotation_score"] = weighted_score / available_weight.replace(0, pd.NA)
    result["available_components"] = result.apply(
        lambda row: "、".join(name.replace("_score", "") for name in score_weights if row[f"{name}_available"]), axis=1
    )
    result[["etf_score", "sentiment_score"]] = result[["etf_score", "sentiment_score"]].fillna(0)
    return result.sort_values("rotation_score", ascending=False).reset_index(drop=True)


def normalize_score_weights(weights: dict[str, float] | None = None) -> dict[str, float]:
    defaults = {
        "price_trend_score": 0.50,
        "heat_score": 0.20,
        "etf_score": 0.15,
        "sentiment_score": 0.15,
    }
    if weights:
        defaults.update({key: float(value) for key, value in weights.items() if key in defaults})
    total = sum(defaults.values())
    if total <= 0:
        return {
            "price_trend_score": 0.50,
            "heat_score": 0.20,
            "etf_score": 0.15,
            "sentiment_score": 0.15,
        }
    return {key: value / total for key, value in defaults.items()}


def _etf_score(etf_summary: pd.DataFrame | None) -> pd.DataFrame:
    if etf_summary is None or etf_summary.empty:
        return pd.DataFrame(columns=["industry_name", "etf_score", "etf_total_amount", "etf_main_net_inflow"])
    df = etf_summary.copy()
    df["amount_score"] = _rank_score(pd.to_numeric(df["total_amount"], errors="coerce"))
    df["inflow_score"] = _rank_score(pd.to_numeric(df["total_main_net_inflow"], errors="coerce"))
    df["etf_score"] = df["amount_score"] * 0.60 + df["inflow_score"] * 0.40
    return df.rename(
        columns={
            "mapped_industry": "industry_name",
            "total_amount": "etf_total_amount",
            "total_main_net_inflow": "etf_main_net_inflow",
        }
    )[["industry_name", "etf_score", "etf_total_amount", "etf_main_net_inflow"]]


def _sentiment_score(zt_summary: pd.DataFrame | None) -> pd.DataFrame:
    if zt_summary is None or zt_summary.empty:
        return pd.DataFrame(columns=["industry_name", "sentiment_score", "limit_up_count", "max_limit_up_days"])
    df = zt_summary.copy()
    df["count_score"] = _rank_score(pd.to_numeric(df["limit_up_count"], errors="coerce"))
    df["streak_score"] = _rank_score(pd.to_numeric(df["max_limit_up_days"], errors="coerce"))
    df["seal_score"] = _rank_score(pd.to_numeric(df["total_seal_amount"], errors="coerce"))
    df["sentiment_score"] = df["count_score"] * 0.50 + df["streak_score"] * 0.25 + df["seal_score"] * 0.25
    return df.rename(columns={"mapped_industry": "industry_name"})[
        ["industry_name", "sentiment_score", "limit_up_count", "max_limit_up_days"]
    ]


def _rank_score(series: pd.Series) -> pd.Series:
    return series.rank(pct=True, na_option="bottom") * 100
