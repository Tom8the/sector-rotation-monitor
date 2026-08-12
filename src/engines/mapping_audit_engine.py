from __future__ import annotations

import pandas as pd


def build_mapping_audit(
    industries: pd.DataFrame,
    stock_map: pd.DataFrame,
    etf_detail: pd.DataFrame | None = None,
    zt_detail: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Make industry mapping coverage measurable rather than implicit."""
    names = industries.get("industry_name", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()
    rows: list[dict[str, object]] = []
    for industry in names:
        stock_count = 0
        if not stock_map.empty and "mapped_industry" in stock_map.columns:
            stock_count = int(stock_map[stock_map["mapped_industry"].astype(str).eq(industry)].shape[0])
        etf_count = 0
        if etf_detail is not None and not etf_detail.empty and "mapped_industry" in etf_detail.columns:
            etf_count = int(etf_detail[etf_detail["mapped_industry"].astype(str).eq(industry)].shape[0])
        zt_count = 0
        if zt_detail is not None and not zt_detail.empty and "mapped_industry" in zt_detail.columns:
            zt_count = int(zt_detail[zt_detail["mapped_industry"].astype(str).eq(industry)].shape[0])
        status = "已覆盖" if stock_count > 0 else "需维护"
        rows.append({"industry_name": industry, "mapped_stock_count": stock_count, "mapped_etf_count": etf_count, "mapped_zt_count": zt_count, "mapping_status": status})
    return pd.DataFrame(rows).sort_values(["mapping_status", "industry_name"]).reset_index(drop=True)
