from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.data_service import DataService
from src.core.database import CsvCache
from src.core.history_store import sync_processed_outputs
from src.core.notifier import build_report_message, send_configured_notification
from src.core.quality import append_run_log, build_data_quality, overall_status
from src.core.reporter import generate_html_report, generate_markdown_report
from src.engines.dragon_tiger_engine import add_limit_up_ratio, build_dragon_tiger_summary
from src.engines.flow_engine import build_etf_mapping_quality, build_etf_observation, build_industry_main_flow
from src.engines.etf_history_engine import update_etf_history
from src.engines.market_structure_engine import summarize_block_trade, summarize_margin_detail
from src.engines.mapping_audit_engine import build_mapping_audit
from src.engines.candidate_engine import build_event_candidate_pool
from src.engines.northbound_engine import build_hsgt_moneyflow, build_northbound_summary
from src.engines.score_engine import compute_rotation_scores
from src.engines.risk_engine import build_rotation_signals
from src.engines.style_index_engine import summarize_style_indexes
from src.engines.sentiment_engine import build_zt_sentiment
from src.engines.stock_mapping_engine import build_industry_stock_counts, build_stock_industry_map
from src.engines.trend_engine import build_comparison_series, compute_trend_scores, normalize_industry_daily
from src.engines.valuation_engine import build_industry_valuation
from src.fetchers.akshare_fetcher import AkshareFetcher
from src.fetchers.astock_fetcher import AStockFetcher
from src.fetchers.tushare_fetcher import TushareFetcher
from src.utils.config import load_settings, project_path
from src.utils.dates import lookback_start, yyyymmdd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run daily sector rotation MVP pipeline.")
    parser.add_argument("--date", dest="end_date", default=yyyymmdd(date.today()), help="End date in YYYYMMDD.")
    parser.add_argument("--lookback-days", type=int, default=None, help="Calendar days to fetch before end date.")
    parser.add_argument("--refresh", action="store_true", help="Ignore local raw-data cache and fetch from remote sources.")
    return parser.parse_args()


