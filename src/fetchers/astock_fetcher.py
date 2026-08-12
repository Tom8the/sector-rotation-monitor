from __future__ import annotations

"""Small, dependency-light adapters for stable a-stock-data upstream paths.

The project deliberately owns these calls instead of importing a-stock-data as a
package.  That repository is a collection of provider recipes, not a versioned
runtime dependency.
"""

import time
from dataclasses import dataclass

import pandas as pd
import requests


@dataclass
class AStockFetcher:
    request_interval_seconds: float = 1.2
    timeout_seconds: int = 15

    def __post_init__(self) -> None:
        self._last_request_at = 0.0

    def tencent_quotes(self, symbols: list[str]) -> pd.DataFrame:
        """Fetch latest Tencent quotes for indexes, equities, or ETFs."""
        if not symbols:
            return pd.DataFrame()
        self._throttle()
        response = requests.get(
            "https://qt.gtimg.cn/q=" + ",".join(symbols),
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        rows: list[dict[str, object]] = []
        for line in response.text.split(";"):
            if "~" not in line:
                continue
            symbol = line.split("=", 1)[0].replace("v_", "").strip()
            fields = line.split('"', 2)[1].split("~") if '"' in line else []
            if len(fields) < 34:
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "name": fields[1],
                    "latest_price": pd.to_numeric(fields[3], errors="coerce"),
                    "previous_close": pd.to_numeric(fields[4], errors="coerce"),
                    "pct_change": pd.to_numeric(fields[32], errors="coerce"),
                    "quote_time": fields[30],
                    "source": "astock_tencent",
                }
            )
        return pd.DataFrame(rows)

    def eastmoney_sector_fund_flow(self) -> pd.DataFrame:
        """Fetch the current Eastmoney industry capital-flow ranking directly."""
        self._throttle()
        response = requests.get(
            "https://push2.eastmoney.com/api/qt/clist/get",
            params={
                "pn": 1,
                "pz": 100,
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f62",
                "fs": "m:90+t:2+f:!50",
                "fields": "f12,f14,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f124",
            },
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        rows = ((response.json().get("data") or {}).get("diff") or [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows).rename(
            columns={
                "f12": "sector_code",
                "f14": "sector_name",
                "f3": "pct_change",
                "f62": "main_net_inflow",
                "f184": "main_net_inflow_ratio",
                "f66": "super_large_net_inflow",
                "f72": "large_net_inflow",
                "f78": "medium_net_inflow",
                "f84": "small_net_inflow",
                "f124": "quote_timestamp",
            }
        )
        df["source"] = "astock_eastmoney"
        return df

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_at
        if self.request_interval_seconds > elapsed:
            time.sleep(self.request_interval_seconds - elapsed)
        self._last_request_at = time.time()
