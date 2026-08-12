from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime
from typing import Any

import pandas as pd
import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.config import load_local_env

os.environ["NO_PROXY"] = "*"
load_local_env()
TUSHARE_URL = os.getenv("TUSHARE_URL", "http://datahubco.com/app-api/openapi/v1/tushare")
TUSHARE_API_KEY = os.getenv("TUSHARE_API_KEY")
TIMEOUT = 12


def ok(name: str, rows: int | None = None, fields: list[str] | None = None, sample: Any = None) -> dict[str, Any]:
    return {"source": name, "ok": True, "rows": rows, "fields": fields, "sample": sample}


def fail(name: str, exc: BaseException | str) -> dict[str, Any]:
    return {"source": name, "ok": False, "error": str(exc)}


def tushare_api(api_name: str, params: dict[str, Any], fields: str) -> pd.DataFrame:
    if not TUSHARE_API_KEY:
        raise RuntimeError("TUSHARE_API_KEY is not set")
    query_params = dict(params)
    query_params["fields"] = fields
    query_params["limit"] = 3
    response = requests.get(
        f"{TUSHARE_URL.rstrip('/')}/{api_name.replace('_', '-')}",
        headers={"X-API-Key": TUSHARE_API_KEY},
        params=query_params,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()
    if body.get("code") != 0:
        raise RuntimeError(f"Tushare {api_name} failed: code={body.get('code')} msg={body.get('msg')}")
    data = body.get("data") or {}
    return pd.DataFrame(data.get("items", []), columns=data.get("fields", []))


def test_tushare() -> list[dict[str, Any]]:
    tests: list[dict[str, Any]] = []
    calls = [
        ("trade_cal", {"exchange": "SSE", "start_date": "20260701", "end_date": "20260709"}, "exchange,cal_date,is_open"),
        ("index_daily", {"ts_code": "000300.SH", "start_date": "20260701", "end_date": "20260709"}, "ts_code,trade_date,close,pct_chg,vol,amount"),
        ("daily_basic", {"ts_code": "000001.SZ", "start_date": "20260701", "end_date": "20260709"}, "ts_code,trade_date,pe_ttm,pb,total_mv,circ_mv"),
        ("stock_basic", {"list_status": "L"}, "ts_code,symbol,name,area,industry,list_date"),
    ]
    for api_name, params, fields in calls:
        try:
            df = tushare_api(api_name, params, fields)
            tests.append(ok(f"tushare.{api_name}", len(df), list(df.columns), df.head(2).to_dict("records")))
        except Exception as exc:
            tests.append(fail(f"tushare.{api_name}", exc))
    return tests


def test_akshare() -> list[dict[str, Any]]:
    import akshare as ak

    tests: list[dict[str, Any]] = []
    calls = [
        ("ak.stock_sector_fund_flow_rank", lambda: ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")),
        ("ak.fund_etf_spot_em", ak.fund_etf_spot_em),
        ("ak.stock_zt_pool_em", lambda: ak.stock_zt_pool_em(date="20260709")),
    ]
    for name, func in calls:
        try:
            df = func()
            tests.append(ok(name, len(df), list(df.columns), df.head(2).to_dict("records")))
        except Exception as exc:
            tests.append(fail(name, exc))
        time.sleep(1)
    return tests


def em_get(url: str, params: dict[str, Any] | None = None) -> requests.Response:
    time.sleep(1 + random.random() * 0.3)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://quote.eastmoney.com/",
    }
    response = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
    response.raise_for_status()
    return response


def test_astock_data_paths() -> list[dict[str, Any]]:
    tests: list[dict[str, Any]] = []

    try:
        response = requests.get(
            "https://qt.gtimg.cn/q=sh000001,sz399300,sh000300",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        lines = [line for line in response.text.split(";") if line.strip()]
        tests.append(ok("a-stock-data.tencent_quote", len(lines), ["raw_quote_line"], lines[:2]))
    except Exception as exc:
        tests.append(fail("a-stock-data.tencent_quote", exc))

    try:
        params = {
            "pn": 1,
            "pz": 10,
            "po": 1,
            "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": "m:90+t:2",
            "fields": "f12,f14,f2,f3,f4,f5,f6,f20,f21,f62,f104,f105,f128",
        }
        data = em_get("https://push2.eastmoney.com/api/qt/clist/get", params=params).json()
        rows = ((data.get("data") or {}).get("diff") or [])
        tests.append(ok("a-stock-data.eastmoney_industry_rank", len(rows), list(rows[0].keys()) if rows else [], rows[:2]))
    except Exception as exc:
        tests.append(fail("a-stock-data.eastmoney_industry_rank", exc))

    try:
        params = {
            "pn": 1,
            "pz": 5,
            "po": 1,
            "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": "b:BK0428",
            "fields": "f12,f14,f2,f3,f4,f5,f6,f20,f21,f62",
        }
        data = em_get("https://push2.eastmoney.com/api/qt/clist/get", params=params).json()
        rows = ((data.get("data") or {}).get("diff") or [])
        tests.append(ok("a-stock-data.eastmoney_board_constituents", len(rows), list(rows[0].keys()) if rows else [], rows[:2]))
    except Exception as exc:
        tests.append(fail("a-stock-data.eastmoney_board_constituents", exc))

    try:
        import socket

        from mootdx.quotes import Quotes

        servers = [
            ("119.97.185.59", 7709),
            ("124.70.133.119", 7709),
            ("116.205.183.150", 7709),
            ("123.60.73.44", 7709),
            ("116.205.163.254", 7709),
        ]
        client = None
        server_used = None
        for ip, port in servers:
            try:
                with socket.create_connection((ip, port), timeout=2):
                    client = Quotes.factory(market="std", server=(ip, port))
                    server_used = ip
                    break
            except Exception:
                continue
        if client is None:
            raise RuntimeError("no reachable mootdx server")
        df = client.bars(symbol="000001", frequency=9, start=0, offset=5)
        result = ok("a-stock-data.mootdx_bars", len(df), list(df.columns), df.head(2).to_dict("records"))
        result["server"] = server_used
        tests.append(result)
    except Exception as exc:
        tests.append(fail("a-stock-data.mootdx_bars", exc))

    return tests


def main() -> None:
    results = {
        "tested_at": datetime.now().isoformat(timespec="seconds"),
        "tushare_url": TUSHARE_URL,
        "results": [],
    }
    results["results"].extend(test_tushare())
    results["results"].extend(test_akshare())
    results["results"].extend(test_astock_data_paths())
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