def main() -> None:
    started_at = datetime.now()
    args = parse_args()
    settings = load_settings()
    etf_mapping_path = settings.get("mapping_files", {}).get("etf_industry")
    etf_mapping = load_settings(project_path(etf_mapping_path)) if etf_mapping_path else settings.get("etf_mapping_keywords", {})
    overrides_path = settings.get("mapping_files", {}).get("stock_industry_overrides")
    overrides_config = load_settings(project_path(overrides_path)) if overrides_path else {}
    stock_overrides = overrides_config.get("overrides", {}) if isinstance(overrides_config, dict) else {}
    lookback_days = args.lookback_days or int(settings["market"]["default_lookback_days"])
    end = pd.to_datetime(args.end_date).date()
    start_date = lookback_start(end, lookback_days)
    end_date = args.end_date

    raw_dir = project_path(settings["paths"]["raw_data_dir"])
    processed_dir = project_path(settings["paths"]["processed_data_dir"])
    research_dir = project_path("data/research")
    reports_dir = project_path(settings["paths"]["reports_dir"])
    report_assets_dir = project_path(settings["paths"].get("report_assets_dir", "data/reports/assets"))
    logs_dir = project_path(settings["paths"].get("logs_dir", "data/logs"))

    tushare_settings = settings["data_sources"]["tushare"]
    fetcher = TushareFetcher(
        base_url=tushare_settings["base_url"],
        token_env=tushare_settings["token_env"],
        request_interval_seconds=float(tushare_settings["request_interval_seconds"]),
    )
    akshare = AkshareFetcher()
    service = DataService(tushare=fetcher, akshare=akshare, astock=AStockFetcher(), cache=CsvCache(raw_dir), refresh=args.refresh)

    industries = service.get_sw_industries(
        source=settings["market"]["sw_source"],
        level=settings["market"]["industry_level"],
    )
    daily_frames = []
    for row in industries.itertuples(index=False):
        df = service.get_sw_daily(row.index_code, start_date=start_date, end_date=end_date)
        if not df.empty:
            daily_frames.append(df)
    if not daily_frames:
        raise RuntimeError("No SW industry daily data fetched.")

    raw_industry_daily = pd.concat(daily_frames, ignore_index=True)
    industry_daily = normalize_industry_daily(raw_industry_daily, industries)
    benchmark_daily = service.get_index_daily(
        settings["market"]["benchmark_index"],
        start_date=start_date,
        end_date=end_date,
    )
    trend_scores = compute_trend_scores(industry_daily, benchmark_daily)
    if trend_scores.empty:
        raise RuntimeError("Trend score calculation returned empty data.")

    latest_trade_date = str(trend_scores["trade_date"].max())
    benchmark_daily.to_csv(processed_dir / f"benchmark_daily_{latest_trade_date}.csv", index=False, encoding="utf-8-sig")
    processed_dir.mkdir(parents=True, exist_ok=True)
    industry_daily.to_csv(processed_dir / f"industry_daily_{latest_trade_date}.csv", index=False, encoding="utf-8-sig")
    score_path = processed_dir / f"trend_scores_{latest_trade_date}.csv"
    trend_scores.to_csv(score_path, index=False, encoding="utf-8-sig")

    comparison = build_comparison_series(
        industry_daily,
        benchmark_daily,
        industries["industry_name"].dropna().astype(str).tolist(),
    )
    comparison_path = processed_dir / f"comparison_series_{latest_trade_date}.csv"
    comparison.to_csv(comparison_path, index=False, encoding="utf-8-sig")

    etf_summary_path = None
    zt_summary_path = None
    etf_summary = None
    etf_mapping_quality = None
    zt_summary = None
    valuation_summary = None
    northbound_summary = None
    dragon_tiger_summary = None
    valuation_summary_path = None
    northbound_summary_path = None
    dragon_tiger_summary_path = None
    sector_flow_summary = pd.DataFrame()
    margin_summary = pd.DataFrame()
    block_trade_summary = pd.DataFrame()
    extra_messages = []

    stock_map = pd.DataFrame()
    stock_counts = pd.DataFrame()
    etf_detail = pd.DataFrame()
    zt_detail = pd.DataFrame()
    try:
        stock_basic = service.get_stock_basic()
        stock_map = build_stock_industry_map(stock_basic, settings.get("zt_industry_mapping_keywords", {}), stock_overrides)
        stock_counts = build_industry_stock_counts(stock_map)
        stock_map.to_csv(processed_dir / f"stock_industry_map_{latest_trade_date}.csv", index=False, encoding="utf-8-sig")
        stock_counts.to_csv(processed_dir / f"industry_stock_counts_{latest_trade_date}.csv", index=False, encoding="utf-8-sig")
    except Exception as exc:
        extra_messages.append(f"股票行业映射暂缺: {exc}")

    try:
        daily_basic = service.get_daily_basic(latest_trade_date)
        valuation_summary = build_industry_valuation(daily_basic, stock_map, latest_trade_date, processed_dir)
        valuation_summary_path = processed_dir / f"valuation_summary_{latest_trade_date}.csv"
        daily_basic.to_csv(processed_dir / f"daily_basic_{latest_trade_date}.csv", index=False, encoding="utf-8-sig")
        valuation_summary.to_csv(valuation_summary_path, index=False, encoding="utf-8-sig")
    except Exception as exc:
        extra_messages.append(f"估值数据暂缺: {exc}")

    try:
        hsgt_moneyflow = build_hsgt_moneyflow(service.get_moneyflow_hsgt(start_date, latest_trade_date))
        hsgt_frames = []
        for market_type in ["1", "3"]:
            frame = service.get_hsgt_top10(latest_trade_date, market_type)
            if not frame.empty:
                hsgt_frames.append(frame)
        hsgt_top10 = pd.concat(hsgt_frames, ignore_index=True) if hsgt_frames else pd.DataFrame()
        northbound_detail, northbound_summary = build_northbound_summary(hsgt_top10, stock_map)
        northbound_summary_path = processed_dir / f"northbound_summary_{latest_trade_date}.csv"
        hsgt_moneyflow.to_csv(processed_dir / f"hsgt_moneyflow_{latest_trade_date}.csv", index=False, encoding="utf-8-sig")
        northbound_detail.to_csv(processed_dir / f"northbound_detail_{latest_trade_date}.csv", index=False, encoding="utf-8-sig")
        northbound_summary.to_csv(northbound_summary_path, index=False, encoding="utf-8-sig")
    except Exception as exc:
        extra_messages.append(f"北向资金数据暂缺: {exc}")

    try:
        margin_summary = summarize_margin_detail(service.get_margin_detail(latest_trade_date))
        margin_summary.to_csv(processed_dir / f"margin_summary_{latest_trade_date}.csv", index=False, encoding="utf-8-sig")
    except Exception as exc:
        extra_messages.append(f"融资融券数据暂缺: {exc}")

    try:
        block_trade_detail, block_trade_summary = summarize_block_trade(service.get_block_trade(latest_trade_date), stock_map)
        block_trade_detail.to_csv(processed_dir / f"block_trade_detail_{latest_trade_date}.csv", index=False, encoding="utf-8-sig")
        block_trade_summary.to_csv(processed_dir / f"block_trade_summary_{latest_trade_date}.csv", index=False, encoding="utf-8-sig")
    except Exception as exc:
        extra_messages.append(f"大宗交易数据暂缺: {exc}")

    try:
        style_frames = {
            style_name: service.get_index_daily(ts_code, start_date, latest_trade_date)
            for style_name, ts_code in settings.get("style_index_codes", {}).items()
        }
        style_index_summary = summarize_style_indexes(style_frames)
        style_index_summary.to_csv(processed_dir / f"style_index_summary_{latest_trade_date}.csv", index=False, encoding="utf-8-sig")
    except Exception as exc:
        extra_messages.append(f"风格指数数据暂缺: {exc}")

    try:
        top_list = service.get_top_list(latest_trade_date)
        dragon_tiger_detail, dragon_tiger_summary = build_dragon_tiger_summary(top_list, stock_map)
        dragon_tiger_summary_path = processed_dir / f"dragon_tiger_summary_{latest_trade_date}.csv"
        dragon_tiger_detail.to_csv(processed_dir / f"dragon_tiger_detail_{latest_trade_date}.csv", index=False, encoding="utf-8-sig")
        dragon_tiger_summary.to_csv(dragon_tiger_summary_path, index=False, encoding="utf-8-sig")
    except Exception as exc:
        extra_messages.append(f"龙虎榜数据暂缺: {exc}")

    try:
        etf_raw = service.get_etf_spot(latest_trade_date)
        etf_detail, etf_summary = build_etf_observation(etf_raw, etf_mapping)
        etf_mapping_quality = build_etf_mapping_quality(etf_detail)
        etf_detail_path = processed_dir / f"etf_detail_{latest_trade_date}.csv"
        etf_summary_path = processed_dir / f"etf_summary_{latest_trade_date}.csv"
        etf_mapping_quality_path = processed_dir / f"etf_mapping_quality_{latest_trade_date}.csv"
        etf_detail.to_csv(etf_detail_path, index=False, encoding="utf-8-sig")
        etf_summary.to_csv(etf_summary_path, index=False, encoding="utf-8-sig")
        etf_mapping_quality.to_csv(etf_mapping_quality_path, index=False, encoding="utf-8-sig")
        etf_history_settings = settings.get("etf_history", {})
        _, etf_history_series, etf_history_errors = update_etf_history(
            etf_detail,
            service.get_etf_history,
            research_dir / "etf_history_detail.csv",
            latest_trade_date,
            lookback_days=int(etf_history_settings.get("lookback_days", 180)),
            max_per_industry=int(etf_history_settings.get("max_etfs_per_industry", 1)),
        )
        if not etf_history_series.empty:
            etf_history_series.to_csv(research_dir / "etf_industry_series.csv", index=False, encoding="utf-8-sig")
        if etf_history_errors:
            extra_messages.append(f"ETF历史部分暂缺: {len(etf_history_errors)} 个代表ETF获取失败")
    except Exception as exc:
        extra_messages.append(f"ETF 数据暂缺: {exc}")

    try:
        sector_flow_raw = service.get_sector_fund_flow(latest_trade_date)
        sector_flow_summary = build_industry_main_flow(sector_flow_raw, settings.get("zt_industry_mapping_keywords", {}))
        sector_flow_summary.to_csv(processed_dir / f"sector_flow_summary_{latest_trade_date}.csv", index=False, encoding="utf-8-sig")
    except Exception as exc:
        extra_messages.append(f"行业主力资金数据暂缺: {exc}")

    try:
        zt_raw = service.get_zt_pool(latest_trade_date)
        zt_detail, zt_summary = build_zt_sentiment(zt_raw, settings.get("zt_industry_mapping_keywords", {}))
        zt_summary = add_limit_up_ratio(zt_summary, stock_counts)
        zt_detail_path = processed_dir / f"zt_detail_{latest_trade_date}.csv"
        zt_summary_path = processed_dir / f"zt_summary_{latest_trade_date}.csv"
        zt_detail.to_csv(zt_detail_path, index=False, encoding="utf-8-sig")
        zt_summary.to_csv(zt_summary_path, index=False, encoding="utf-8-sig")
    except Exception as exc:
        extra_messages.append(f"涨停池数据暂缺: {exc}")

    rotation_scores = compute_rotation_scores(trend_scores, etf_summary, zt_summary, settings.get("scoring", {}).get("weights"))
    mapping_audit = build_mapping_audit(industries, stock_map, etf_detail, zt_detail)
    mapping_audit.to_csv(processed_dir / f"mapping_audit_{latest_trade_date}.csv", index=False, encoding="utf-8-sig")
    risk_signals = build_rotation_signals(
        rotation_scores,
        sector_flow=sector_flow_summary,
        zt_summary=zt_summary,
        northbound_summary=northbound_summary,
    )
    if not risk_signals.empty:
        rotation_scores = risk_signals
        risk_signals.to_csv(processed_dir / f"risk_signals_{latest_trade_date}.csv", index=False, encoding="utf-8-sig")
    candidate_pool = build_event_candidate_pool(rotation_scores, stock_map, daily_basic if "daily_basic" in locals() else pd.DataFrame(), zt_detail, dragon_tiger_detail if "dragon_tiger_detail" in locals() else pd.DataFrame(), northbound_detail if "northbound_detail" in locals() else pd.DataFrame(), top_industries=None)
    candidate_pool.to_csv(processed_dir / f"candidate_pool_{latest_trade_date}.csv", index=False, encoding="utf-8-sig")
    rotation_path = processed_dir / f"rotation_scores_{latest_trade_date}.csv"
    rotation_scores.to_csv(rotation_path, index=False, encoding="utf-8-sig")

    source_events = pd.DataFrame(service.events)
    source_health_path = processed_dir / f"source_health_{latest_trade_date}.csv"
    source_events.to_csv(source_health_path, index=False, encoding="utf-8-sig")

    quality = build_data_quality(
        requested_end_date=end_date,
        latest_trade_date=latest_trade_date,
        industries=industries,
        trend_scores=trend_scores,
        comparison=comparison,
        etf_mapping_quality=etf_mapping_quality,
        zt_summary=zt_summary,
        valuation_summary=valuation_summary,
        northbound_summary=northbound_summary,
        dragon_tiger_summary=dragon_tiger_summary,
        source_events=source_events,
        extra_messages=extra_messages,
    )
    quality_status = overall_status(quality)
    quality_path = processed_dir / f"data_quality_{latest_trade_date}.csv"
    quality.to_csv(quality_path, index=False, encoding="utf-8-sig")

    report_path = reports_dir / f"sector_rotation_{latest_trade_date}.md"
    generate_markdown_report(
        latest_trade_date,
        rotation_scores,
        comparison_path,
        report_path,
        etf_summary_path=etf_summary_path,
        zt_summary_path=zt_summary_path,
        valuation_summary_path=valuation_summary_path,
        northbound_summary_path=northbound_summary_path,
        dragon_tiger_summary_path=dragon_tiger_summary_path,
        extra_messages=extra_messages,
    )
    html_report_path = reports_dir / f"sector_rotation_{latest_trade_date}.html"
    generate_html_report(
        latest_trade_date,
        rotation_scores,
        html_report_path,
        report_assets_dir / latest_trade_date,
        etf_summary_path=etf_summary_path,
        zt_summary_path=zt_summary_path,
        valuation_summary_path=valuation_summary_path,
        northbound_summary_path=northbound_summary_path,
        dragon_tiger_summary_path=dragon_tiger_summary_path,
        extra_messages=extra_messages,
    )

    finished_at = datetime.now()
    append_run_log(
        logs_dir / "daily_run_log.csv",
        started_at=started_at,
        finished_at=finished_at,
        requested_end_date=end_date,
        latest_trade_date=latest_trade_date,
        status=quality_status,
        refresh=args.refresh,
        message_count=len(extra_messages),
    )
    db_path = project_path(settings["paths"].get("duckdb_path", "data/sector_rotation.duckdb"))
    synced_tables = sync_processed_outputs(db_path, processed_dir, latest_trade_date)
    automation_settings = settings.get("automation", {})
    notification = send_configured_notification(
        webhook_url_env=automation_settings.get("webhook_url_env", "SECTOR_ROTATION_WEBHOOK_URL"),
        message=build_report_message(
            report_date=latest_trade_date,
            status=quality_status,
            top_industry=str(rotation_scores.iloc[0]["industry_name"]),
            top_score=float(rotation_scores.iloc[0]["rotation_score"]),
            markdown_report=report_path,
            html_report=html_report_path,
        ),
    )

    print(f"Fetched industries: {len(industries)}")
    print(f"Latest trade date: {latest_trade_date}")
    print(f"Data quality: {quality_status}")
    print(f"Trend scores: {score_path}")
    print(f"Rotation scores: {rotation_path}")
    print(f"Comparison series: {comparison_path}")
    print(f"Data quality file: {quality_path}")
    print(f"Source health: {source_health_path}")
    if etf_summary_path:
        print(f"ETF summary: {etf_summary_path}")
    if zt_summary_path:
        print(f"ZT summary: {zt_summary_path}")
    print(f"DuckDB history: {db_path} ({len(synced_tables)} tables synced)")
    for message in extra_messages:
        print(message)
    print(f"Report: {report_path}")
    print(f"HTML report: {html_report_path}")
    print(f"Notification: {notification}")
    print("")
    print(
        rotation_scores[
            [
                "industry_name",
                "rotation_score",
                "price_trend_score",
                "heat_score",
                "etf_score",
                "sentiment_score",
                "ret_20d",
                "excess_20d",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
