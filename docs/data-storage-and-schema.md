# 数据存储与字段字典

更新时间：2026-07-09

## 当前存储方式

系统现在采用“双层本地存储”：

| 层级 | 位置 | 用途 |
| --- | --- | --- |
| 原始缓存 | `data/raw/` | 缓存 Tushare / AKShare 原始接口结果，减少重复请求 |
| 加工文件 | `data/processed/` | 每日 CSV 产物，便于检查、导出和兜底 |
| 历史库 | `data/sector_rotation.duckdb` | 历史查询、回看、热力图、回测分析 |
| 日报 | `data/reports/` | Markdown 日报 |
| 配置 | `config/` | 数据源、路径、行业映射规则 |

原则：CSV 继续保留作为可检查的落盘文件；DuckDB 作为历史查询层。看板日期和历史回看优先读取 DuckDB，如果历史库不存在则自动退回 CSV。

## 原始缓存规则

原始缓存由 `CsvCache` 管理：

```text
data/raw/{接口名}_{参数hash}.csv
```

默认运行优先读取缓存；使用 `scripts/daily_run.py --refresh` 时忽略缓存并重新请求远端。

## 加工结果命名规则

加工结果按最新有效交易日命名：

```text
data/processed/{数据集}_{YYYYMMDD}.csv
data/reports/sector_rotation_{YYYYMMDD}.md
```

核心 CSV 产物：

- `industry_daily_YYYYMMDD.csv`
- `trend_scores_YYYYMMDD.csv`
- `rotation_scores_YYYYMMDD.csv`
- `comparison_series_YYYYMMDD.csv`
- `etf_summary_YYYYMMDD.csv`
- `zt_summary_YYYYMMDD.csv`
- `valuation_summary_YYYYMMDD.csv`
- `northbound_summary_YYYYMMDD.csv`
- `dragon_tiger_summary_YYYYMMDD.csv`
- `data_quality_YYYYMMDD.csv`
- `source_health_YYYYMMDD.csv`

## DuckDB 历史表

DuckDB 路径由 `config/settings.yaml` 配置：

```yaml
paths:
  duckdb_path: "data/sector_rotation.duckdb"
```

每次 `scripts/daily_run.py` 完成后，会将当前交易日的加工结果同步进 DuckDB。同步以 `snapshot_date` 为幂等键：同一天重复运行会覆盖同一天记录，不会追加重复行。

当前历史表：

| 表名 | 来源 CSV | 内容 |
| --- | --- | --- |
| `industry_daily` | `industry_daily_*.csv` | 申万行业日线历史 |
| `trend_score_daily` | `trend_scores_*.csv` | 趋势与热度基础评分 |
| `rotation_score_daily` | `rotation_scores_*.csv` | 综合轮动评分 |
| `comparison_series_daily` | `comparison_series_*.csv` | 板块走势对比序列 |
| `etf_summary_daily` | `etf_summary_*.csv` | ETF 行业汇总 |
| `etf_detail_daily` | `etf_detail_*.csv` | ETF 明细 |
| `zt_summary_daily` | `zt_summary_*.csv` | 涨停情绪汇总 |
| `zt_detail_daily` | `zt_detail_*.csv` | 涨停明细 |
| `valuation_summary_daily` | `valuation_summary_*.csv` | 行业估值汇总 |
| `northbound_summary_daily` | `northbound_summary_*.csv` | 北向活跃成交行业汇总 |
| `northbound_detail_daily` | `northbound_detail_*.csv` | 北向活跃个股明细 |
| `dragon_tiger_summary_daily` | `dragon_tiger_summary_*.csv` | 龙虎榜行业汇总 |
| `dragon_tiger_detail_daily` | `dragon_tiger_detail_*.csv` | 龙虎榜个股明细 |
| `data_quality_log` | `data_quality_*.csv` | 数据质量检查 |
| `source_health_log` | `source_health_*.csv` | 数据源读取事件 |

手动回填历史库：

```powershell
.\.venv\Scripts\python.exe scripts\sync_history_db.py
```

只回填某一天：

```powershell
.\.venv\Scripts\python.exe scripts\sync_history_db.py --date 20260708
```

## 核心数据集

### `rotation_scores_YYYYMMDD.csv` / `rotation_score_daily`

最终轮动综合评分，看板排名主表。

