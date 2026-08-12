from __future__ import annotations

import pandas as pd


def build_northbound_summary(hsgt_top10: pd.DataFrame, stock_map: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if hsgt_top10.empty:
        return pd.DataFrame(), pd.DataFrame()
    df = hsgt_top10.merge(stock_map[["ts_code", "mapped_industry", "stock_industry"]], on="ts_code", how="left")
    df["mapped_industry"] = df["mapped_industry"].fillna("未映射")
    for column in ["amount", "net_amount", "buy", "sell"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    if "net_amount" not in df.columns:
        df["net_amount"] = pd.NA
    if "buy" in df.columns and "sell" in df.columns:
        df["estimated_net_amount"] = df["net_amount"].fillna(df["buy"] - df["sell"])
    else:
        df["estimated_net_amount"] = df["net_amount"]
    summary = (
        df[df["mapped_industry"].ne("未映射")]
        .groupby("mapped_industry", as_index=False)
        .agg(
            hsgt_stock_count=("ts_code", "nunique"),
            hsgt_active_amount=("amount", "sum"),
            hsgt_net_amount=("estimated_net_amount", "sum"),
        )
        .sort_values("hsgt_active_amount", ascending=False)
    )
    return df, summary


def build_hsgt_moneyflow(moneyflow: pd.DataFrame) -> pd.DataFrame:
    if moneyflow.empty:
        return moneyflow
    df = moneyflow.copy()
    for column in ["hgt", "sgt", "north_money", "south_money"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.sort_values("trade_date", ascending=False).reset_index(drop=True)
