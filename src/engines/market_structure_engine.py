from __future__ import annotations

import pandas as pd


def summarize_margin_detail(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    df = raw.copy()
    for column in ["rzye", "rzmre", "rzche", "rqye", "rqmcl", "rqchl"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    rzmre = df["rzmre"] if "rzmre" in df.columns else pd.Series(0.0, index=df.index)
    rzche = df["rzche"] if "rzche" in df.columns else pd.Series(0.0, index=df.index)
    rqmcl = df["rqmcl"] if "rqmcl" in df.columns else pd.Series(0.0, index=df.index)
    rqchl = df["rqchl"] if "rqchl" in df.columns else pd.Series(0.0, index=df.index)
    df["net_margin_change"] = rzmre.fillna(0) - rzche.fillna(0)
    df["net_short_change"] = rqmcl.fillna(0) - rqchl.fillna(0)
    return df


def summarize_block_trade(raw: pd.DataFrame, stock_map: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if raw.empty:
        return pd.DataFrame(), pd.DataFrame()
    df = raw.merge(stock_map[["ts_code", "mapped_industry"]], on="ts_code", how="left") if not stock_map.empty else raw.copy()
    df["mapped_industry"] = df.get("mapped_industry", pd.Series(index=df.index, dtype=object)).fillna("未映射")
    for column in ["amount", "vol", "price"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    summary = (
        df[df["mapped_industry"].ne("未映射")]
        .groupby("mapped_industry", as_index=False)
        .agg(block_trade_count=("ts_code", "count"), block_trade_amount=("amount", "sum"))
        .sort_values("block_trade_amount", ascending=False)
    )
    return df, summary