| 字段 | 含义 |
| --- | --- |
| `snapshot_date` | 入库快照日期，DuckDB 自动补充 |
| `trade_date` | 最新有效交易日 |
| `industry_name` | 申万一级行业名称 |
| `rotation_score` | 最终综合分 |
| `price_trend_score` | 趋势分 |
| `heat_score` | 热度分 |
| `etf_score` | ETF 资金分 |
| `sentiment_score` | 涨停情绪分 |
| `rsi_14` / `relative_rsi_14` | RSI 与相对 RSI |
| `ret_5d` / `ret_20d` / `ret_60d` | 5/20/60 日涨跌幅 |
| `excess_20d` / `excess_60d` | 相对沪深300超额收益 |

当前默认综合分权重位于 `config/settings.yaml`：

```yaml
scoring:
  weights:
    price_trend_score: 0.50
    heat_score: 0.20
    etf_score: 0.15
    sentiment_score: 0.15
```

看板“参数配置”页可修改权重；重新运行日任务后生效。

### `industry_daily_YYYYMMDD.csv` / `industry_daily`

申万一级行业日线，用于长期历史分析。

| 字段 | 含义 |
| --- | --- |
| `ts_code` | 行业指数代码 |
| `trade_date` | 交易日 |
| `close` | 收盘点位 |
| `amount` | 成交额 |
| `industry_name` | 申万一级行业 |
| `snapshot_date` | 入库快照日期 |

### `comparison_series_YYYYMMDD.csv` / `comparison_series_daily`

板块走势对比图使用的数据。

| 字段 | 含义 |
| --- | --- |
| `trade_date` | 交易日 |
| `close` | 指数点位 |
| `name` | 行业或基准名称 |
| `cum_return` | 从序列起点计算的累计涨跌幅 |

### `etf_summary_YYYYMMDD.csv` / `etf_summary_daily`

ETF 行业汇总表。

| 字段 | 含义 |
| --- | --- |
| `mapped_industry` | 映射行业 |
| `etf_count` | ETF 数量 |
| `avg_pct_change` | ETF 平均涨跌幅 |
| `total_amount` | ETF 总成交额 |
| `total_main_net_inflow` | ETF 主力净流入合计 |
| `total_latest_shares` | ETF 最新份额合计 |

### `zt_summary_YYYYMMDD.csv` / `zt_summary_daily`

涨停情绪行业汇总。

| 字段 | 含义 |
| --- | --- |
| `mapped_industry` | 映射行业 |
| `limit_up_count` | 涨停家数 |
| `stock_count` | 行业股票数量 |
| `limit_up_ratio` | 涨停家数 / 行业股票数量 |
| `max_limit_up_days` | 最高连板 |
| `total_seal_amount` | 封板资金合计 |
| `open_board_count` | 炸板次数 |

### `valuation_summary_YYYYMMDD.csv` / `valuation_summary_daily`

行业估值汇总。

| 字段 | 含义 |
| --- | --- |
| `mapped_industry` | 映射行业 |
| `stock_count` | 股票数量 |
| `total_mv` | 总市值 |
| `pe_ttm` | 行业聚合 PE(TTM) |
| `pb` | 行业聚合 PB |
| `pe_percentile` / `pb_percentile` | 历史分位，样本不足时为空 |
| `valuation_state` | `样本不足` / `偏低` / `适中` / `偏贵` |

### `northbound_summary_YYYYMMDD.csv` / `northbound_summary_daily`

北向活跃成交行业汇总。

| 字段 | 含义 |
| --- | --- |
| `mapped_industry` | 映射行业 |
| `hsgt_stock_count` | 活跃个股数量 |
| `hsgt_active_amount` | 沪深股通十大活跃股成交额 |
| `hsgt_net_amount` | 估算净额；接口字段为空时可能为 0 |

### `dragon_tiger_summary_YYYYMMDD.csv` / `dragon_tiger_summary_daily`

龙虎榜行业汇总。

| 字段 | 含义 |
| --- | --- |
| `mapped_industry` | 映射行业 |
| `top_list_count` | 上榜个股数量 |
| `top_list_amount` | 上榜成交额 |
| `top_list_net_amount` | 净买入 |
| `top_list_buy` | 买入额 |
| `top_list_sell` | 卖出额 |

## 历史分析口径

看板“历史回看”页基于 `rotation_score_daily`：

- 行业综合分趋势
- 行业排名变化
- 连续 Top10 天数
- 最新 Top15 行业热力图
- 分数上升/下降行业数量
- 轮动扩散比例

当前只有一个交易日样本时，趋势、分位和扩散指标会正常显示单点结果；随着每日运行积累，历史图和估值分位会逐步具备统计意义。
