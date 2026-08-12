from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.history_store import available_snapshots
from src.core.reporter import format_pct
from src.engines.history_engine import (
    build_breadth_series,
    build_rotation_heatmap,
    build_strength_summary,
    latest_rank_changes,
    load_rotation_history,
)
from src.engines.backtest_engine import run_topn_rotation_backtest
from src.engines.risk_engine import build_rotation_signals
from src.engines.research_engine import load_price_research_history, run_walk_forward_grid
from src.engines.portfolio_engine import build_portfolio_plan
from src.engines.style_engine import build_style_summary
from src.utils.config import load_settings, project_path, save_settings


st.set_page_config(
    page_title="AËÇ°ÊùøÂùóËΩÆÂä®ÁõëÊéß",
    page_icon="",
    layout="wide",
)


def available_dates(processed_dir: Path, db_path: Path | None = None) -> list[str]:
    if db_path is not None and db_path.exists():
        db_dates = available_snapshots(db_path)
        if db_dates:
            return db_dates
    files = sorted(processed_dir.glob("rotation_scores_*.csv"), reverse=True)
    if files:
        return [path.stem.replace("rotation_scores_", "") for path in files]
    files = sorted(processed_dir.glob("trend_scores_*.csv"), reverse=True)
    return [path.stem.replace("trend_scores_", "") for path in files]


@st.cache_data(show_spinner=False)
def load_trend_scores(path: str, mtime: float) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"trade_date": str})
    return df


@st.cache_data(show_spinner=False)
def load_comparison_series(path: str, mtime: float) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"trade_date": str})
    df["display_date"] = pd.to_datetime(df["trade_date"].astype(str), format="%Y%m%d")
    return df


