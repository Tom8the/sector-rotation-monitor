from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests


def build_report_message(
    *,
    report_date: str,
    status: str,
    top_industry: str,
    top_score: float,
    markdown_report: Path,
    html_report: Path | None = None,
    dashboard_url: str = "http://localhost:8501/",
) -> str:
    lines = [
        f"A股板块轮动监控日报 {report_date}",
        f"数据质量: {status}",
        f"轮动第一: {top_industry} ({top_score:.1f})",
        f"看板: {dashboard_url}",
        f"Markdown: {markdown_report}",
    ]
    if html_report is not None:
        lines.append(f"HTML: {html_report}")
    return "\n".join(lines)


def send_webhook_notification(webhook_url: str | None, message: str, timeout_seconds: float = 10.0) -> dict[str, Any]:
    if not webhook_url:
        return {"sent": False, "reason": "webhook_not_configured"}
    payloads = [
        {"msgtype": "text", "text": {"content": message}},
        {"msg_type": "text", "content": {"text": message}},
        {"text": message},
    ]
    last_error = None
    for payload in payloads:
        try:
            response = requests.post(webhook_url, json=payload, timeout=timeout_seconds)
            if response.status_code < 400:
                return {"sent": True, "status_code": response.status_code, "payload": payload}
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception as exc:
            last_error = str(exc)
    return {"sent": False, "reason": last_error or "unknown_error"}


def send_configured_notification(
    *,
    webhook_url_env: str,
    message: str,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    return send_webhook_notification(os.environ.get(webhook_url_env), message, timeout_seconds)
