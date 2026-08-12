from __future__ import annotations

import pandas as pd

from src.engines.sentiment_engine import map_zt_industry


ETF_COLUMN_MAP = {
    "代码": "code",
    "名称": "name",
    "最新价": "latest_price",
    "涨跌幅": "pct_change",
    "成交额": "amount",
    "主力净流入-净额": "main_net_inflow",
    "最新份额": "latest_shares",
    "数据日期": "data_date",
    "更新时间": "updated_at",
}


def normalize_etf_mapping_config(mapping_config: dict[str, object]) -> tuple[list[str], dict[str, list[str]]]:
    if "industry_keywords" in mapping_config or "exclude_keywords" in mapping_config:
        exclude_keywords = [str(value) for value in mapping_config.get("exclude_keywords", [])]
        industry_keywords = mapping_config.get("industry_keywords", {})
        return exclude_keywords, industry_keywords if isinstance(industry_keywords, dict) else {}
    return [], mapping_config


def classify_etf(name: str, mapping_config: dict[str, object]) -> tuple[str, str]:
    normalized = str(name).upper()
    exclude_keywords, keyword_map = normalize_etf_mapping_config(mapping_config)
    for keyword in exclude_keywords:
        if str(keyword).upper() in normalized:
            return "非行业ETF", "非行业"
    for industry, keywords in keyword_map.items():
        for keyword in keywords:
            if str(keyword).upper() in normalized:
                return str(industry), "行业映射"
    return "未映射", "未映射"


def map_etf_industry(name: str, keyword_map: dict[str, list[str]]) -> str:
    return classify_etf(name, keyword_map)[0]


def build_etf_observation(raw: pd.DataFrame, keyword_map: dict[str, object]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if raw.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = raw.rename(columns={k: v for k, v in ETF_COLUMN_MAP.items() if k in raw.columns}).copy()
    required = ["code", "name", "pct_change", "amount", "main_net_inflow", "latest_shares"]
    for column in required:
        if column not in df.columns:
            df[column] = None
    for column in ["pct_change", "amount", "main_net_inflow", "latest_shares", "latest_price"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    classified = df["name"].map(lambda value: classify_etf(value, keyword_map))
    df["mapped_industry"] = classified.map(lambda value: value[0])
    df["mapping_status"] = classified.map(lambda value: value[1])
    mapped = df[df["mapping_status"].eq("行业映射")].copy()
    if mapped.empty:
        summary = pd.DataFrame()
    else:
        summary = (
            mapped.groupby("mapped_industry", as_index=False)
            .agg(
                etf_count=("code", "count"),
                avg_pct_change=("pct_change", "mean"),
                total_amount=("amount", "sum"),
                total_main_net_inflow=("main_net_inflow", "sum"),
                total_latest_shares=("latest_shares", "sum"),
            )
            .sort_values(["total_amount", "total_main_net_inflow"], ascending=False)
            .reset_index(drop=True)
        )
    return df, summary


def build_etf_mapping_quality(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty or "mapping_status" not in detail.columns:
        return pd.DataFrame()
    quality = (
        detail.groupby("mapping_status", as_index=False)
        .agg(
            etf_count=("code", "count"),
            total_amount=("amount", "sum"),
            sample_names=("name", lambda values: "、".join(list(map(str, values))[:8])),
        )
        .sort_values("total_amount", ascending=False)
        .reset_index(drop=True)
    )
    total_count = quality["etf_count"].sum()
    total_amount = quality["total_amount"].sum()
    quality["count_share"] = quality["etf_count"] / total_count if total_count else 0
    quality["amount_share"] = quality["total_amount"] / total_amount if total_amount else 0
    return quality


def build_industry_main_flow(raw: pd.DataFrame, keyword_map: dict[str, list[str]]) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    df = raw.copy()
    name_column = next((column for column in ["sector_name", "名称", "行业", "板块名称"] if column in df.columns), None)
    flow_column = next((column for column in ["main_net_inflow", "主力净流入-净额", "今日主力净流入-净额"] if column in df.columns), None)
    if name_column is None or flow_column is None:
        return pd.DataFrame()
    df["mapped_industry"] = df[name_column].map(lambda value: map_zt_industry(value, keyword_map))
    df["main_net_inflow"] = pd.to_numeric(df[flow_column], errors="coerce")
    return (
        df[df["mapped_industry"].ne("未映射")]
        .groupby("mapped_industry", as_index=False)
        .agg(main_net_inflow=("main_net_inflow", "sum"), source_sector_count=(name_column, "count"))
        .sort_values("main_net_inflow", ascending=False)
        .reset_index(drop=True)
    )
