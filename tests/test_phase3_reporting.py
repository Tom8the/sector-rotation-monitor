from datetime import datetime

import pandas as pd

from scripts.run_daily_job import append_scheduler_log, find_missing_snapshot_dates, safe_console_text
from src.core.notifier import build_report_message, send_webhook_notification
from src.core.reporter import generate_html_report


def test_generate_html_report_writes_html_and_chart_asset(tmp_path):
    rotation = pd.DataFrame(
        [
            {
                "industry_name": "电子",
                "rotation_score": 90.0,
                "price_trend_score": 80.0,
                "heat_score": 70.0,
                "etf_score": 60.0,
                "sentiment_score": 50.0,
                "ret_20d": 0.1,
                "excess_20d": 0.05,
            },
            {
                "industry_name": "银行",
                "rotation_score": 70.0,
                "price_trend_score": 65.0,
                "heat_score": 40.0,
                "etf_score": 30.0,
                "sentiment_score": 20.0,
                "ret_20d": -0.02,
                "excess_20d": -0.01,
            },
        ]
    )

    output = generate_html_report("20260708", rotation, tmp_path / "report.html", tmp_path / "assets")

    assert output.exists()
    html = output.read_text(encoding="utf-8")
    assert "A股板块轮动监控日报" in html
    assert "电子" in html
    assert any((tmp_path / "assets").glob("rotation_top10_20260708.*"))


def test_webhook_without_url_is_noop():
    result = send_webhook_notification(None, "message")

    assert result["sent"] is False
    assert result["reason"] == "webhook_not_configured"


def test_build_report_message_contains_paths(tmp_path):
    message = build_report_message(
        report_date="20260708",
        status="正常",
        top_industry="电子",
        top_score=88.8,
        markdown_report=tmp_path / "report.md",
        html_report=tmp_path / "report.html",
    )

    assert "20260708" in message
    assert "电子" in message
    assert "report.html" in message


def test_append_scheduler_log_writes_csv(tmp_path):
    log_path = tmp_path / "scheduler_job_log.csv"

    append_scheduler_log(
        log_path,
        started_at=datetime(2026, 7, 9, 16, 30),
        finished_at=datetime(2026, 7, 9, 16, 31),
        attempt=1,
        max_retries=2,
        return_code=0,
        stdout="ok",
        stderr="",
    )

    text = log_path.read_text(encoding="utf-8-sig")
    assert "return_code" in text
    assert ",0," in text


def test_safe_console_text_escapes_characters_not_supported_by_gbk():
    assert safe_console_text("job \U0001f680", "gbk") == "job \\U0001f680"


def test_find_missing_snapshot_dates_only_returns_open_days_without_scores(tmp_path):
    class FakeFetcher:
        def trade_cal(self, start_date, end_date):
            return pd.DataFrame(
                [
                    {"cal_date": "20260724", "is_open": 1},
                    {"cal_date": "20260725", "is_open": 0},
                    {"cal_date": "20260727", "is_open": 1},
                ]
            )

    (tmp_path / "rotation_scores_20260724.csv").write_text("ok", encoding="utf-8")
    settings = {"paths": {"processed_data_dir": "unused"}, "data_sources": {"tushare": {}}}

    missing = find_missing_snapshot_dates(
        settings,
        "20260728",
        lookback_days=7,
        processed_dir=tmp_path,
        fetcher=FakeFetcher(),
    )

    assert missing == ["20260727"]
