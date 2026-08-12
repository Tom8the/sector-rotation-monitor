from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


class CsvCache:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, name: str, params: dict[str, Any]) -> Path:
        digest = hashlib.sha1(json.dumps(params, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
        return self.root / f"{name}_{digest}.csv"

    def read(self, name: str, params: dict[str, Any]) -> pd.DataFrame | None:
        path = self.path_for(name, params)
        if not path.exists():
            return None
        return pd.read_csv(path, dtype={"trade_date": str, "cal_date": str})

    def write(self, name: str, params: dict[str, Any], df: pd.DataFrame) -> Path:
        path = self.path_for(name, params)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return path

