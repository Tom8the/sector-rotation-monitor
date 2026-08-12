from __future__ import annotations

import pandas as pd


def map_stock_industry(name: str, keyword_map: dict[str, list[str]]) -> str:
    normalized = str(name).upper()
    for industry, keywords in keyword_map.items():
        if str(industry).upper() in normalized:
            return industry
        for keyword in keywords:
            if str(keyword).upper() in normalized:
                return industry
    return "未映射"


def build_stock_industry_map(
    stock_basic: pd.DataFrame,
    keyword_map: dict[str, list[str]],
    overrides: dict[str, str] | None = None,
) -> pd.DataFrame:
    if stock_basic.empty:
        return pd.DataFrame(columns=["ts_code", "name", "stock_industry", "mapped_industry"])
    df = stock_basic.copy()
    if "industry" not in df.columns:
        df["industry"] = None
    df["stock_industry"] = df["industry"].fillna("未分类")
    explicit = overrides or {}
    df["mapped_industry"] = df["stock_industry"].map(lambda value: map_stock_industry(value, keyword_map))
    if "ts_code" in df.columns:
        df["mapped_industry"] = df["ts_code"].astype(str).map(explicit).fillna(df["mapped_industry"])
    return df[["ts_code", "name", "stock_industry", "mapped_industry"]]


def build_industry_stock_counts(stock_map: pd.DataFrame) -> pd.DataFrame:
    if stock_map.empty:
        return pd.DataFrame(columns=["mapped_industry", "stock_count"])
    return (
        stock_map[stock_map["mapped_industry"].ne("未映射")]
        .groupby("mapped_industry", as_index=False)
        .agg(stock_count=("ts_code", "nunique"))
    )
