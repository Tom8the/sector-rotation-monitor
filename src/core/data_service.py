from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.core.database import CsvCache
from src.fetchers.akshare_fetcher import AkshareFetcher
from src.fetchers.astock_fetcher import AStockFetcher
from src.fetchers.tushare_fetcher import TushareFetcher


@dataclass
class DataService:
    tushare: TushareFetcher
    cache: CsvCache
    refresh: bool = False
    akshare: AkshareFetcher | None = None
    astock: AStockFetcher | None = None
    events: list[dict[str, str]] = field(default_factory=list)

    def _record_event(
        self,
        dataset: str,
        params: dict[str, Any],
        source: str,
        status: str,
        rows: int,
        message: str = "",
    ) -> None:
        self.events.append(
            {
                "dataset": dataset,
                "params": ";".join(f"{key}={value}" for key, value in sorted(params.items())),
                "source": source,
                "status": status,
                "rows": str(rows),
                "cache_path": str(self.cache.path_for(dataset, params)),
                "message": message,
            }
        )

    def get_sw_industries(self, source: str, level: str) -> pd.DataFrame:
        params = {"source": source, "level": level}
        cached = None if self.refresh else self.cache.read("sw_industries", params)
        if cached is not None and not cached.empty:
            self._record_event("sw_industries", params, "cache", "ok", len(cached))
            return cached
        df = self.tushare.sw_industries(source=source, level=level)
        self.cache.write("sw_industries", params, df)
        self._record_event("sw_industries", params, "remote", "ok", len(df))
        return df

    def get_sw_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        params = {"ts_code": ts_code, "start_date": start_date, "end_date": end_date, "schema_version": "ohlcv_v2"}
        cached = None if self.refresh else self.cache.read("sw_daily", params)
        if cached is not None and not cached.empty:
            self._record_event("sw_daily", params, "cache", "ok", len(cached))
            return cached
        try:
            df = self.tushare.sw_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if not df.empty:
                self.cache.write("sw_daily", params, df)
            self._record_event("sw_daily", params, "tushare", "ok", len(df))
            return df
        except Exception as exc:
            cached = self.cache.read("sw_daily", params)
            if cached is not None:
                self._record_event("sw_daily", params, "fallback_cache", "stale", len(cached), str(exc))
                return cached
            self._record_event("sw_daily", params, "tushare", "error", 0, str(exc))
            raise

    def get_etf_spot(self, trade_date: str) -> pd.DataFrame:
        if self.akshare is None:
            raise RuntimeError("Akshare fetcher is not configured.")
        params = {"trade_date": trade_date}
        cached = None if self.refresh else self.cache.read("ak_etf_spot", params)
        if cached is not None and not cached.empty:
            self._record_event("ak_etf_spot", params, "cache", "ok", len(cached))
            return cached
        try:
            df = self.akshare.etf_spot()
            if not df.empty:
                self.cache.write("ak_etf_spot", params, df)
            self._record_event("ak_etf_spot", params, "akshare", "ok", len(df))
            return df
        except Exception as exc:
            cached = self.cache.read("ak_etf_spot", params)
            if cached is not None:
                self._record_event("ak_etf_spot", params, "fallback_cache", "stale", len(cached), str(exc))
                return cached
            self._record_event("ak_etf_spot", params, "akshare", "error", 0, str(exc))
            raise

    def get_etf_history(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        params = {"code": str(code).zfill(6), "start_date": start_date, "end_date": end_date, "schema_version": "fund_daily_v1"}
        cached = None if self.refresh else self.cache.read("etf_history", params)
        if cached is not None and not cached.empty:
            self._record_event("etf_history", params, "cache", "ok", len(cached))
            return cached
        ts_code = self._etf_ts_code(code)
        try:
            df = self.tushare.fund_daily(ts_code, start_date, end_date)
            if not df.empty:
                self.cache.write("etf_history", params, df)
            self._record_event("etf_history", params, "tushare", "ok", len(df))
            return df
        except Exception as tushare_error:
            if self.akshare is not None:
                try:
                    df = self.akshare.etf_history(str(code), start_date, end_date)
                    if not df.empty:
                        self.cache.write("etf_history", params, df)
                    self._record_event("etf_history", params, "akshare_fallback", "ok", len(df), str(tushare_error))
                    return df
                except Exception as akshare_error:
                    self._record_event("etf_history", params, "tushare+akshare", "error", 0, f"{tushare_error}; {akshare_error}")
                    raise RuntimeError(f"ETF history unavailable for {code}") from akshare_error
            self._record_event("etf_history", params, "tushare", "error", 0, str(tushare_error))
            raise

    @staticmethod
    def _etf_ts_code(code: str) -> str:
        normalized = str(code).split(".")[0].zfill(6)
        return f"{normalized}.SH" if normalized.startswith(("5", "51", "56", "58")) else f"{normalized}.SZ"

    def get_zt_pool(self, trade_date: str) -> pd.DataFrame:
        if self.akshare is None:
            raise RuntimeError("Akshare fetcher is not configured.")
        params = {"trade_date": trade_date}
        cached = None if self.refresh else self.cache.read("ak_zt_pool", params)
        if cached is not None and not cached.empty:
            self._record_event("ak_zt_pool", params, "cache", "ok", len(cached))
            return cached
        try:
            df = self.akshare.zt_pool(trade_date)
            if not df.empty:
                self.cache.write("ak_zt_pool", params, df)
            self._record_event("ak_zt_pool", params, "akshare", "ok", len(df))
            return df
        except Exception as exc:
            cached = self.cache.read("ak_zt_pool", params)
            if cached is not None:
                self._record_event("ak_zt_pool", params, "fallback_cache", "stale", len(cached), str(exc))
                return cached
            self._record_event("ak_zt_pool", params, "akshare", "error", 0, str(exc))
            raise

    def get_index_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        params = {"ts_code": ts_code, "start_date": start_date, "end_date": end_date, "schema_version": "ohlcv_v2"}
        cached = None if self.refresh else self.cache.read("index_daily", params)
        if cached is not None and not cached.empty:
            self._record_event("index_daily", params, "cache", "ok", len(cached))
            return cached
        try:
            df = self.tushare.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if not df.empty:
                self.cache.write("index_daily", params, df)
            self._record_event("index_daily", params, "remote", "ok", len(df))
            return df
        except Exception as exc:
            cached = self.cache.read("index_daily", params)
            if cached is not None:
                self._record_event("index_daily", params, "fallback_cache", "stale", len(cached), str(exc))
                return cached
            self._record_event("index_daily", params, "remote", "error", 0, str(exc))
            raise

    def get_daily_basic(self, trade_date: str) -> pd.DataFrame:
        params = {"trade_date": trade_date}
        cached = None if self.refresh else self.cache.read("daily_basic", params)
        if cached is not None and not cached.empty:
            self._record_event("daily_basic", params, "cache", "ok", len(cached))
            return cached
        try:
            df = self.tushare.daily_basic(trade_date)
            if not df.empty:
                self.cache.write("daily_basic", params, df)
            self._record_event("daily_basic", params, "remote", "ok", len(df))
            return df
        except Exception as exc:
            cached = self.cache.read("daily_basic", params)
            if cached is not None:
                self._record_event("daily_basic", params, "fallback_cache", "stale", len(cached), str(exc))
                return cached
            self._record_event("daily_basic", params, "remote", "error", 0, str(exc))
            raise

    def get_stock_basic(self) -> pd.DataFrame:
        params = {"list_status": "L"}
        cached = None if self.refresh else self.cache.read("stock_basic", params)
        if cached is not None and not cached.empty:
            self._record_event("stock_basic", params, "cache", "ok", len(cached))
            return cached
        try:
            df = self.tushare.stock_basic()
            if not df.empty:
                self.cache.write("stock_basic", params, df)
            self._record_event("stock_basic", params, "remote", "ok", len(df))
            return df
        except Exception as exc:
            cached = self.cache.read("stock_basic", params)
            if cached is not None:
                self._record_event("stock_basic", params, "fallback_cache", "stale", len(cached), str(exc))
                return cached
            self._record_event("stock_basic", params, "remote", "error", 0, str(exc))
            raise

    def get_moneyflow_hsgt(self, start_date: str, end_date: str) -> pd.DataFrame:
        params = {"start_date": start_date, "end_date": end_date}
        cached = None if self.refresh else self.cache.read("moneyflow_hsgt", params)
        if cached is not None and not cached.empty:
            self._record_event("moneyflow_hsgt", params, "cache", "ok", len(cached))
            return cached
        try:
            df = self.tushare.moneyflow_hsgt(start_date, end_date)
            if not df.empty:
                self.cache.write("moneyflow_hsgt", params, df)
            self._record_event("moneyflow_hsgt", params, "remote", "ok", len(df))
            return df
        except Exception as exc:
            cached = self.cache.read("moneyflow_hsgt", params)
            if cached is not None:
                self._record_event("moneyflow_hsgt", params, "fallback_cache", "stale", len(cached), str(exc))
                return cached
            self._record_event("moneyflow_hsgt", params, "remote", "error", 0, str(exc))
            raise

    def get_hsgt_top10(self, trade_date: str, market_type: str) -> pd.DataFrame:
        params = {"trade_date": trade_date, "market_type": market_type}
        cached = None if self.refresh else self.cache.read("hsgt_top10", params)
        if cached is not None and not cached.empty:
            self._record_event("hsgt_top10", params, "cache", "ok", len(cached))
            return cached
        try:
            df = self.tushare.hsgt_top10(trade_date, market_type)
            if not df.empty:
                self.cache.write("hsgt_top10", params, df)
            self._record_event("hsgt_top10", params, "remote", "ok", len(df))
            return df
        except Exception as exc:
            cached = self.cache.read("hsgt_top10", params)
            if cached is not None:
                self._record_event("hsgt_top10", params, "fallback_cache", "stale", len(cached), str(exc))
                return cached
            self._record_event("hsgt_top10", params, "remote", "error", 0, str(exc))
            raise

    def get_top_list(self, trade_date: str) -> pd.DataFrame:
        params = {"trade_date": trade_date}
        cached = None if self.refresh else self.cache.read("top_list", params)
        if cached is not None and not cached.empty:
            self._record_event("top_list", params, "cache", "ok", len(cached))
            return cached
        try:
            df = self.tushare.top_list(trade_date)
            if not df.empty:
                self.cache.write("top_list", params, df)
            self._record_event("top_list", params, "remote", "ok", len(df))
            return df
        except Exception as exc:
            cached = self.cache.read("top_list", params)
            if cached is not None:
                self._record_event("top_list", params, "fallback_cache", "stale", len(cached), str(exc))
                return cached
            self._record_event("top_list", params, "remote", "error", 0, str(exc))
            raise

    def get_sector_fund_flow(self, trade_date: str) -> pd.DataFrame:
        """AKShare first, direct Eastmoney/a-stock-data second, then cache."""
        params = {"trade_date": trade_date}
        cached = None if self.refresh else self.cache.read("sector_fund_flow", params)
        if cached is not None and not cached.empty:
            self._record_event("sector_fund_flow", params, "cache", "ok", len(cached))
            return cached
        errors: list[str] = []
        if self.akshare is not None:
            try:
                df = self.akshare.sector_fund_flow_rank()
                if not df.empty:
                    self.cache.write("sector_fund_flow", params, df)
                    self._record_event("sector_fund_flow", params, "akshare", "ok", len(df))
                    return df
            except Exception as exc:
                errors.append(f"akshare: {exc}")
                self._record_event("sector_fund_flow", params, "akshare", "error", 0, str(exc))
        if self.astock is not None:
            try:
                df = self.astock.eastmoney_sector_fund_flow()
                if not df.empty:
                    self.cache.write("sector_fund_flow", params, df)
                    self._record_event("sector_fund_flow", params, "astock_eastmoney", "ok", len(df))
                    return df
            except Exception as exc:
                errors.append(f"astock: {exc}")
                self._record_event("sector_fund_flow", params, "astock_eastmoney", "error", 0, str(exc))
        cached = self.cache.read("sector_fund_flow", params)
        if cached is not None:
            self._record_event("sector_fund_flow", params, "fallback_cache", "stale", len(cached), "; ".join(errors))
            return cached
        raise RuntimeError("sector fund flow unavailable: " + "; ".join(errors))

    def get_margin_detail(self, trade_date: str) -> pd.DataFrame:
        return self._get_tushare_cached("margin_detail", {"trade_date": trade_date}, lambda: self.tushare.margin_detail(trade_date))

    def get_block_trade(self, trade_date: str) -> pd.DataFrame:
        return self._get_tushare_cached("block_trade", {"trade_date": trade_date}, lambda: self.tushare.block_trade(trade_date))

    def _get_tushare_cached(self, dataset: str, params: dict[str, Any], request: Any) -> pd.DataFrame:
        cached = None if self.refresh else self.cache.read(dataset, params)
        if cached is not None and not cached.empty:
            self._record_event(dataset, params, "cache", "ok", len(cached))
            return cached
        try:
            df = request()
            if not df.empty:
                self.cache.write(dataset, params, df)
            self._record_event(dataset, params, "tushare", "ok", len(df))
            return df
        except Exception as exc:
            cached = self.cache.read(dataset, params)
            if cached is not None:
                self._record_event(dataset, params, "fallback_cache", "stale", len(cached), str(exc))
                return cached
            self._record_event(dataset, params, "tushare", "error", 0, str(exc))
            raise