@st.cache_data(show_spinner=False)
def load_optional_csv(path: str, mtime: float) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        return pd.DataFrame()
    try:
        return normalize_security_codes(pd.read_csv(csv_path, dtype={"code": str, "ts_code": str, "symbol": str}))
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_text_csv(path: str, mtime: float) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        return pd.DataFrame()
    try:
        return normalize_security_codes(pd.read_csv(csv_path, dtype=str))
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def normalize_security_codes(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for column in ["code", "symbol", "ts_code"]:
        if column not in result.columns:
            continue
        result[column] = result[column].map(_format_security_code)
    return result


def _format_security_code(value: object) -> object:
    if pd.isna(value):
        return value
    text = str(value).strip()
    if not text:
        return text
    if "." in text and text.rsplit(".", 1)[1].upper() in {"SZ", "SH", "BJ"}:
        code, market = text.rsplit(".", 1)
        return code.zfill(6) + "." + market.upper() if code.isdigit() else text
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text.zfill(6) if text.isdigit() and len(text) <= 6 else text


def prepare_chart_data(df: pd.DataFrame, selected_names: list[str], period: str, range_label: str) -> pd.DataFrame:
    data = df[df["name"].isin(selected_names)].copy()
    if data.empty:
        return data

    max_date = data["display_date"].max()
    range_days = {
        "Ëøë1Êúà": 30,
        "Ëøë3Êúà": 90,
        "Ëøë6Êúà": 180,
        "Ëøë1Âπ¥": 365,
    }.get(range_label)
    if range_days:
        min_date = max_date - pd.Timedelta(days=range_days)
        data = data[data["display_date"] >= min_date]

    if period != "Êó•":
        freq = "W-FRI" if period == "Âë®" else "ME"
        resampled_frames = []
        for name, group in data.groupby("name"):
            sampled = (
                group.sort_values("display_date")
                .set_index("display_date")
                .resample(freq)
                .last()
                .dropna(subset=["close"])
                .reset_index()
            )
            sampled["name"] = name
            resampled_frames.append(sampled)
        data = pd.concat(resampled_frames, ignore_index=True) if resampled_frames else data.iloc[0:0]

    frames = []
    for name, group in data.groupby("name"):
        group = group.sort_values("display_date").copy()
        if group.empty:
            continue
        group["cum_return"] = group["close"] / group["close"].iloc[0] - 1
        frames.append(group)
    if not frames:
        return pd.DataFrame(columns=data.columns)
    return pd.concat(frames, ignore_index=True)


PAGE_HELP = {
    "overview": """**Áî®ÈÄî**ÔºöÊåâÁªºÂêàËØÑÂàÜÊéíÂàó 31 ‰∏™Áî≥‰∏á‰∏ÄÁ∫ßË°å‰∏öÔºåÂø´ÈÄüËØÜÂà´ÂΩìÂâçÁõ∏ÂØπÂº∫ÂäøÊñπÂêë„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**ÔºöÁªºÂêàË∂ãÂäø„ÄÅÊàê‰∫§ÁÉ≠Â∫¶„ÄÅETF ËµÑÈáëÂíåÊ∂®ÂÅúÊÉÖÁª™ÔºõÁº∫Â§±Âõ†Â≠ê‰ºöËá™Âä®ÂâîÈô§ÊùÉÈáçÔºå‰∏çÊåâÈõ∂ÂàÜÂ§ÑÁêÜ„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**ÔºöÈ´òÂàÜ‰ª£Ë°®Â§öÁª¥‰ø°Âè∑ËæÉÂº∫Ôºå‰ªçÂ∫îÁªìÂêàÈ£éÈô©‰ø°Âè∑ÂíåËµ∞ÂäøÊåÅÁª≠ÊÄßÔºå‰∏çËÉΩÁõ¥Êé•‰Ωú‰∏∫‰∫§ÊòìÊåá‰ª§„ÄÇ""",
    "detail": """**Áî®ÈÄî**Ôºö‰∏ãÈíªÂçï‰∏ÄË°å‰∏öÔºåÊü•ÁúãË∂ãÂäø„ÄÅËØÑÂàÜË¥°ÁåÆ„ÄÅ‰º∞ÂÄº„ÄÅETF„ÄÅÊ∂®ÂÅúÁ≠âËØÅÊçÆ„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**ÔºöË°å‰∏öÊó•Á∫øÊù•Ëá™ TushareÔºõETF„ÄÅÊ∂®ÂÅú„ÄÅÂåóÂêë„ÄÅÈæôËôéÊ¶úÁ≠âÊåâË°å‰∏öÊò†Â∞ÑÊ±áÊÄª„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**Ôºö‰ºòÂÖàÁúãË∂ãÂäøÁä∂ÊÄÅ„ÄÅËµÑÈáëÁä∂ÊÄÅ„ÄÅÈ£éÈô©ÊèêÁ§∫ÂíåËØÑÂàÜÂÆåÊï¥Â∫¶ÊòØÂê¶‰∏ÄËá¥„ÄÇ""",
    "compare": """**Áî®ÈÄî**ÔºöÊØîËæÉÂ§ö‰∏™Ë°å‰∏öÂèäÊ≤™Ê∑±300Âú®‰∏çÂêåÂå∫Èó¥ÁöÑÁ¥ØËÆ°Ê∂®Ë∑åÊàñÁÇπ‰ΩçËµ∞Âäø„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**Ôºö‰ΩøÁî®Áî≥‰∏á‰∏ÄÁ∫ßË°å‰∏öÊó•Á∫øÂíåÊ≤™Ê∑±300Êó•Á∫øÔºõË°å‰∏öÊåâÂΩìÂâçÁªºÂêàÂàÜÊéíÂ∫èÈÄâÊã©„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**ÔºöÈáçÁÇπËßÇÂØüÁõ∏ÂØπÂü∫ÂáÜÁöÑÊåÅÁª≠Âº∫Âº±ÔºåËÄåÈùûÂè™ÁúãÂçïÊó•Ê∂®ÂπÖ„ÄÇ""",
    "etf": """**Áî®ÈÄî**ÔºöËßÇÂØüË°å‰∏ö‰ª£Ë°® ETF ÁöÑÈò∂ÊÆµÊ∂®Ë∑å‰∏éÊàê‰∫§È¢ùÈáèËÉΩ„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**ÔºöÊØè‰∏™Ë°å‰∏öÈÄâÂèñÊàê‰∫§È¢ùÊúÄÈ´òÁöÑ 1 Âè™Â∑≤Êò†Â∞Ñ ETFÔºõÂéÜÂè≤Êó•Á∫ø‰ºòÂÖàÊù•Ëá™ Tushare `fund_daily`ÔºåAKShare ‰ªÖ‰ΩúÂÖúÂ∫ï„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**ÔºöÈáèËÉΩÊåÅÁª≠ÊîæÂ§ß‰∏îËµ∞ÂäøËΩ¨Âº∫Êõ¥ÊúâÂèÇËÄÉ‰ª∑ÂÄºÔºõÂΩìÊó•Âø´ÁÖß‰ªÖ‰ΩúËæÖÂä©„ÄÇ""",
    "valuation": """**Áî®ÈÄî**ÔºöÂà§Êñ≠Ë°å‰∏ö‰º∞ÂÄºÁõ∏ÂØπÈ´ò‰ΩéÂèäÂÖ∂ÂéÜÂè≤‰ΩçÁΩÆ„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**ÔºöTushare `daily_basic` ÁöÑ PE(TTM)„ÄÅPB„ÄÅÂ∏ÇÂÄºÔºåÊåâËÇ°Á•®Ë°å‰∏öÊò†Â∞ÑÊ±áÊÄª„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**Ôºö‰º∞ÂÄºÈÄÇÂêàÂÅöÈ£éÈô©Á∫¶ÊùüÔºå‰∏çËÉΩËÑ±Á¶ªÁõàÂà©„ÄÅÊôØÊ∞îÂíåË∂ãÂäøÂçïÁã¨Âà§Êñ≠„ÄÇ""",
    "northbound": """**Áî®ÈÄî**ÔºöËßÇÂØüÂåóÂêëÊï¥‰ΩìÊµÅÂêëÔºå‰ª•ÂèäÂ§ñËµÑÂΩìÊó•ÈáçÁÇπ‰∫§ÊòìÁöÑË°å‰∏öÂíå‰∏™ËÇ°„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**ÔºöTushare `moneyflow_hsgt`„ÄÅ`hsgt_top10`ÔºõHGT ‰∏∫Ê≤™ËÇ°ÈÄöÔºåSGT ‰∏∫Ê∑±ËÇ°ÈÄö„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**ÔºöÊ¥ªË∑ÉÊàê‰∫§ÂèçÊò†ÂÖ≥Ê≥®Â∫¶Ôºå‰∏ç‰∏ÄÂÆöÁ≠â‰∫éÂáÄ‰π∞ÂÖ•ÔºõÂ∫î‰∏éË°å‰∏öË∂ãÂäøÂíåËµÑÈáë‰ø°Âè∑‰∫§ÂèâÈ™åËØÅ„ÄÇ""",
    "sentiment": """**Áî®ÈÄî**ÔºöËØÜÂà´Áü≠Á∫øËµÑÈáëÈõÜ‰∏≠„ÄÅÊÉÖÁª™Êâ©Êï£ÂíåÁÇ∏ÊùøÂàÜÊ≠ßÊâÄÂú®Ë°å‰∏ö„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**ÔºöAKShare Ê∂®ÂÅúÊ±†ÔºåÊ±áÊÄªÊ∂®ÂÅúÂÆ∂Êï∞„ÄÅËøûÊùøÈ´òÂ∫¶„ÄÅÂ∞ÅÊùøËµÑÈáëÂíåÁÇ∏ÊùøÊÉÖÂÜµ„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**ÔºöÊ∂®ÂÅúÊâ©Êï£ÈÖçÂêàË∂ãÂäøËµ∞Âº∫ÊòØÁ°ÆËÆ§ÔºõÈ´òËøûÊùø„ÄÅÁÇ∏ÊùøÂ¢ûÂ§öÂàôÊèêÁ§∫ËøΩÈ´òÈ£éÈô©„ÄÇ""",
    "flow": """**Áî®ÈÄî**ÔºöÁªºÂêàËßÇÂØüË°å‰∏ö‰∏ªÂäõËµÑÈáë„ÄÅËûçËµÑËûçÂà∏„ÄÅÂ§ßÂÆó‰∫§ÊòìÂèäÂÖ∂ÂéÜÂè≤ÂèòÂåñ„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**ÔºöË°å‰∏ö‰∏ªÂäõËµÑÈáë‰ºòÂÖà AKShare„ÄÅÂ§±Ë¥•Êó∂‰∏úÊñπË¥¢ÂØåË°•‰ΩçÔºõËûçËµÑËûçÂà∏ÂíåÂ§ßÂÆó‰∫§ÊòìÊù•Ëá™ Tushare„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**ÔºöËøûÁª≠ÊµÅÂÖ•ÊØîÂçïÊó•ÊµÅÂÖ•Êõ¥Êúâ‰ª∑ÂÄºÔºõ‰∏ªÂäõËµÑÈáëÂè£ÂæÑ‰∏çËÉΩÁ≠âÂêå‰∫éÊú∫ÊûÑÁúüÂÆûÊåÅ‰ªì„ÄÇ""",
    "risk": """**Áî®ÈÄî**ÔºöÊääË∂ãÂäø„ÄÅËµÑÈáë„ÄÅÊÉÖÁª™„ÄÅ‰º∞ÂÄº‰∏éÊï∞ÊçÆÂÆåÊï¥Â∫¶Ê±áÊÄªÊàêÈ£éÈô©ÊèêÁ§∫„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**ÔºöÂ§çÁî®Ë°å‰∏öËØÑÂàÜ„ÄÅRSI„ÄÅÁõ∏ÂØπÂº∫Âº±„ÄÅ‰∏ªÂäõËµÑÈáë„ÄÅÂåóÂêë„ÄÅETF ÂíåÊ∂®ÂÅúÊÉÖÁª™„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**ÔºöÁî®‰∫éËØÜÂà´ËøáÁÉ≠„ÄÅÊã•Êå§„ÄÅËÉåÁ¶ªÂíåË∂ãÂäøËµ∞Âº±Ôºå‰∏çÈ¢ÑÊµãÊ∂®Ë∑åÔºå‰πü‰∏çÊõø‰ª£‰ªì‰ΩçÁ∫™Âæã„ÄÇ""",
    "portfolio": """**Áî®ÈÄî**ÔºöÂ∞ÜË°å‰∏öËØÑÂàÜËΩ¨‰∏∫ÂèóË°å‰∏öÊï∞Èáè„ÄÅÂçïË°å‰∏ö‰∏äÈôê„ÄÅÁé∞ÈáëÁºìÂÜ≤ÂíåÈ£éÊ†ºÊö¥Èú≤Á∫¶ÊùüÁöÑÁ†îÁ©∂ÁªÑÂêà„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**Ôºö‰ΩøÁî®È£éÈô©‰ø°Âè∑„ÄÅÁªºÂêàËØÑÂàÜÂíå `settings.yaml` ÁöÑÈ£éÊ†ºÂàÜÁªÑ„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**ÔºöÈÖçÁΩÆÂÄôÈÄâÊúâÂª∫ËÆÆÊùÉÈáçÔºõËßÇÂØüÂÄôÈÄâ‰ªÖÁî®‰∫éË∑üË∏™ÔºåÊùÉÈáç‰∏∫ 0„ÄÇËØ•È°µ‰∏çËøûÊé•Ë¥¶Êà∑„ÄÇ""",
    "candidates": """**Áî®ÈÄî**Ôºö‰ªéÁªÑÂêàÂÖ≥Ê≥®Ë°å‰∏ö‰∏≠ÁîüÊàêÈúÄË¶Å‰∫∫Â∑•Á†îÁ©∂ÁöÑ‰∏™ËÇ°‰∫ã‰ª∂Ê∏ÖÂçï„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**ÔºöËûçÂêàË°å‰∏öËØÑÂàÜ„ÄÅËÇ°Á•®Êò†Â∞Ñ„ÄÅÊ∂®ÂÅúÊ±†„ÄÅÈæôËôéÊ¶ú„ÄÅÂåóÂêëÊ¥ªË∑ÉÂíå‰º∞ÂÄºÂø´ÁÖßÔºõÂÄôÈÄâÊ±†Ë¶ÜÁõñÂÖ®ÈÉ®Ë°å‰∏ö„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**ÔºöÂÄôÈÄâÂàÜ‰ª£Ë°®ÂèØÊ†∏Êü•‰∫ã‰ª∂ÁöÑÈõÜ‰∏≠Á®ãÂ∫¶Ôºå‰∏ç‰ª£Ë°®‰π∞ÂÖ•‰ø°Âè∑ÊàñÈ¢ÑÊúüÊî∂Áõä„ÄÇ""",
    "style": """**Áî®ÈÄî**ÔºöËØÜÂà´Â∏ÇÂú∫ÂÅèÂ•ΩÁöÑÊàêÈïø„ÄÅÂà∂ÈÄ†„ÄÅÊ∂àË¥π„ÄÅÂë®Êúü„ÄÅÈáëËûçÊàñÈò≤Âæ°È£éÊ†º„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**ÔºöTushare È£éÊ†ºÊåáÊï∞Êó•Á∫ø‰∏éË°å‰∏öËØÑÂàÜÔºåÈ£éÊ†ºÂàÜÁªÑÁª¥Êä§Âú® `settings.yaml`„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**ÔºöÈ£éÊ†ºÂº∫‰∏ç‰ª£Ë°®ÁªÑÂÜÖÊØè‰∏™Ë°å‰∏öÈÉΩÂº∫ÔºõÂèØÁî®‰∫éÂèëÁé∞ÁªÑÂêàÁöÑÈöêÊÄßÈ£éÊ†ºÈõÜ‰∏≠„ÄÇ""",
    "history": """**Áî®ÈÄî**ÔºöÂõûÁúãË°å‰∏öËØÑÂàÜ„ÄÅÊéíÂêç„ÄÅÁÉ≠ÂäõÂõæÂíåÊâ©Êï£ËøáÁ®ã„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**ÔºöÂÆûÊó∂Â§öÁª¥Âø´ÁÖß‰ªéÁ≥ªÁªüËøêË°åÊó•Ëµ∑ÁßØÁ¥ØÔºõ‰ª∑Ê†ºÁ†îÁ©∂Â∫èÂàóÂè™Áî®ÂΩìÊó∂ÂèØÂæó‰ª∑Ê†ºÂíåÊàê‰∫§È¢ùÔºåË¶ÜÁõñÊõ¥ÈïøÂéÜÂè≤„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**Ôºö‰∏§Â•óÂ∫èÂàóÁöÑÂõ†Â≠êË¶ÜÁõñ‰∏çÂêåÔºå‰∏çËÉΩÁõ¥Êé•ÊãºÊé•‰∏∫Âêå‰∏ÄÂè£ÂæÑ„ÄÇ""",
    "backtest": """**Áî®ÈÄî**ÔºöÈ™åËØÅÊåâË°å‰∏öËØÑÂàÜÈÄâÂèñ TopN Ë°å‰∏öÁöÑÂéÜÂè≤Ë°®Áé∞ÂíåÂèÇÊï∞Á®≥ÂÆöÊÄß„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**Ôºö‰ª∑Ê†ºÁ†îÁ©∂ËØÑÂàÜ„ÄÅË°å‰∏öÂºÄÈ´ò‰ΩéÊî∂Êó•Á∫øÂíåÊ≤™Ê∑±300Âü∫ÂáÜÔºõ‰ºòÂÖàÊ¨°Êó•ÂºÄÁõòËøõÂÖ•ÔºåÁº∫Â§±Êó∂ÂõûÈÄÄÊî∂Áõò‰ª∑„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**ÔºöÂÖ≥Ê≥®Ê†∑Êú¨Â§ñË∂ÖÈ¢ù„ÄÅÊç¢ÊâãÂíåÊâßË°åÈôêÂà∂„ÄÇÂèÇÊï∞ÁΩëÊ†ºÈ™åËØÅÈúÄÊâãÂä®ËøêË°åÔºåÈÅøÂÖçÈòªÂ°ûÈ°µÈù¢„ÄÇ""",
    "quality": """**Áî®ÈÄî**ÔºöÊ£ÄÊü•ÂΩìÊó•Êï∞ÊçÆË¶ÜÁõñ„ÄÅË°å‰∏öÊò†Â∞Ñ„ÄÅÊï∞ÊçÆÊ∫êÈôçÁ∫ßÂíåÊó•‰ªªÂä°ËøêË°åÁä∂ÊÄÅ„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**ÔºöÊØèÊó•‰ªªÂä°ÁîüÊàêÁöÑÊï∞ÊçÆË¥®Èáè„ÄÅÊù•Ê∫êÂÅ•Â∫∑„ÄÅÊò†Â∞ÑÂÆ°ËÆ°ÂèäË∞ÉÂ∫¶Êó•Âøó„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**ÔºöÂá∫Áé∞ÂºÇÂ∏∏Êó∂ÂÖàÁúãÊï∞ÊçÆÊ∫êÂÅ•Â∫∑ÊòéÁªÜÔºåÂÜçÂÜ≥ÂÆöÊòØÂê¶‰ΩøÁî®ÂΩìÊó•ËØÑÂàÜ„ÄÇ""",
    "config": """**Áî®ÈÄî**ÔºöÁª¥Êä§ËØÑÂàÜÊùÉÈáç„ÄÅËßÇÂØüË°å‰∏ö„ÄÅÈ£éÊ†ºÂàÜÁªÑÂíåË°å‰∏öÊò†Â∞ÑËßÑÂàô„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**ÔºöÈÖçÁΩÆÂÜôÂÖ• `config/settings.yaml` ÂèäÊò†Â∞Ñ YAML Êñá‰ª∂„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**Ôºö‰øÆÊîπÊùÉÈáçÊàñÊò†Â∞ÑÂêéÈúÄÈáçÊñ∞ËøêË°åÊó•‰ªªÂä°ÔºåÊâç‰ºöÂΩ±ÂìçÊñ∞ÁöÑËØÑÂàÜÂíåÊ±áÊÄª„ÄÇ""",
    "report": """**Áî®ÈÄî**ÔºöÊü•ÁúãÂπ∂ÊâìÂºÄÂΩìÊó•ÁîüÊàêÁöÑ Markdown ‰∏é HTML Á†îÁ©∂Êó•Êä•„ÄÇ\n\n**Êï∞ÊçÆ‰∏éÂè£ÂæÑ**ÔºöÊó•Êä•Áî±ÊØèÊó•‰ªªÂä°Âü∫‰∫éÂΩìÊó•ÂÆåÊï¥Âø´ÁÖßËá™Âä®ÁîüÊàê„ÄÇ\n\n**‰ΩøÁî®Ë¶ÅÁÇπ**ÔºöÈÄÇÂêàÊî∂ÁõòÂêéÂø´ÈÄüÂ§çÁõòÔºõÂ∫îÁªìÂêàÊï∞ÊçÆË¥®ÈáèÁä∂ÊÄÅÈòÖËØª„ÄÇ""",
}


def section_header(title: str, help_key: str) -> None:
    title_col, help_col = st.columns([20, 1])
    with title_col:
        st.subheader(title)
    with help_col:
        with st.popover("?", help="Êü•ÁúãÈ°µÈù¢ËØ¥Êòé", type="tertiary", key=f"help_{help_key}"):
            st.markdown(PAGE_HELP[help_key])


def install_popover_tab_close_handler() -> None:
    """Close help popovers when the client changes the active Streamlit tab."""
    components.html(
        """
        <script>
        const parentWindow = window.parent;
        const parentDocument = parentWindow.document;
        if (!parentWindow.__sectorRotationPopoverCloseHandler) {
          parentWindow.__sectorRotationPopoverCloseHandler = true;
          parentDocument.addEventListener("click", (event) => {
            if (!event.target.closest('[role="tab"]')) return;
            window.setTimeout(() => {
              parentDocument.querySelectorAll('button[aria-expanded="true"]').forEach((button) => button.click());
            }, 0);
          }, true);
        }
        </script>
        """,
        height=0,
        width=0,
    )


def metric_value(df: pd.DataFrame, column: str, formatter=str) -> str:
    if df.empty or column not in df.columns:
        return "-"
    return formatter(df[column].iloc[0])


def format_amount(value: float | int | None) -> str:
    if pd.isna(value):
        return "-"
    number = float(value)
    if abs(number) >= 100_000_000:
        return f"{number / 100_000_000:.2f}‰∫ø"
    if abs(number) >= 10_000:
        return f"{number / 10_000:.2f}‰∏á"
    return f"{number:.0f}"


def build_score_contribution(df: pd.DataFrame, score_column: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    required = ["industry_name", score_column, "price_trend_score", "heat_score", "etf_score", "sentiment_score"]
    if any(column not in df.columns for column in required):
        return pd.DataFrame()

    contribution = df.head(12).copy()
    weights = score_weights()
    for component, label in [("price_trend_score", "Ë∂ãÂäøË¥°ÁåÆ"), ("heat_score", "ÁÉ≠Â∫¶Ë¥°ÁåÆ"), ("etf_score", "ETFË¥°ÁåÆ"), ("sentiment_score", "ÊÉÖÁª™Ë¥°ÁåÆ")]:
        effective_column = f"effective_{component}_weight"
        contribution[label] = contribution[component] * (contribution[effective_column] if effective_column in contribution.columns else weights[component])
    return contribution.melt(
        id_vars=["industry_name", score_column],
        value_vars=["Ë∂ãÂäøË¥°ÁåÆ", "ÁÉ≠Â∫¶Ë¥°ÁåÆ", "ETFË¥°ÁåÆ", "ÊÉÖÁª™Ë¥°ÁåÆ"],
        var_name="Ë¥°ÁåÆÈ°π",
        value_name="Ë¥°ÁåÆÂàÜ",
    )


def file_mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


def score_weights() -> dict[str, float]:
    defaults = {"price_trend_score": 0.50, "heat_score": 0.20, "etf_score": 0.15, "sentiment_score": 0.15}
    defaults.update(settings.get("scoring", {}).get("weights", {}))
    total = sum(float(value) for value in defaults.values())
    if total <= 0:
        total = 1
    return {key: float(value) / total for key, value in defaults.items()}


install_popover_tab_close_handler()

settings = load_settings()
processed_dir = project_path(settings["paths"]["processed_data_dir"])
reports_dir = project_path(settings["paths"]["reports_dir"])
logs_dir = project_path(settings["paths"].get("logs_dir", "data/logs"))
db_path = project_path(settings["paths"].get("duckdb_path", "data/sector_rotation.duckdb"))

dates = available_dates(processed_dir, db_path)
if not dates:
    st.error("Êú™ÊâæÂà∞Â∑≤ÁîüÊàêÁöÑË∂ãÂäøÊï∞ÊçÆ„ÄÇËØ∑ÂÖàËøêË°å scripts/daily_run.py„ÄÇ")
    st.stop()

with st.sidebar:
    st.title("AËÇ°ÊùøÂùóËΩÆÂä®ÁõëÊéß")
    selected_date = st.selectbox("ÂÆåÊï¥Âø´ÁÖßÊó•Êúü", dates, index=0)
    st.caption("Â§öÁª¥Êî∂ÁõòÂêéÂø´ÁÖß")
    st.divider()
    st.caption(f"ÂéÜÂè≤Êó•Êúü: {len(dates)} ‰∏™")
    st.caption("Â≠òÂÇ®: DuckDB + CSV")
    st.caption(f"Âä†Â∑•ÁõÆÂΩï: {processed_dir}")
    st.caption(f"ÂéÜÂè≤Â∫ì: {db_path}")

rotation_path = process€}˝÷⁄$z{-ÆÈ‹j◊ù"¬b'∂ñÁBá7V÷÷'ï˜&˜u≤wG&FUˆ6˜VÁBu“ó“"ê¢÷WG&ñ5ˆ6ˆ«5≥“Ê÷WG&ñ2Ç.à9ŒxËr"¬f˜&÷E˜7Bá7V÷÷'ï˜&˜u≤'vñÂ˜&FR%“íê¢÷WG&ñ5ˆ6ˆ«5≥%“Ê÷WG&ñ2Ç.[õ>Yÿ~iKny∏¢"¬f˜&÷E˜7Bá7V÷÷'ï˜&˜u≤&fu˜&WGW&‚%“íê¢÷WG&ñ5ˆ6ˆ«5≥5“Ê÷WG&ñ2Ç.{J˛äÍiKny∏¢"¬f˜&÷E˜7Bá7V÷÷'ï˜&˜u≤'F˜F≈˜&WGW&‚%“íê¢÷WG&ñ5ˆ6ˆ«5≥E“Ê÷WG&ñ2Ç.i»ZJ~YπÓi*B"¬f˜&÷E˜7Bá7V÷÷'ï˜&˜u≤&÷ÖˆG&vF˜v‚%“íê¢÷WG&ñ5ˆ6ˆ«5≥U“Ê÷WG&ñ2Ç.yªéZ˚ûäŒKâÆzÿûiÿ2"¬f˜&÷E˜7Bá7V÷÷'ï˜&˜u≤&fuˆWÜ6W75˜&WGW&‚%“íê¢÷WG&ñ5ˆ6ˆ«5≥e“Ê÷WG&ñ2Ç.yªéZ˚ûk*Æk{3"¬f˜&÷E˜7Bá7V÷÷'ï˜&˜u≤&fuˆ&VÊ6Ü÷&µˆWÜ6W75˜&WGW&‚%“íê¢÷WG&ñ5ˆ6ˆ«5≥u“Ê÷WG&ñ2Ç.[õ>Yÿ~h⁄.hò≤"¬f˜&÷E˜7Bá7V÷÷'ï˜&˜u≤&fu˜GW&Ê˜fW"%“íê†¢fñr“ÇÊ∆ñÊRÄ¢G&FW2¿¢É“&WÜóEˆFFR"¿¢ì“&WVóGïˆ7W'fR"¿¢÷&∂W'3’G'VR¿¢∆&V«3◊≤&WÜóEˆFFR#¢.òX{Æiz^i…Ú"¬&WVóGïˆ7W'fR#¢.XxX¬'“¿¢FóF∆S“%F˜‚ã⁄ÓX™éXxXŒiª.{´Ú"¿¢ê¢fñrÁWFFUˆ∆ñ˜WBÜÜVñváC”C#¬÷&vñ„÷Fñ7BÜ√”#¬#”#¬C”CÇ¬#”#íê¢7BÁ∆˜F«ïˆ6Ü'BÜfñr¬vñGFÉ“'7G&WF6Ç"ê†¢G&FUˆFó7∆í“G&FW2Ê6˜íÇê¢f˜"6ˆ«V÷‚ñ‚≤'W&ñˆE˜&WGW&‚"¬&w&˜75˜&WGW&‚"¬&6˜7B"¬&ñÊGW7G'ïˆWV≈˜vVñváE˜&WGW&‚"¬&&VÊ6Ü÷&µ˜&WGW&‚"¬'GW&Ê˜fW""¬&ñÁfW7FVE˜vVñváB%”†¢ñb6ˆ«V÷‚ñ‚G&FUˆFó7∆íÊ6ˆ«V÷Á3†¢G&FUˆFó7∆ï∂6ˆ«V÷Â““G&FUˆFó7∆ï∂6ˆ«V÷Â“Ê÷Üf˜&÷E˜7Bê¢G&FUˆFó7∆ï≤&WVóGïˆ7W'fR%““G&FUˆFó7∆ï≤&WVóGïˆ7W'fR%“Ê÷Ü∆÷&Ff«VS¢b'∑f«VS¢„6g“"ê¢7BÊFFg&÷RÄ¢G&FUˆFó7∆íÁ&VÊ÷RÄ¢6ˆ«V÷Á3◊∞¢'6Ê6Ü˜EˆFFR#¢.ä¯NXànizR"¿¢&VÁG'ïˆFFR#¢.KõXZ^izR"¿¢&VÁG'ï˜&ñ6U˜6˜W&6R#¢.KõXZ^Kª~X˙>[ËB"¿¢&6ˆÁ7G&ñÊVEˆWÜ6«W6ñˆÁ2#¢.ã{>zõÆã¯~k∫B"¿¢'GW&Ê˜fW"#¢.h⁄.hòæj˘NKË≤"¿¢&ñÁfW7FVE˜vVñváB#¢.ZÈÓôò^iÿ>y∏Æi´NôÀ""¿¢&WÜóEˆFFR#¢.XŸnX{ÆizR"¿¢'F˜ˆ‚#¢.h»i»ûi[òxÚ"¿¢&Üˆ∆EˆFó2#¢.h»i»ûZJûi["¿¢&ñÊGW7G'ïˆ6˜VÁB#¢.i»ûiXéäŒKâÆi["¿¢'6V∆V7FVEˆñÊGW7G&ñW2#¢.XZ^òûäŒKâ¢"¿¢'W&ñˆE˜&WGW&‚#¢.XÀÆô{NiKny∏¢"¿¢&w&˜75˜&WGW&‚#¢.hâi ŒXòﬁiKny∏¢"¿¢&6˜7B#¢.h⁄.Kπ>hâi ¬"¿¢&ñÊGW7G'ïˆWV≈˜vVñváE˜&WGW&‚#¢.äŒKâÆzÿûiÿ>iKny∏¢"¿¢&&VÊ6Ü÷&µ˜&WGW&‚#¢.k*Æk{3iKny∏¢"¿¢&WVóGïˆ7W'fR#¢.XxX¬"¿¢–¢í¿¢vñGFÉ“'7G&WF6Ç"¿¢ÜñFUˆñÊFWÉ’G'VR¿¢ê†¢7BÁ7V&ÜVFW"Ç.j~i ŒXh^ZInX¯.i[ö®Œä¯"ê¢w&ñEˆÜó7F˜'í“&W6V&6ÖˆÜó7F˜'íñbÊ˜B&W6V&6ÖˆÜó7F˜'íÊV◊GíV«6R&˜FFñˆÂˆÜó7F˜'ê¢w&ñE˜&ñ6W2“&W6V&6ÖˆñÊGW7G'ïˆFñ«íñbÊ˜B&W6V&6ÖˆñÊGW7G'ïˆFñ«íÊV◊GíV«6RñÊGW7G'ïˆFñ«ê¢ñbw&ñEˆÜó7F˜'íÊV◊Gí˜"w&ñE˜&ñ6W2ÊV◊Gí˜"w&ñEˆÜó7F˜'ï≤'6Ê6Ü˜EˆFFR%“ÊÁVÊóVRÇí¬†¢7BÊñÊfÚÇ.X¯.i[ö®Œä¯ô»ähà{>[	KäÆXËnX˚.ä¯NXàniz^8.[ªÆäÍÓXXéyI˛hâKª~jŒz	Nzõn[®˛Xâ~˚»ŒXhﬁXâ.XànäÍﬁ{∏>i…˛Y(ŒkXæä˘^i…˛8""ê¢V«6S†¢fñ∆&∆U˜7∆óG2“6˜'FVBÜw&ñEˆÜó7F˜'ï≤'6Ê6Ü˜EˆFFR%“Ê7GóRá7G"íÁVÊóVRÇíÁFˆ∆ó7BÇíê¢FVfV«E˜7∆óB“fñ∆&∆U˜7∆óG5∂÷ÇÉ¬ñÁBÜ∆V‚Üfñ∆&∆U˜7∆óG2í¢„ríï–¢7∆óEˆFFR“7BÁ6V∆V7F&˜ÇÇ.j~i ŒZInã[~x+í"¬fñ∆&∆U˜7∆óG2¬ñÊFWÉ÷fñ∆&∆U˜7∆óG2ÊñÊFWÇÜFVfV«E˜7∆óBí¬∂Wì“&w&ñE˜7∆óEˆFFR"ê¢'VÂˆw&ñE˜f∆ñFFñˆ‚“7BÊ'WGFˆ‚Ç.ã˘äŒj~i ŒXh^ZInX¯.i[ö®Œä¯"¬∂Wì“''VÂˆw&ñE˜f∆ñFFñˆ‚"ê¢ñbÊ˜B'VÂˆw&ñE˜f∆ñFFñˆ„†¢7BÊñÊfÚÇ.X¯.i[ö®Œä¯äÍzÈ~òx˛ãË>ZJ~˚»Œx+ûX{æh»ûô*ÓYÓhòﬁK…Æã˘äŒ˚»ŒKàﬁK…ÆôãæZÓX[nZË>ö^ô⁄.8""ê¢V«6S†¢w&ñB“'VÂ˜v∆µˆf˜'v&Eˆw&ñBÜw&ñEˆÜó7F˜'í¬w&ñE˜&ñ6W2¬F˜ˆÂ˜f«VW3’≥2¬R¬Ö“¬Üˆ∆EˆFó5˜f«VW3’≥2¬R¬“¬7∆óEˆFFS◊7∆óEˆFFR¬6˜7Eˆ'3÷6˜7Eˆ'2ê¢ñbw&ñBÊV◊Gì†¢7BÊñÊfÚÇ.[Ÿ>XòﬁXà~Xànizk9^YŒi{n[⁄.hâäÍﬁ{∏>i…˛Y(ŒkXæä˘^i…˛K™Niâ>8""ê¢V«6S†¢w&ñEˆFó7∆í“w&ñBÊ6˜íÇê¢f˜"6ˆ«V÷‚ñ‚≤'G&ñÂˆfu˜&WGW&‚"¬'G&ñÂ˜vñÂ˜&FR"¬'FW7Eˆfu˜&WGW&‚"¬'FW7E˜vñÂ˜&FR"¬'FW7E˜F˜F≈˜&WGW&‚"¬'FW7EˆWÜ6W75˜&WGW&‚%”†¢w&ñEˆFó7∆ï∂6ˆ«V÷Â““w&ñEˆFó7∆ï∂6ˆ«V÷Â“Ê÷Üf˜&÷E˜7Bê¢7BÊFFg&÷RÄ¢w&ñEˆFó7∆íÁ&VÊ÷RÜ6ˆ«V÷Á3◊≤'F˜ˆ‚#¢.h»i»ûäŒKâÆi["¬&Üˆ∆EˆFó2#¢.h»i»ûZJûi["¬'G&ñÂ˜G&FW2#¢.äÍﬁ{∏>K™Niâ>i["¬'G&ñÂˆfu˜&WGW&‚#¢.äÍﬁ{∏>[õ>Yÿ~iKny∏¢"¬'G&ñÂ˜vñÂ˜&FR#¢.äÍﬁ{∏>à9ŒxËr"¬'FW7E˜G&FW2#¢.kXæä˘^K™Niâ>i["¬'FW7Eˆfu˜&WGW&‚#¢.kXæä˘^[õ>Yÿ~iKny∏¢"¬'FW7E˜vñÂ˜&FR#¢.kXæä˘^à9ŒxËr"¬'FW7E˜F˜F≈˜&WGW&‚#¢.kXæä˘^{J˛äÍiKny∏¢"¬'FW7EˆWÜ6W75˜&WGW&‚#¢.kXæä˘^yªéZ˚ûäŒKâÆzÿûiÿ2"¬'7∆óEˆFFR#¢.j~i ŒZInã[~x+í'“í¿¢vñGFÉ“'7G&WF6Ç"¿¢ÜñFUˆñÊFWÉ’G'VR¿¢ê†ßvóFÇF%˜V∆óGì†¢6V7FñˆÂˆÜVFW"Ç.i[h⁄ÓãJéòxÚ"¬'V∆óGí"ê¢ñbFF˜V∆óGíÊV◊Gì†¢7BÊñÊfÚÇ.[Ÿ>Xòﬁiz^i…˛k*i»ûi[h⁄ÓãJéòx˛j8i˙^ih~Kªn8.ä˚~òxﬁikã˘ä¬Fñ«ï˜'V‚Áû8""ê¢V«6S†¢7FGW5ˆ6˜VÁG2“FF˜V∆óGï≤'7FGW2%“Áf«VUˆ6˜VÁG2ÇíÁFıˆFñ7BÇíñb'7FGW2"ñ‚FF˜V∆óGíÊ6ˆ«V÷Á2V«6R∑–¢÷WG&ñ5ˆ6ˆ«2“7BÊ6ˆ«V÷Á2ÉBê¢÷WG&ñ5ˆ6ˆ«5≥“Ê÷WG&ñ2Ç.i[NKŸ>x´nh"¬V∆óGï˜7FGW2ê¢÷WG&ñ5ˆ6ˆ«5≥“Ê÷WG&ñ2Ç.j⁄>[ãÇ"¬7FGW5ˆ6˜VÁG2ÊvWBÇ.j⁄>[ãÇ"¬íê¢÷WG&ñ5ˆ6ˆ«5≥%“Ê÷WG&ñ2Ç.k:éhHÚ"¬7FGW5ˆ6˜VÁG2ÊvWBÇ.k:éhHÚ"¬íê¢÷WG&ñ5ˆ6ˆ«5≥5“Ê÷WG&ñ2Ç.[».[ãÇ"¬7FGW5ˆ6˜VÁG2ÊvWBÇ.[».[ãÇ"¬íê¢V∆óGïˆFó7∆í“FF˜V∆óGíÁ&VÊ÷RÄ¢6ˆ«V÷Á3◊∞¢&6ÜV6≤#¢.j8i˙^öí"¿¢'7FGW2#¢.x´nh"¿¢'f«VR#¢.[Ÿ>XòﬁX¬"¿¢'Fá&W6Üˆ∆B#¢.ôàéX¬"¿¢&÷W76vR#¢.ä˚Nià‚"¿¢–¢ê¢f˜"6ˆ«V÷‚ñ‚≤.j8i˙^öí"¬.x´nh"¬.[Ÿ>XòﬁX¬"¬.ôàéX¬"¬.ä˚Nià‚%”†¢ñb6ˆ«V÷‚ñ‚V∆óGïˆFó7∆íÊ6ˆ«V÷Á3†¢V∆óGïˆFó7∆ï∂6ˆ«V÷Â““V∆óGïˆFó7∆ï∂6ˆ«V÷Â“Ê7GóRá7G"ê¢7BÁF&∆RáV∆óGïˆFó7∆íê†¢7BÁ7V&ÜVFW"Ç.äŒKâÆiä[Nähnyπb"ê¢ñb÷ñÊuˆVFóBÊV◊Gì†¢7BÊñÊfÚÇ.[Ÿ>Xòﬁk*i»ûäŒKâÆiä[NZÍäÍ{π>iÈŒ8.ä˚~òxﬁikã˘äŒiz^KªæX™8""ê¢V«6S†¢6˜fW&vR“f∆ˆBÜ÷ñÊuˆVFóE≤&÷ñÊu˜7FGW2%“Ê7GóRá7G"íÊWÇ.[{.ähnyπb"íÊ÷V‚Çííñb&÷ñÊu˜7FGW2"ñ‚÷ñÊuˆVFóBÊ6ˆ«V÷Á2V«6R„ ¢7BÊ÷WG&ñ2Ç.à*zZéäŒKâÆiä[NähnyπnxËr"¬f˜&÷E˜7BÜ6˜fW&vRíê¢7BÊFFg&÷RÄ¢÷ñÊuˆVFóBÁ&VÊ÷RÜ6ˆ«V÷Á3◊≤&ñÊGW7G'ïˆÊ÷R#¢.äŒKâ¢"¬&÷VE˜7Fˆ6µˆ6˜VÁB#¢.iä[Nà*zZéi["¬&÷VEˆWFeˆ6˜VÁB#¢.iä[DUDni["¬&÷VE˜ßEˆ6˜VÁB#¢.kjéXŒj~i Œi["¬&÷ñÊu˜7FGW2#¢.x´nh'“í¿¢vñGFÉ“'7G&WF6Ç"¿¢ÜñFUˆñÊFWÉ’G'VR¿¢ê†¢7BÁ7V&ÜVFW"Ç.ã˘äŒiz^[˘r"ê¢ñb'VÂˆ∆ˆrÊV◊Gì†¢7BÊñÊfÚÇ.i®.izã˘äŒiz^[˘~8""ê¢V«6S†¢∆ˆuˆFó7∆í“'VÂˆ∆ˆrÁFñ¬É#íÁ6˜'E˜f«VW2Ç'7F'FVEˆB"¬66VÊFñÊs‘f«6RíÁ&VÊ÷RÄ¢6ˆ«V÷Á3◊∞¢'7F'FVEˆB#¢.[»Zxæi{nô{B"¿¢&fñÊó6ÜVEˆB#¢.{π>iŸ˛i{nô{B"¿¢&GW&FñˆÂ˜6V6ˆÊG2#¢.à	~i{nzy""¿¢'&WVW7FVEˆVÊEˆFFR#¢.ä˚~k.iz^i…Ú"¿¢&∆FW7E˜G&FUˆFFR#¢.i[h⁄Óiz^i…Ú"¿¢'7FGW2#¢.x´nh"¿¢'&Vg&W6Ç#¢.[ÀÆXãnXã~ik"¿¢&÷W76vUˆ6˜VÁB#¢.h˘zKÆi["¿¢–¢ê¢7BÁF&∆RÜ∆ˆuˆFó7∆íê†¢7BÁ7V&ÜVFW"Ç.i[h⁄Ók©X^[´r"ê¢ñb6˜W&6UˆÜV«FÇÊV◊Gì†¢7BÊñÊfÚÇ.[Ÿ>Xòﬁiz^i…˛k*i»ûi[h⁄Ók©X^[´~ih~Kªn8.ä˚~òxﬁikã˘ä¬Fñ«ï˜'V‚Áû8""ê¢V«6S†¢F˜F≈ˆWfVÁG2“∆V‚á6˜W&6UˆÜV«FÇê¢66ÜUˆWfVÁG2“ñÁBá6˜W&6UˆÜV«FÖ≤'6˜W&6R%“Ê7GóRá7G"íÊWÇ&66ÜR"íÁ7V“Çííñb'6˜W&6R"ñ‚6˜W&6UˆÜV«FÇÊ6ˆ«V÷Á2V«6R ¢f∆∆&6µˆWfVÁG2“ñÁBá6˜W&6UˆÜV«FÖ≤'6˜W&6R%“Ê7GóRá7G"íÊWÇ&f∆∆&6µˆ66ÜR"íÁ7V“Çííñb'6˜W&6R"ñ‚6˜W&6UˆÜV«FÇÊ6ˆ«V÷Á2V«6R ¢W'&˜%ˆWfVÁG2“ñÁBá6˜W&6UˆÜV«FÖ≤'7FGW2%“Ê7GóRá7G"íÊWÇ&W'&˜""íÁ7V“Çííñb'7FGW2"ñ‚6˜W&6UˆÜV«FÇÊ6ˆ«V÷Á2V«6R ¢ÜV«FÖˆ6ˆ«2“7BÊ6ˆ«V÷Á2ÉBê¢ÜV«FÖˆ6ˆ«5≥“Ê÷WG&ñ2Ç.i[h⁄Ók©K®æKªb"¬b'∑F˜F≈ˆWfVÁG7“"ê¢ÜV«FÖˆ6ˆ«5≥“Ê÷WG&ñ2Ç.{…>ZŸéYﬁKäﬁxËr"¬f˜&÷E˜7BÜ66ÜUˆWfVÁG2ÚF˜F≈ˆWfVÁG2ñbF˜F≈ˆWfVÁG2V«6Ríê¢ÜV«FÖˆ6ˆ«5≥%“Ê÷WG&ñ2Ç.ôòﬁ{™~{…>ZŸÇ"¬b'∂f∆∆&6µˆWfVÁG7“"ê¢ÜV«FÖˆ6ˆ«5≥5“Ê÷WG&ñ2Ç.ôIûä˙˛K®æKªb"¬b'∂W'&˜%ˆWfVÁG7“"ê†¢6˜W&6U˜7V÷÷'í“Ä¢6˜W&6UˆÜV«FÇÊw&˜W'íÖ≤&FF6WB"¬'6˜W&6R"¬'7FGW2%“¬5ˆñÊFWÉ‘f«6Rê¢ÊvrÜWfVÁG3“Ç&FF6WB"¬&6˜VÁB"í¬&˜w3“Ç'&˜w2"¬∆÷&Ff«VW3¢7G"á7V“áBÁFıˆÁV÷W&ñ2áf«VW2¬W'&˜'3“&6ˆW&6R"íÊfñ∆∆ÊÉíÊ7GóRÜñÁBííííê¢Á6˜'E˜f«VW2Ö≤&FF6WB"¬'6˜W&6R"¬'7FGW2%“ê¢ê¢6˜W&6U˜7V÷÷'í“6˜W&6U˜7V÷÷'íÁ&VÊ÷RÄ¢6ˆ«V÷Á3◊∞¢&FF6WB#¢.i[h⁄Óô∏b"¿¢'6˜W&6R#¢.i⁄^k©"¿¢'7FGW2#¢.x´nh"¿¢&WfVÁG2#¢.j i["¿¢'&˜w2#¢.äŒi["¿¢–¢ê¢7BÁF&∆Rá6˜W&6U˜7V÷÷'íê†¢6˜W&6UˆFWFñ¬“6˜W&6UˆÜV«FÇÁFñ¬ÉÉíÁ&VÊ÷RÄ¢6ˆ«V÷Á3◊∞¢&FF6WB#¢.i[h⁄Óô∏b"¿¢'&◊2#¢.X¯.i["¿¢'6˜W&6R#¢.i⁄^k©"¿¢'7FGW2#¢.x´nh"¿¢'&˜w2#¢.äŒi["¿¢&66ÜU˜FÇ#¢.{…>ZŸéih~Kªb"¿¢&÷W76vR#¢.ä˚Nià‚"¿¢–¢ê¢7BÊFFg&÷Rá6˜W&6UˆFWFñ¬¬vñGFÉ“'7G&WF6Ç"¬ÜñFUˆñÊFWÉ’G'VRê†¢7BÁ7V&ÜVFW"Ç.ã>[™niz^[˘r"ê¢ñb66ÜVGV∆W%ˆ∆ˆrÊV◊Gì†¢7BÊñÊfÚÇ.i®.izã>[™nKªæX™iz^[˘~8""ê¢V«6S†¢66ÜVGV∆W%ˆFó7∆í“66ÜVGV∆W%ˆ∆ˆrÁFñ¬É#íÁ6˜'E˜f«VW2Ç'7F'FVEˆB"¬66VÊFñÊs‘f«6RíÁ&VÊ÷RÄ¢6ˆ«V÷Á3◊∞¢'7F'FVEˆB#¢.[»Zxæi{nô{B"¿¢&fñÊó6ÜVEˆB#¢.{π>iŸ˛i{nô{B"¿¢&GW&FñˆÂ˜6V6ˆÊG2#¢.à	~i{nzy""¿¢&GFV◊B#¢.[	ﬁä˘^j i["¿¢&÷Ö˜&WG&ñW2#¢.i»ZJ~òxﬁä˘R"¿¢'&WGW&Âˆ6ˆFR#¢.ã˘NYπÓz"¿¢'7FF˜WE˜Fñ¬#¢.ãÈ>X{Æiéäh"¿¢'7FFW'%˜Fñ¬#¢.ôIûä˙˛iéäh"¿¢–¢ê¢7BÊFFg&÷Rá66ÜVGV∆W%ˆFó7∆í¬vñGFÉ“'7G&WF6Ç"¬ÜñFUˆñÊFWÉ’G'VRê†ßvóFÇF%ˆ6ˆÊfñs†¢6V7FñˆÂˆÜVFW"Ç.X¯.i[òXﬁ{⁄‚"¬&6ˆÊfñr"ê¢7BÊ6Fñˆ‚Ç.K˙ÓiKûYÓK…ÆXiûXZR6ˆÊfñr˜6WGFñÊw2Áñ÷Œ˚…æô»ähòxﬁikã˘äŒiz^KªæX™YÓ˚»Œikä¯NXànhòﬁK…ÆK€˛yJéiky®Niÿ>òxﬁ8""ê¢vVñváG2“6WGFñÊw2ÊvWBÇ'66˜&ñÊr"¬∑“íÊvWBÇ'vVñváG2"¬∑“ê¢vóFÇ7BÊf˜&“Ç'66˜&U˜vVñváEˆf˜&“"ì†¢6ˆ≈ˆ¬6ˆ≈ˆ"¬6ˆ≈ˆ2¬6ˆ≈ˆB“7BÊ6ˆ«V÷Á2ÉBê¢&ñ6U˜vVñváB“6ˆ≈ˆÊÁV÷&W%ˆñÁWBÇ.ãhæX´˛iÿ>òx“"¬÷ñÂ˜f«VS”„¬÷Ö˜f«VS”„¬f«VS÷f∆ˆBávVñváG2ÊvWBÇ'&ñ6U˜G&VÊE˜66˜&R"¬„Síí¬7FW”„Rê¢ÜVE˜vVñváB“6ˆ≈ˆ"ÊÁV÷&W%ˆñÁWBÇ.x:ﬁ[™niÿ>òx“"¬÷ñÂ˜f«VS”„¬÷Ö˜f«VS”„¬f«VS÷f∆ˆBávVñváG2ÊvWBÇ&ÜVE˜66˜&R"¬„#íí¬7FW”„Rê¢WFe˜vVñváB“6ˆ≈ˆ2ÊÁV÷&W%ˆñÁWBÇ$UDniÿ>òx“"¬÷ñÂ˜f«VS”„¬÷Ö˜f«VS”„¬f«VS÷f∆ˆBávVñváG2ÊvWBÇ&WFe˜66˜&R"¬„Ríí¬7FW”„Rê¢6VÁFñ÷VÁE˜vVñváB“6ˆ≈ˆBÊÁV÷&W%ˆñÁWBÇ.h8^{∫Æiÿ>òx“"¬÷ñÂ˜f«VS”„¬÷Ö˜f«VS”„¬f«VS÷f∆ˆBávVñváG2ÊvWBÇ'6VÁFñ÷VÁE˜66˜&R"¬„Ríí¬7FW”„Rê¢7V&÷óGFVB“7BÊf˜&’˜7V&÷óEˆ'WGFˆ‚Ç.K˘ﬁZŸéä¯NXàniÿ>òx“"ê¢ñb7V&÷óGFVC†¢WFFVB“Fñ7Bá6WGFñÊw2ê¢WFFVBÁ6WFFVfV«BÇ'66˜&ñÊr"¬∑“ï≤'vVñváG2%““∞¢'&ñ6U˜G&VÊE˜66˜&R#¢&ñ6U˜vVñváB¿¢&ÜVE˜66˜&R#¢ÜVE˜vVñváB¿¢&WFe˜66˜&R#¢WFe˜vVñváB¿¢'6VÁFñ÷VÁE˜66˜&R#¢6VÁFñ÷VÁE˜vVñváB¿¢–¢6fU˜6WGFñÊw2áWFFVBê¢7BÁ7V66W72Ç.[{.K˘ﬁZŸéä¯NXàniÿ>òxﬁ8.ä˚~òxﬁikã˘äŒiz^KªæX™K∫^yI˛hâikä¯NXàn8""ê†¢7BÁ7V&ÜVFW"Ç.[Ÿ>Xòﬁö8ÓjŒXàn{∏B"ê¢7BÊ6ˆFRáñ÷¬Á6fUˆGV◊á6WGFñÊw2ÊvWBÇ'7Gñ∆Uˆw&˜W2"¬∑“í¬∆∆˜u˜VÊñ6ˆFS’G'VR¬6˜'Eˆ∂Wó3‘f«6Rí¬∆ÊwVvS“'ñ÷¬"ê¢7BÁ7V&ÜVFW"Ç.[Ÿ>Xòﬁäx.Z˘˛i€˛YŸr"ê¢vóFÇ7BÊf˜&“Ç&6ˆ◊&ó6ˆÂˆñÊGW7G&ñW5ˆf˜&“"ì†¢ˆ'6W'fVB“7BÁFWáEˆñÁWBÇ.äx.Z˘˛i€˛YŸ~˚»éyJéò	~X˚~Xànô©N˚»í"¬f«VS“.˚»¬"Ê¶ˆñ‚á6WGFñÊw2ÊvWBÇ&÷&∂WB"¬∑“íÊvWBÇ&6ˆ◊&ó6ˆÂˆñÊGW7G&ñW2"¬µ“ííê¢ñb7BÊf˜&’˜7V&÷óEˆ'WGFˆ‚Ç.K˘ﬁZŸéäx.Z˘˛i€˛YŸr"ì†¢f«VW2“∑f«VRÁ7G&óÇíf˜"f«VRñ‚ˆ'6W'fVBÁ&W∆6RÇ"¬"¬.˚»¬"íÁ7∆óBÇ.˚»¬"íñbf«VRÁ7G&óÇï–¢WFFVB“Fñ7Bá6WGFñÊw2ê¢WFFVBÁ6WFFVfV«BÇ&÷&∂WB"¬∑“ï≤&6ˆ◊&ó6ˆÂˆñÊGW7G&ñW2%““f«VW0¢6fU˜6WGFñÊw2áWFFVBê¢7BÁ7V66W72Ç.[{.K˘ﬁZŸéäx.Z˘˛i€˛YŸ~8.òxﬁikã˘äŒiz^KªæX™YÓã[X´˛Z˚ûj˘NK…ÆiªNik8""ê†¢7BÁ7V&ÜVFW"Ç.äŒKâÆiä[NäxNXâí"ê¢7BÊ6Fñˆ‚Ç.iä[N[€Y8“UDn8kjéXŒ8KÀXŒ8X…~Y	Y(ŒõÈûâòÓjiŒk~hæ8.K˙ÓiKûXòﬁä˚~K˘ﬁyYíî‘¬{π>iËN˚…æK˘ﬁZŸéYÓK…ÆY éKàæKàj iz^ãyyI˛iXé8""ê¢WFeˆ÷ñÊu˜FÇ“&ˆ¶V7E˜FÇá6WGFñÊw2ÊvWBÇ&÷ñÊuˆfñ∆W2"¬∑“íÊvWBÇ&WFeˆñÊGW7G'í"¬&6ˆÊfñrˆWFeˆñÊGW7G'ïˆ÷ñÊrÁñ÷¬"íê¢˜fW'&ñFW5ˆ÷ñÊu˜FÇ“&ˆ¶V7E˜FÇá6WGFñÊw2ÊvWBÇ&÷ñÊuˆfñ∆W2"¬∑“íÊvWBÇ'7Fˆ6µˆñÊGW7G'ïˆ˜fW'&ñFW2"¬&6ˆÊfñr˜7Fˆ6µˆñÊGW7G'ïˆ˜fW'&ñFW2Áñ÷¬"íê¢WFeˆ÷ñÊu˜FWáB“WFeˆ÷ñÊu˜FÇÁ&VE˜FWáBÜVÊ6ˆFñÊs“'WFb”Ç"íñbWFeˆ÷ñÊu˜FÇÊWÜó7G2ÇíV«6R&ñÊGW7G'ïˆ∂Wóv˜&G3¢∑’∆ÊWÜ6«VFUˆ∂Wóv˜&G3¢µ’∆‚ ¢˜fW'&ñFW5ˆ÷ñÊu˜FWáB“˜fW'&ñFW5ˆ÷ñÊu˜FÇÁ&VE˜FWáBÜVÊ6ˆFñÊs“'WFb”Ç"íñb˜fW'&ñFW5ˆ÷ñÊu˜FÇÊWÜó7G2ÇíV«6R&˜fW'&ñFW3¢∑’∆‚ ¢vóFÇ7BÊf˜&“Ç&÷ñÊu˜'V∆W5ˆf˜&“"ì†¢ßEˆ÷ñÊu˜FWáB“7BÁFWáEˆ&VÇ.à*zZÇ˛h8^{∫ÆäŒKâÆiä[Bî‘¬"¬f«VS◊ñ÷¬Á6fUˆGV◊á6WGFñÊw2ÊvWBÇ'ßEˆñÊGW7G'ïˆ÷ñÊuˆ∂Wóv˜&G2"¬∑“í¬∆∆˜u˜VÊñ6ˆFS’G'VR¬6˜'Eˆ∂Wó3‘f«6Rí¬ÜVñváC”#cê¢WFeˆ÷ñÊuˆVFóB“7BÁFWáEˆ&VÇ$UDbäŒKâÆiä[Bî‘¬"¬f«VS÷WFeˆ÷ñÊu˜FWáB¬ÜVñváC”#cê¢˜fW'&ñFW5ˆ÷ñÊuˆVFóB“7BÁFWáEˆ&VÇ.à*zZéK∫>z[ÀÆXãniä[Bî‘¬"¬f«VS÷˜fW'&ñFW5ˆ÷ñÊu˜FWáB¬ÜVñváC”cê¢ñb7BÊf˜&’˜7V&÷óEˆ'WGFˆ‚Ç.K˘ﬁZŸéäŒKâÆiä[B"ì†¢G'ì†¢ßEˆ÷ñÊr“ñ÷¬Á6fUˆ∆ˆBáßEˆ÷ñÊu˜FWáBí˜"∑–¢WFeˆ÷ñÊr“ñ÷¬Á6fUˆ∆ˆBÜWFeˆ÷ñÊuˆVFóBí˜"∑–¢˜fW'&ñFW5ˆ÷ñÊr“ñ÷¬Á6fUˆ∆ˆBÜ˜fW'&ñFW5ˆ÷ñÊuˆVFóBí˜"∑–¢ñbÊ˜Bó6ñÁ7FÊ6RáßEˆ÷ñÊr¬Fñ7Bí˜"Ê˜Bó6ñÁ7FÊ6RÜWFeˆ÷ñÊr¬Fñ7Bí˜"Ê˜Bó6ñÁ7FÊ6RÜ˜fW'&ñFW5ˆ÷ñÊr¬Fñ7Bí˜"Ê˜Bó6ñÁ7FÊ6RÜ˜fW'&ñFW5ˆ÷ñÊrÊvWBÇ&˜fW'&ñFW2"¬∑“í¬Fñ7Bì†¢&ó6Rf«VTW'&˜"Ç.iä[NXh^ZÎû[¯^öæiäÚî‘¬Z˚ûã"ê¢WFFVB“Fñ7Bá6WGFñÊw2ê¢WFFVE≤'ßEˆñÊGW7G'ïˆ÷ñÊuˆ∂Wóv˜&G2%““ßEˆ÷ñÊp¢6fU˜6WGFñÊw2áWFFVBê¢WFeˆ÷ñÊu˜FÇÁw&óFU˜FWáBáñ÷¬Á6fUˆGV◊ÜWFeˆ÷ñÊr¬∆∆˜u˜VÊñ6ˆFS’G'VR¬6˜'Eˆ∂Wó3‘f«6Rí¬VÊ6ˆFñÊs“'WFb”Ç"ê¢˜fW'&ñFW5ˆ÷ñÊu˜FÇÁw&óFU˜FWáBáñ÷¬Á6fUˆGV◊Ü˜fW'&ñFW5ˆ÷ñÊr¬∆∆˜u˜VÊñ6ˆFS’G'VR¬6˜'Eˆ∂Wó3‘f«6Rí¬VÊ6ˆFñÊs“'WFb”Ç"ê¢7BÁ7V66W72Ç.äŒKâÆiä[N[{.K˘ﬁZŸé8.ä˚~òxﬁikã˘äŒiz^KªæX™[õnj8i˙^i[h⁄ÓãJéòx˛ö^y®Niä[NähnyπnxË~8""ê¢WÜ6WBáñ÷¬Âî‘ƒW'&˜"¬f«VTW'&˜"í2WÜ3†¢7BÊW'&˜"Üb.iä[Ni ÆK˘ﬁZŸé˚…ß∂WÜ7“"ê†ßvóFÇF%˜&W˜'C†¢6V7FñˆÂˆÜVFW"Ç$÷&∂F˜v‚iz^h™R"¬'&W˜'B"ê¢ñbáF÷≈˜&W˜'E˜FÇÊWÜó7G2Çì†¢7BÊ∆ñÊµˆ'WGFˆ‚Ç.hô>[»ÖD‘¬iz^h™R"¬áF÷≈˜&W˜'E˜FÇÁ&W6ˆ«fRÇíÊ5˜W&íÇíê¢ñb&W˜'E˜FÇÊWÜó7G2Çì†¢7BÊ÷&∂F˜v‚á&W˜'E˜FÇÁ&VE˜FWáBÜVÊ6ˆFñÊs“'WFb”Ç"íê¢V«6S†¢7BÁv&ÊñÊrÇ.i ÆhõÓXã[Ÿ>iz^h™^YÆih~Kªn8""ê†