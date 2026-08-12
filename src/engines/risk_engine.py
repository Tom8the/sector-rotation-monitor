from __future__ import annotations

import pandas as pd


def build_rotation_signals(scores: pd.DataFrame, *, sector_flow: pd.DataFrame | None = None, zt_summary: pd.DataFrame | None = None, northbound_summary: pd.DataFrame | None = None) -> pd.DataFrame:
    """Convert cross-sectional component scores into readable signal and risk states."""
    if scores.empty:
        return pd.DataFrame()
    result = scores.copy()
    result["signal_state"] = result.apply(_signal_state, axis=1)
    result["risk_flags"] = result.apply(_base_risk_flags, axis=1)
    result["data_confidence"] = result.apply(_confidence, axis=1)
    if sector_flow is not None and not sector_flow.empty and "mapped_industry" in sector_flow.columns:
        flow = sector_flow[["mapped_industry", "main_net_inflow"]].rename(columns={"mapped_industry": "industry_name"})
        result = result.merge(flow, on="industry_name", how="left")
        result["flow_state"] = result["main_net_inflow"].map(lambda value: "资金流入" if pd.notna(value) and value > 0 else "资金流出" if pd.notna(value) else "未覆盖")
    else:
        result["flow_state"] = "未覆盖"
    if zt_summary is not None and not zt_summary.empty and {"mapped_industry", "open_board_count"}.issubset(zt_summary.columns):
        zt = zt_summary[["mapped_industry", "open_board_count"]].rename(columns={"mapped_industry": "industry_name"})
        result = result.merge(zt, on="industry_name", how="left")
        result.loc[pd.to_numeric(result["open_board_count"], errors="coerce").fillna(0) >= 3, "risk_flags"] += "|炸板偏多"
    if northbound_summary is not None and not northbound_summary.empty and {"mapped_industry", "hsgt_net_amount"}.issubset(northbound_summary.columns):
        north = northbound_summary[["mapped_industry", "hsgt_net_amount"]].rename(columns={"mapped_industry": "industry_name"})
        result = result.merge(north, on="industry_name", how="left")
        negative = pd.to_numeric(result["hsgt_net_amount"], errors="coerce") < 0
        strong = pd.to_numeric(result["price_trend_score"], errors="coerce") >= 70
        result.loc[negative & strong, "risk_flags"] += "|北向背离"
    result["risk_flags"] = result["risk_flags"].str.strip("|").replace("", "无")
    return result


def _signal_state(row: pd.Series) -> str:
    trend = float(row.get("price_trend_score", row.get("trend_score", 0)) or 0)
    excess = float(row.get("excess_20d", 0) or 0)
    rsi = float(row.get("rsi_14", 50) or 50)
    if trend >= 75 and excess > 0 and rsi < 75:
        return "趋势确认"
    if trend >= 60 and excess >= 0:
        return "趋势启动"
    if trend < 40 or excess < -0.03:
        return "趋势走弱"
    return "观察等待"


def _base_risk_flags(row: pd.Series) -> str:
    flags: list[str] = []
    if float(row.get("rsi_14", 50) or 50) >= 75 or float(row.get("relative_rsi_14", 50) or 50) >= 75:
        flags.append("技术过热")
    if float(row.get("sentiment_score", 0) or 0) >= 90:
        flags.append("情绪拥挤")
    return "|".join(flags)


def _confidence(row: pd.Series) -> float:
    if pd.notna(row.get("score_completeness")):
        return round(float(row["score_completeness"]), 2)
    available = sum(pd.notna(row.get(column)) for column in ["price_trend_score", "heat_score", "etf_score", "sentiment_score"])
    return round(available / 4, 2)
