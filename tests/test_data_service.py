import pandas as pd

from src.core.data_service import DataService
from src.core.database import CsvCache


class DummyTushare:
    def __init__(self):
        self.calls = 0

    def sw_industries(self, source: str, level: str) -> pd.DataFrame:
        self.calls += 1
        return pd.DataFrame([{"index_code": "801001.SI", "industry_name": "电子"}])


def test_data_service_records_remote_and_cache_events(tmp_path):
    cache = CsvCache(tmp_path)
    tushare = DummyTushare()

    first_service = DataService(tushare=tushare, cache=cache)
    first = first_service.get_sw_industries(source="SW2021", level="L1")

    second_service = DataService(tushare=tushare, cache=cache)
    second = second_service.get_sw_industries(source="SW2021", level="L1")

    assert len(first) == 1
    assert len(second) == 1
    assert tushare.calls == 1
    assert first_service.events[0]["source"] == "remote"
    assert second_service.events[0]["source"] == "cache"
    assert second_service.events[0]["dataset"] == "sw_industries"
