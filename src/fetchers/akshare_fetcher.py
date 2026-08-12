from __future__ import annotations

import time

import pandas as pd


class AkshareFetcher:
    def __init__(self, request_interval_seconds: float = 1.0) -> None:
        self.request_interval_seconds = request_interval_seconds

    def etf_spot(self) -> pd.DataFrame:
        import akshare as ak

        self._throttle()
        return ak.fund_etf_spot_em()

    def etf_history(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch unadjusted daily history for one exchange-traded fund."""
        import akshare as ak

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                self._throttle()
                return ak.fund_etf_hist_em(
                    symbol=str(code).zfill(6),
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="",
                )
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1 + attempt)
        raise RuntimeError(f"ETF history request failed for {code}") from last_error

    def zt_pool(self, trade_date: str) -> pd.DataFrame:
        import akshare as ak

        self._throttle()
        return ak.stock_zt_pool_em(date=trade_date)

    def sector_fund_flow_rank(self, indicator: str = "今日", sector_type: str = "行业资金流") -> pd.DataFrame:
        import akshare as ak

        self._throttle()
        return ak.stock_sector_fund_flow_rank(indicator=indicator, sector_type=sector_type)

    def _throttle(self) -> None:
        time.sleep(self.request_interval_seconds)
