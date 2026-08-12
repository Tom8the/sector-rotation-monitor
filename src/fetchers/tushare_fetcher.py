from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests

from src.utils.config import load_local_env

os.environ["NO_PROXY"] = "*"


@dataclass
class TushareFetcher:
    base_url: str
    token_env: str = "TUSHARE_API_KEY"
    request_interval_seconds: float = 0.6
    timeout_seconds: int = 20
    page_size: int = 5000

    def __post_init__(self) -> None:
        load_local_env()
        self.base_url = self.base_url.rstrip("/")
        self._last_request_at = 0.0

    @property
    def token(self) -> str:
        token = os.getenv(self.token_env)
        if not token:
            raise RuntimeError(f"{self.token_env} is not set")
        return token

    def query(self, api_name: str, params: dict[str, Any] | None = None, fields: str = "") -> pd.DataFrame:
        query_params = dict(params or {})
        if fields:
            query_params["fields"] = fields
        query_params.setdefault("limit", self.page_size)

        items: list[list[Any]] = []
        response_fields: list[str] = []
        offset = int(query_params.pop("offset", 0) or 0)
        page_limit = int(query_params["limit"])

        while True:
            self._throttle()
            request_params = dict(query_params)
            request_params["offset"] = offset
            response = requests.get(
                f"{self.base_url}/{api_name.replace('_', '-')}",
                headers={"X-API-Key": self.token},
                params=request_params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            if body.get("code") != 0:
                raise RuntimeError(f"Tushare {api_name} failed: code={body.get('code')} msg={body.get('msg')}")
            data = body.get("data") or {}
            response_fields = data.get("fields", response_fields)
            page_items = data.get("items", []) or []
            items.extend(page_items)

            if not data.get("has_more") or not page_items or len(page_items) < page_limit:
                break
            offset += len(page_items)

        return pd.DataFrame(items, columns=response_fields)

    def trade_cal(self, start_date: str, end_date: str) -> pd.DataFrame:
        return self.query(
            "trade_cal",
            {"exchange": "SSE", "start_date": start_date, "end_date": end_date},
            "exchange,cal_date,is_open",
        )

    def sw_industries(self, source: str = "SW2021", level: str = "L1") -> pd.DataFrame:
        df = self.query(
            "index_classify",
            {"src": source},
            "index_code,industry_name,level,industry_code,is_pub,parent_code",
        )
        if df.empty:
            return df
        return df[df["level"].eq(level)].reset_index(drop=True)

    def sw_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self.query(
            "sw_daily",
            {"ts_code": ts_code, "start_date": start_date, "end_date": end_date},
            "ts_code,trade_date,open,high,low,close,pct_change,vol,amount",
        )

    def index_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self.query(
            "index_daily",
            {"ts_code": ts_code, "start_date": start_date, "end_date": end_date},
            "ts_code,trade_date,open,high,low,close,pct_chg,vol,amount",
        )

    def fund_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self.query(
            "fund_daily",
            {"ts_code": ts_code, "start_date": start_date, "end_date": end_date},
            "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount",
        )

    def daily_basic(self, trade_date: str) -> pd.DataFrame:
        return self.query(
            "daily_basic",
            {"trade_date": trade_date},
            "ts_code,trade_date,pe,pe_ttm,pb,total_mv,circ_mv",
        )

    def stock_basic(self) -> pd.DataFrame:
        return self.query(
            "stock_basic",
            {"list_status": "L"},
            "ts_code,symbol,name,area,industry,list_date",
        )

    def moneyflow_hsgt(self, start_date: str, end_date: str) -> pd.DataFrame:
        return self.query(
            "moneyflow_hsgt",
            {"start_date": start_date, "end_date": end_date},
            "trade_date,ggt_ss,ggt_sz,hgt,sgt,north_money,south_money",
        )

    def hsgt_top10(self, trade_date: str, market_type: str) -> pd.DataFrame:
        return self.query(
            "hsgt_top10",
            {"trade_date": trade_date, "market_type": market_type},
            "trade_date,ts_code,name,close,change,rank,market_type,amount,net_amount,buy,sell",
        )

    def top_list(self, trade_date: str) -> pd.DataFrame:
        return self.query(
            "top_list",
            {"trade_date": trade_date},
            "trade_date,ts_code,name,close,pct_change,turnover_rate,amount,l_sell,l_buy,l_amount,net_amount,net_rate,amount_rate,float_values,reason",
        )

    def margin_detail(self, trade_date: str) -> pd.DataFrame:
        return self.query(
            "margin_detail",
            {"trade_date": trade_date},
            "trade_date,exchange_id,rzye,rzmre,rzche,rqye,rqyl,rqmcl,rqchl",
        )

    def block_trade(self, trade_date: str) -> pd.DataFrame:
        return self.query(
            "block_trade",
            {"trade_date": trade_date},
            "trade_date,ts_code,price,vol,amount,buyer,seller",
        )

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_at
        wait = self.request_interval_seconds - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.time()
