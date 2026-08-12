from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import pandas as pd


STATUS_ORDER = {"正常": 0, "注意": 1, "异常": 2}


def overall_status(quality: pd.DataFrame) -> str:
    if quality.empty or "status" not in quality.columns:
        return "注意"
    return max(quality["status"].dropna().astype(str), key=lambda value: STATUS_ORDER.get(value, 1), default="注意")


def build_data_quality(
    *,
    requested_end_date: str,
    latest_trade_date: str,
    industries: pd.DataFrame,
    trend_scores: pd.DataFrame,
    comparison: pd.DataFrame,
    etf_mapping_quality: pd.DataFrame | None,
    zt_summary: pd.DataFrame | None,
    valuation_summary: pd.DataFrame | None = None,
    northbound_summary: pd.DataFrame | None = None,
    dragon_tiger_summary: pd.DataFrame | None = None,
    source_events: pd.DataFrame | None = None,
    extra_messages: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    def add(check: str, status: str, value: object, threshold: str, message: str) -> None:
        rows.append(
            {
                "check": check,
                "status": status,
                "value": str(value),
                "threshold": threshold,
                "message": message,
            }
        )

    add(
        "latest_trade_date",
        "正常" if latest_trade_date == requested_end_date else "注意",
        latest_trade_date,
        requested_end_date,
        "最新交易日与请求日期一致" if latest_trade_date == requested_end_date else "数据源最新交易日早于请求日期，通常是非交易日或源端尚未更新",
    )

    industry_count = len(industries)
    add(
        "industry_count",
        "正常" if industry_count == 31 else "异常",
        industry_count,
        "31",
        "申万一级行业数量正常" if industry_count == 31 else "申万一级行业数量不等于31，需要检查行业列表接口",
    )

    trend_count = trend_scores["industry_name"].nunique() if "industry_name" in trend_scores.columns else len(trend_scores)
    add(
        "trend_score_count",
        "正常" if trend_count == 31 else "异常",
        trend_count,
        "31",
        "趋势评分覆盖31个行业" if trend_count == 31 else "趋势评分行业覆盖不完整",
    )

    add(
        "comparison_series",
        "正常" if not comparison.empty else "异常",
        len(comparison),
        ">0",
        "板块走势序列已生成" if not comparison.empty else "板块走势序列为空",
    )

    if etf_mapping_quality is None or etf_mapping_quality.empty:
        add("etf_mapping_quality", "注意", "missing", "exists", "ETF映射质量文件缺失或为空")
    else:
        quality = etf_mapping_quality.set_index("mapping_status")
        unmapped_share = float(quality.loc["未映射", "amount_share"]) if "未映射" in quality.index else 0.0
        add(
            "etf_unmapped_amount_share",
            "正常" if unmapped_share <= 0.01 else "注意",
            f"{unmapped_share:.4f}",
            "<=0.0100",
            "ETF未映射成交额占比可接受" if unmapped_share <= 0.01 else "ETF未映射成交额占比偏高，需要维护映射规则",
        )

    zt_count = 0 if zt_summary is None or zt_summary.empty else int(zt_summary["limit_up_count"].sum())
    add(
        "zt_pool",
        "正常" if zt_count > 0 else "注意",
        zt_count,
        ">0",
        "涨停池情绪数据已生成" if zt_count > 0 else "涨停池为空，可能是接口缺失或非交易时段",
    )
    if zt_summary is not None and not zt_summary.empty and "stock_count" in zt_summary.columns:
        missing_stock_count = int(pd.to_numeric(zt_summary["stock_count"], errors="coerce").isna().sum())
        add(
            "zt_stock_count_mapping",
            "正常" if missing_stock_count == 0 else "注意",
            missing_stock_count,
            "0",
            "涨停占比行业股本映射完整" if missing_stock_count == 0 else "部分涨停行业缺少股票数量，需维护行业映射关键字",
        )

    valuation_count = 0 if valuation_summary is None or valuation_summary.empty else len(valuation_summary)
    add(
        "valuation_summary",
        "正常" if valuation_count > 0 else "注意",
        valuation_count,
        ">0",
        "行业估值汇总已生成" if valuation_count > 0 else "行业估值汇总为空，需检查 daily_basic 或股票行业映射",
    )

    northbound_count = 0 if northbound_summary is None or northbound_summary.empty else len(northbound_summary)
    add(
        "northbound_summary",
        "正常" if northbound_count > 0 else "注意",
        northbound_count,
        ">0",
        "北向活跃成交行业汇总已生成" if northbound_count > 0 else "北向活跃成交为空，可能是接口当日无数据或行业映射不足",
    )

    dragon_tiger_count = 0 if dragon_tiger_summary is None or dragon_tiger_summary.empty else len(dragon_tiger_summary)
    add(
        "dragon_tiger_summary",
        "正常" if dragon_tiger_count > 0 else "注意",
        dragon_tiger_count,
        ">0",
        "龙虎榜行业汇总已生成" if dragon_tiger_count > 0 else "龙虎榜行业汇总为空，可能是当日无榜单或行业映射不足",
    )

    if source_events is None or source_events.empty:
        add("source_events", "注意", "missing", "exists", "数据源读取事件缺失")
    else:
        error_count = int(source_events["status"].astype(str).eq("error").sum()) if "status" in source_events.columns else 0
        fallback_count = int(source_events["source"].astype(str).eq("fallback_cache").sum()) if "source" in source_events.columns else 0
        status = "异常" if error_count else "注意" if fallback_count else "正常"
        add(
            "source_health",
            status,
            f"errors={error_count};fallback_cache={fallback_count};events={len(source_events)}",
            "errors=0",
            "数据源读取事件正常" if status == "正常" else "存在数据源错误或降级缓存读取，需要检查明细",
        )

    for index, message in enumerate(extra_messages, start=1):
        add(f"extra_message_{index}", "注意", "message", "-", message)

    return pd.DataFrame(rows)


def append_run_log(
    path: Path,
    *,
    started_at: datetime,
    finished_at: datetime,
    requested_end_date: str,
    latest_trade_date: str,
    status: str,
    refresh: bool,
    message_count: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": f"{(finished_at - started_at).total_seconds():.2f}",
        "requested_end_date": requested_end_date,
        "latest_trade_date": latest_trade_date,
        "status": status,
        "refresh": str(refresh),
        "message_count": str(message_count),
    }
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)
