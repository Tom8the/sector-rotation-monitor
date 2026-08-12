from __future__ import annotations

import pandas as pd


def build_dragon_tiger_summary(top_list: pd.DataFrame, stock_map: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if top_list.empty:
        return pd.DataFrame(), pd.DataFrame()
    df = top_list.merge(stock_map[["ts_code", "mapped_industry", "stock_industry"]], on="ts_code", how="left")
    df["mapped_industry"] = df["mapped_industry"].fillna("未映射")
    for column in ["amount", "l_sell", "l_buy", "l_amount", "net_amount", "net_rate", "amount_rate"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    summary = (
        df[df["mapped_industry"].ne("未映射")]
        .groupby("mapped_industry", as_index=False)
        .agg(
            top_list_count=("ts_code", "nunique"),
            top_list_amount=("amount", "sum"),
            top_list_net_amount=("net_amount", "sum"),
            top_list_buy=("l_buy", "sum"),
            top_list_sell=("l_sell", "sum"),
        )
        .sort_values(["top_list_net_amount", "top_list_amount"], ascending=False)
    )
    return df, summary


def add_limit_up_ratio(zt_summary: pd.DataFrame, stock_counts: pd.DataFrame) -> pd.DataFrame:
    if zt_summary is None or zt_summary.empty:
        return zt_summary
    result = zt_summary.merge(stock_counts, on="mapped_industry", how="left")
    result["stock_count"] = pd.to_numeric(result["stock_count"], errors="coerce")
    result["limit_up_ratio"] = result["limit_up_count"] / result["stock_count"].where(result["stock_count"] > 0)
    return result
