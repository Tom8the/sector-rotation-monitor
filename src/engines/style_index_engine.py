from __future__ import annotations

import pandas as pd


def summarize_style_indexes(index_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for style_name, raw in index_frames.items():
        if raw.empty or "close" not in raw.columns:
            continue
        df = raw.copy().sort_values("trade_date")
        close = pd.to_numeric(df["close"], errors="coerce").dropna()
        if close.empty:
            continue
        rows.append(
            {
                "style_name": style_name,
                "trade_date": str(df["trade_date"].iloc[-1]),
                "close": float(close.iloc[-1]),
                "ret_5d": _return(close, 5),
                "ret_20d": _return(close, 20),
                "ret_60d": _return(close, 60),
            }
        )
    return pd.DataFrame(rows).sort_values("ret_20d", ascending=False, na_position="last").reset_index(drop=True) if rows else pd.DataFrame()


def _return(close: pd.Series, days: int) -> float | None:
    return float(close.iloc[-1] / close.iloc[-days - 1] - 1) if len(close) > days else None
