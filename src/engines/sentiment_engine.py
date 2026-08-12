from __future__ import annotations

import pandas as pd


ZT_COLUMN_MAP = {
    "代码": "code",
    "名称": "name",
    "涨跌幅": "pct_change",
    "最新价": "latest_price",
    "成交额": "amount",
    "流通市值": "float_mv",
    "总市值": "total_mv",
    "换手率": "turnover_rate",
    "封板资金": "seal_amount",
    "首次封板时间": "first_limit_time",
    "最后封板时间": "last_limit_time",
    "炸板次数": "open_board_count",
    "涨停统计": "limit_stat",
    "连板数": "limit_up_days",
    "所属行业": "industry",
}


def build_zt_sentiment(raw: pd.DataFrame, keyword_map: dict[str, list[str]] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    if raw.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = raw.rename(columns={k: v for k, v in ZT_COLUMN_MAP.items() if k in raw.columns}).copy()
    required = ["code", "name", "pct_change", "amount", "seal_amount", "open_board_count", "limit_up_days", "industry"]
    for column in required:
        if column not in df.columns:
            df[column] = None
    for column in ["pct_change", "amount", "seal_amount", "open_board_count", "limit_up_days", "latest_price"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df["industry"] = df["industry"].fillna("未分类")
    df["mapped_industry"] = df["industry"].map(lambda value: map_zt_industry(value, keyword_map or {}))

    summary = (
        df.groupby("mapped_industry", as_index=False)
        .agg(
            source_industries=("industry", lambda values: "、".join(sorted(set(map(str, values)))[:5])),
            limit_up_count=("code", "count"),
            max_limit_up_days=("limit_up_days", "max"),
            total_seal_amount=("seal_amount", "sum"),
            avg_turnover_amount=("amount", "mean"),
            open_board_count=("open_board_count", "sum"),
        )
        .sort_values(["limit_up_count", "max_limit_up_days", "total_seal_amount"], ascending=False)
        .reset_index(drop=True)
    )
    return df, summary


def map_zt_industry(name: str, keyword_map: dict[str, list[str]]) -> str:
    normalized = str(name).upper()
    for industry, keywords in keyword_map.items():
        for keyword in keywords:
            if str(keyword).upper() in normalized:
                return industry
    return "未映射"

