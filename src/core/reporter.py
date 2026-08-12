from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio


def format_pct(value: float | None) -> str:
    if pd.isna(value):
        return "-"
    return f"{value * 100:.2f}%"


def generate_markdown_report(
    report_date: str,
    trend_scores: pd.DataFrame,
    comparison_path: Path,
    output_path: Path,
    etf_summary_path: Path | None = None,
    zt_summary_path: Path | None = None,
    valuation_summary_path: Path | None = None,
    northbound_summary_path: Path | None = None,
    dragon_tiger_summary_path: Path | None = None,
    extra_messages: list[str] | None = None,
) -> Path:
    lines = [
        f"# A股板块轮动监控日报 - {report_date}",
        "",
        "## 综合轮动TOP10",
        "",
        "| 排名 | 行业 | 综合分 | 趋势分 | 热度分 | ETF分 | 情绪分 | RSI14 | RSI状态 | 相对RSI14 | 相对RSI状态 | 20日涨幅 | 20日超额 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: | ---: |",
    ]
    top = trend_scores.head(10).copy()
    for idx, row in top.iterrows():
        lines.append(
            "| {rank} | {name} | {score:.1f} | {trend:.1f} | {heat:.1f} | {etf:.1f} | {sentiment:.1f} | {rsi} | {rsi_state} | {relative_rsi} | {relative_rsi_state} | {ret20} | {ex20} |".format(
                rank=idx + 1,
                name=row["industry_name"],
                score=row.get("rotation_score", row.get("trend_score", 0)),
                trend=row.get("price_trend_score", 0),
                heat=row.get("heat_score", 0),
                etf=row.get("etf_score", 0),
                sentiment=row.get("sentiment_score", 0),
                rsi=format_score(row.get("rsi_14")),
                rsi_state=row.get("rsi_state", "缺失"),
                relative_rsi=format_score(row.get("relative_rsi_14")),
                relative_rsi_state=row.get("relative_rsi_state", "缺失"),
                ret20=format_pct(row.get("ret_20d")),
                ex20=format_pct(row.get("excess_20d")),
            )
        )

    if etf_summary_path and etf_summary_path.exists():
        etf_summary = pd.read_csv(etf_summary_path)
        if not etf_summary.empty:
            lines.extend(
                [
                    "",
                    "## ETF资金观察TOP10",
                    "",
                    "| 排名 | 映射行业 | ETF数量 | 平均涨跌幅 | 总成交额 | 主力净流入 | 最新份额合计 |",
                    "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            for idx, row in etf_summary.head(10).iterrows():
                lines.append(
                    "| {rank} | {industry} | {count} | {pct} | {amount} | {inflow} | {shares} |".format(
                        rank=idx + 1,
                        industry=row["mapped_industry"],
                        count=int(row["etf_count"]),
                        pct=format_pct(row.get("avg_pct_change") / 100),
                        amount=format_number(row.get("total_amount")),
                        inflow=format_number(row.get("total_main_net_inflow")),
                        shares=format_number(row.get("total_latest_shares")),
                    )
                )

    if valuation_summary_path and valuation_summary_path.exists():
        valuation_summary = pd.read_csv(valuation_summary_path)
        if not valuation_summary.empty:
            lines.extend(
                [
                    "",
                    "## 估值温度TOP10",
                    "",
                    "| 排名 | 行业 | PE(TTM) | PB | PE分位 | PB分位 | 状态 | 股票数 |",
                    "| --- | --- | ---: | ---: | ---: | ---: | --- | ---: |",
                ]
            )
            sort_column = "pe_percentile" if "pe_percentile" in valuation_summary.columns else "pe_ttm"
            valuation_top = valuation_summary.sort_values(sort_column, ascending=False, na_position="last").head(10)
            for idx, row in valuation_top.reset_index(drop=True).iterrows():
                lines.append(
                    "| {rank} | {industry} | {pe} | {pb} | {pe_pct} | {pb_pct} | {state} | {count} |".format(
                        rank=idx + 1,
                        industry=row["mapped_industry"],
                        pe=format_score(row.get("pe_ttm")),
                        pb=format_score(row.get("pb")),
                        pe_pct=format_pct(row.get("pe_percentile")),
                        pb_pct=format_pct(row.get("pb_percentile")),
                        state=row.get("valuation_state", "-"),
                        count=int(row["stock_count"]) if not pd.isna(row.get("stock_count")) else "-",
                    )
                )

    if northbound_summary_path and northbound_summary_path.exists():
        northbound_summary = pd.read_csv(northbound_summary_path)
        if not northbound_summary.empty:
            lines.extend(
                [
                    "",
                    "## 北向活跃成交TOP10",
                    "",
                    "| 排名 | 行业 | 个股数 | 活跃成交额 | 估算净额 |",
                    "| --- | --- | ---: | ---: | ---: |",
                ]
            )
            for idx, row in northbound_summary.head(10).iterrows():
                lines.append(
                    "| {rank} | {industry} | {count} | {amount} | {net} |".format(
                        rank=idx + 1,
                        industry=row["mapped_industry"],
                        count=int(row["hsgt_stock_count"]),
                        amount=format_number(row.get("hsgt_active_amount")),
                        net=format_number(row.get("hsgt_net_amount")),
                    )
                )

    if dragon_tiger_summary_path and dragon_tiger_summary_path.exists():
        dragon_tiger_summary = pd.read_csv(dragon_tiger_summary_path)
        if not dragon_tiger_summary.empty:
            lines.extend(
                [
                    "",
                    "## 龙虎榜净买入TOP10",
                    "",
                    "| 排名 | 行业 | 上榜个股数 | 成交额 | 净买入 | 买入额 | 卖出额 |",
                    "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            dragon_top = dragon_tiger_summary.sort_values("top_list_net_amount", ascending=False).head(10)
            for idx, row in dragon_top.reset_index(drop=True).iterrows():
                lines.append(
                    "| {rank} | {industry} | {count} | {amount} | {net} | {buy} | {sell} |".format(
                        rank=idx + 1,
                        industry=row["mapped_industry"],
                        count=int(row["top_list_count"]),
                        amount=format_number(row.get("top_list_amount")),
                        net=format_number(row.get("top_list_net_amount")),
                        buy=format_number(row.get("top_list_buy")),
                        sell=format_number(row.get("top_list_sell")),
                    )
                )

    if zt_summary_path and zt_summary_path.exists():
        zt_summary = pd.read_csv(zt_summary_path)
        if not zt_summary.empty:
            lines.extend(
                [
                    "",
                    "## 情绪异动TOP10",
                    "",
                    "| 排名 | 行业 | 涨停家数 | 涨停占比 | 最高连板 | 封板资金 | 炸板次数 |",
                    "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            for idx, row in zt_summary.head(10).iterrows():
                lines.append(
                    "| {rank} | {industry} | {count} | {ratio} | {days} | {seal} | {open_count} |".format(
                        rank=idx + 1,
                        industry=row["mapped_industry"],
                        count=int(row["limit_up_count"]),
                        ratio=format_pct(row.get("limit_up_ratio")),
                        days=int(row["max_limit_up_days"]) if not pd.isna(row["max_limit_up_days"]) else "-",
                        seal=format_number(row.get("total_seal_amount")),
                        open_count=int(row["open_board_count"]) if not pd.isna(row["open_board_count"]) else "-",
                    )
                )

    lines.extend(
        [
            "",
            "## 观察提示",
            "",
            "- 当前轮动分权重读取自 `config/settings.yaml` 的 `scoring.weights`。",
            "- ETF 到行业、涨停池行业到申万一级行业仍采用关键词映射，后续会逐步维护为更精确的映射表。",
            f"- 多板块走势对比数据已输出：`{comparison_path.as_posix()}`。",
        ]
    )
    for message in extra_messages or []:
        lines.append(f"- {message}")
    lines.append("")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def generate_html_report(
    report_date: str,
    rotation_scores: pd.DataFrame,
    output_path: Path,
    assets_dir: Path,
    *,
    etf_summary_path: Path | None = None,
    zt_summary_path: Path | None = None,
    valuation_summary_path: Path | None = None,
    northbound_summary_path: Path | None = None,
    dragon_tiger_summary_path: Path | None = None,
    extra_messages: list[str] | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    chart_paths = generate_report_charts(report_date, rotation_scores, assets_dir)
    top = rotation_scores.head(10).copy()
    top_columns = [
        "industry_name",
        "rotation_score",
        "price_trend_score",
        "heat_score",
        "etf_score",
        "sentiment_score",
        "ret_20d",
        "excess_20d",
    ]
    top_display = _format_report_table(top[[column for column in top_columns if column in top.columns]])

    sections = [
        f"<h1>A股板块轮动监控日报 - {report_date}</h1>",
        _summary_cards(top),
        _chart_section("核心图表", chart_paths),
        "<h2>综合轮动 TOP10</h2>",
        top_display.to_html(index=False, escape=False, classes="data-table"),
    ]
    sections.extend(_optional_table_section("ETF资金观察", etf_summary_path, ["mapped_industry", "etf_count", "avg_pct_change", "total_amount", "total_main_net_inflow"]))
    sections.extend(_optional_table_section("估值温度", valuation_summary_path, ["mapped_industry", "stock_count", "pe_ttm", "pb", "pe_percentile", "pb_percentile", "valuation_state"]))
    sections.extend(_optional_table_section("北向活跃成交", northbound_summary_path, ["mapped_industry", "hsgt_stock_count", "hsgt_active_amount", "hsgt_net_amount"]))
    sections.extend(_optional_table_section("龙虎榜净买入", dragon_tiger_summary_path, ["mapped_industry", "top_list_count", "top_list_amount", "top_list_net_amount", "top_list_buy", "top_list_sell"]))
    sections.extend(_optional_table_section("情绪异动", zt_summary_path, ["mapped_industry", "limit_up_count", "limit_up_ratio", "max_limit_up_days", "total_seal_amount", "open_board_count"]))

    if extra_messages:
        items = "".join(f"<li>{_escape_html(message)}</li>" for message in extra_messages)
        sections.append(f"<h2>观察提示</h2><ul>{items}</ul>")

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>A股板块轮动监控日报 - {report_date}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #172033; background: #f7f8fb; }}
    h1 {{ margin-bottom: 8px; }}
    h2 {{ margin-top: 32px; }}
    .cards {{ display: grid; grid-template-columns: repeat(4, minmax(160px, 1fr)); gap: 12px; margin: 20px 0; }}
    .card {{ background: #fff; border: 1px solid #dbe1ea; border-radius: 8px; padding: 14px; }}
    .label {{ color: #667085; font-size: 13px; }}
    .value {{ font-size: 24px; font-weight: 700; margin-top: 6px; }}
    .chart-grid {{ display: grid; grid-template-columns: repeat(2, minmax(280px, 1fr)); gap: 16px; }}
    .chart-card {{ background: #fff; border: 1px solid #dbe1ea; border-radius: 8px; padding: 12px; }}
    .chart-card img {{ width: 100%; height: auto; }}
    .data-table {{ border-collapse: collapse; width: 100%; background: #fff; border: 1px solid #dbe1ea; }}
    .data-table th, .data-table td {{ border-bottom: 1px solid #e6eaf0; padding: 8px 10px; text-align: right; }}
    .data-table th:first-child, .data-table td:first-child {{ text-align: left; }}
    .data-table th {{ background: #eef2f7; }}
    a {{ color: #2563eb; }}
  </style>
</head>
<body>
{''.join(sections)}
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")
    return output_path


def generate_report_charts(report_date: str, rotation_scores: pd.DataFrame, assets_dir: Path) -> dict[str, Path]:
    charts: dict[str, Path] = {}
    if rotation_scores.empty:
        return charts

    top = rotation_scores.head(10).sort_values("rotation_score")
    fig = px.bar(
        top,
        x="rotation_score",
        y="industry_name",
        orientation="h",
        labels={"rotation_score": "综合分", "industry_name": "行业"},
        title="综合轮动 TOP10",
    )
    charts["综合轮动TOP10"] = _write_chart(fig, assets_dir / f"rotation_top10_{report_date}")

    contribution_columns = ["price_trend_score", "heat_score", "etf_score", "sentiment_score"]
    if all(column in rotation_scores.columns for column in contribution_columns):
        contribution = rotation_scores.head(10)[["industry_name"] + contribution_columns].copy()
        contribution["趋势贡献"] = contribution["price_trend_score"] * 0.50
        contribution["热度贡献"] = contribution["heat_score"] * 0.20
        contribution["ETF贡献"] = contribution["etf_score"] * 0.15
        contribution["情绪贡献"] = contribution["sentiment_score"] * 0.15
        melted = contribution.melt(
            id_vars=["industry_name"],
            value_vars=["趋势贡献", "热度贡献", "ETF贡献", "情绪贡献"],
            var_name="贡献项",
            value_name="贡献分",
        )
        fig = px.bar(
            melted,
            x="贡献分",
            y="industry_name",
            color="贡献项",
            orientation="h",
            title="综合分贡献拆解",
            labels={"industry_name": "行业"},
        )
        charts["贡献拆解"] = _write_chart(fig, assets_dir / f"score_contribution_{report_date}")
    return charts


def _write_chart(fig, base_path: Path) -> Path:
    html_path = base_path.with_suffix(".html")
    png_path = base_path.with_suffix(".png")
    fig.update_layout(height=480, margin=dict(l=20, r=20, t=56, b=20))
    pio.write_html(fig, html_path, full_html=True, include_plotlyjs="cdn")
    try:
        fig.write_image(png_path, width=1100, height=620, scale=2)
        return png_path
    except Exception:
        return html_path


def _summary_cards(rotation_scores: pd.DataFrame) -> str:
    if rotation_scores.empty:
        return ""
    top = rotation_scores.iloc[0]
    cards = [
        ("轮动第一", str(top.get("industry_name", "-"))),
        ("综合分", format_score(top.get("rotation_score", top.get("trend_score")))),
        ("20日涨幅", format_pct(top.get("ret_20d"))),
        ("20日超额", format_pct(top.get("excess_20d"))),
    ]
    return '<div class="cards">' + "".join(
        f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div></div>'
        for label, value in cards
    ) + "</div>"


def _chart_section(title: str, chart_paths: dict[str, Path]) -> str:
    if not chart_paths:
        return ""
    cards = []
    for name, path in chart_paths.items():
        if path.suffix.lower() == ".png":
            cards.append(f'<div class="chart-card"><h3>{name}</h3><img src="{path.name}" alt="{name}"></div>')
        else:
            cards.append(f'<div class="chart-card"><h3>{name}</h3><a href="{path.name}">打开交互式图表</a></div>')
    return f"<h2>{title}</h2><div class=\"chart-grid\">{''.join(cards)}</div>"


def _optional_table_section(title: str, path: Path | None, columns: list[str]) -> list[str]:
    if path is None or not path.exists():
        return []
    df = pd.read_csv(path)
    if df.empty:
        return []
    display = _format_report_table(df[[column for column in columns if column in df.columns]].head(10))
    return [f"<h2>{title}</h2>", display.to_html(index=False, escape=False, classes="data-table")]


def _format_report_table(df: pd.DataFrame) -> pd.DataFrame:
    display = df.copy()
    for column in display.columns:
        if column.endswith("_ratio") or column.endswith("_share") or column.endswith("_percentile") or column in {"ret_20d", "excess_20d"}:
            display[column] = display[column].map(format_pct)
        elif any(token in column for token in ["amount", "mv", "inflow", "buy", "sell"]):
            display[column] = display[column].map(format_number)
        elif pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(format_score)
    return display


def _escape_html(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_number(value: float | int | None) -> str:
    if pd.isna(value):
        return "-"
    number = float(value)
    if abs(number) >= 100_000_000:
        return f"{number / 100_000_000:.2f}亿"
    if abs(number) >= 10_000:
        return f"{number / 10_000:.2f}万"
    return f"{number:.0f}"


def format_score(value: float | int | None) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value):.1f}"
