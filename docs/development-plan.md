# A股板块轮动监控系统开发计划

更新时间：2026-07-10

## 1. 当前状态

系统已经推进到 Phase 4.5：在自动化日报基础上，补齐参数配置、风格监控、数据源健康增强和轮动信号回测框架。

当前最新运行结果：

- 请求日期：20260710
- 最新有效交易日：20260709
- 数据质量：注意
- 原因：数据源最新交易日早于请求日期，其他核心检查正常
- 数据源事件：errors=0，fallback_cache=0
- 历史库：`data/sector_rotation.duckdb`
- HTML 日报：`data/reports/sector_rotation_YYYYMMDD.html`
- 自动化入口：`scripts/run_daily_job.py`

## 2. 已完成阶段

## Phase 1.0 / MVP

- 接入 Tushare 中转站、AKShare、a-stock-data 调用规则。
- 建立 CSV 原始缓存和加工结果目录。
- 获取申万一级行业列表、行业日线、沪深300基准日线。
- 计算 5/20/60 日涨跌幅、20/60 日超额收益、均线结构分、成交热度分。
- 接入 ETF 行情、ETF 行业映射、ETF 映射质量检查。
- 接入涨停池，完成涨停行业映射和情绪分。
- 输出综合轮动分：

```text
默认：rotation_score = 趋势分 * 50% + 热度分 * 20% + ETF分 * 15% + 情绪分 * 15%
```

实际权重读取自 `config/settings.yaml` 的 `scoring.weights`，可在看板“参数配置”页修改。

## Phase 1.5：稳定性

- 增加数据质量检查。
- 增加运行日志。
- 增加数据源健康记录。
- 增加核心计算测试。
- 增加历史回看、排名变化、连续 Top10 天数。
- 修复 Streamlit CSV 缓存刷新问题，文件更新后页面能读取新结果。

## Phase 2.0：四维指标补齐

- 趋势增强：
  - RSI(14)
  - 相对 RSI(14)
  - 行业排名变化

- 资金增强：
  - 北向资金总流序列：`moneyflow_hsgt`
  - 沪深股通十大活跃股：`hsgt_top10`
  - 北向活跃成交行业聚合
  - 北向个股明细

- 估值模块：
  - 个股 `daily_basic`
  - 股票行业映射
  - 行业 PE(TTM)、PB、总市值、估值状态
  - 历史分位框架已建立；样本不足时标记为“样本不足”

- 情绪增强：
  - 龙虎榜：`top_list`
  - 龙虎榜行业净买入聚合
  - 龙虎榜个股明细
  - 涨停占比：涨停家数 / 行业股票数

## Phase 2.5：历史库与回测分析

- 引入 DuckDB。
- 保留 CSV 导出。
- `daily_run.py` 结束后自动同步加工结果到 DuckDB。
- 新增 `scripts/sync_history_db.py`，支持历史 CSV 回填。
- 看板日期列表和历史回看优先读取 DuckDB，历史库不存在时退回 CSV。
- 建立历史指标表：
  - `industry_daily`
  - `trend_score_daily`
  - `rotation_score_daily`
  - `comparison_series_daily`
  - `etf_summary_daily`
  - `zt_summary_daily`
  - `valuation_summary_daily`
  - `northbound_summary_daily`
  - `dragon_tiger_summary_daily`
  - `data_quality_log`
  - `source_health_log`
- 看板新增历史分析：
  - 行业综合分趋势
  - 行业排名变化曲线
  - 行业轮动热力图
  - 强势板块持续天数
  - 轮动扩散/收敛观察

## Phase 3.0：自动化与推送

- 新增带重试的日任务入口：`scripts/run_daily_job.py`。
- 新增 Windows 任务计划安装脚本：`scripts/install_windows_task.ps1`。
- 新增调度日志：`data/logs/scheduler_job_log.csv`。
- `daily_run.py` 每次运行后自动生成：
  - Markdown 日报
  - HTML 日报
  - PNG 图表快照
  - 交互式 HTML 图表
- 看板“日报”页增加 HTML 日报入口。
- 新增可选 Webhook 推送：
  - 环境变量：`SECTOR_ROTATION_WEBHOOK_URL`
  - 未配置时自动跳过，不影响日跑。
- 新增自动化说明文档：`docs/automation-and-push.md`。

## Phase 3.1：文档与运维收口

- 新增 `.env.example`，记录必要环境变量。
- 补充 `docs/data-source-rules.md`，覆盖 Phase 2.0 新增 Tushare 接口。
- 明确自动化入口、回填入口、Webhook 配置方式。

## Phase 4.0：产品化增强

- 评分权重进入 `config/settings.yaml`，并由 `daily_run.py` 实际读取。
- 看板新增“参数配置”页，可保存趋势/热度/ETF/情绪权重。
- 看板新增“风格监控”页，基于风格分组展示科技成长、高端制造、消费医药、周期资源、金融地产、稳定防御等风格强弱。
- 数据质量页增强：
  - 缓存命中率
  - 降级缓存次数
  - 错误事件数
  - 调度任务日志
- DuckDB 同步范围扩展到 ETF、涨停、北向、龙虎榜明细表。

## Phase 4.5：策略复盘/信号验证

- 新增 `src/engines/backtest_engine.py`。
- 看板新增“回测分析”页。
- 支持按综合排名 TopN、持有 N 个交易日进行轮动信号回测。
- 输出交易次数、胜率、平均收益、累计收益、最大回撤和净值曲线。
- 当前只有一个评分快照时会提示样本不足；后续每日积累后自动形成可用回测序列。

## 3. 当前看板结构

Streamlit 看板当前包含：

- 轮动排名
- 行业详情
- 板块走势
- ETF资金
- 估值温度
- 北向资金
- 情绪异动
- 历史回看
- 数据质量
- 日报

历史回看页现在包含：

- 最新排名变化
- 多行业综合分历史走势
- 最新 Top15 行业热力图
- 强势持续表
- 扩散/收敛指标
- 历史明细表

## 4. 当前输出与存储

CSV 加工结果位于 `data/processed/`。

DuckDB 历史库位于：

```text
data/sector_rotation.duckdb
```

日报位于：

```text
data/reports/sector_rotation_YYYYMMDD.md
data/reports/sector_rotation_YYYYMMDD.html
data/reports/assets/YYYYMMDD/
```

手动回填历史库：

```powershell
.\.venv\Scripts\python.exe scripts\sync_history_db.py
```

手动运行自动化任务：

```powershell
.\.venv\Scripts\python.exe scripts\run_daily_job.py
```

安装 Windows 每日任务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows_task.ps1
```

## 5. 当前限制

- 当前已有两个有效评分快照（20260708、20260709）；历史趋势、热力图和扩散指标已可用，但统计意义会随着每日运行增强。
- 实时多维快照目前只有两个交易日；价格研究序列已生成 62 个评分日，可用于初步样本内外验证，但仍不足以推导长期稳定的参数结论。
- 行业 PE/PB 分位需要积累至少 20 个历史样本后才有统计意义。
- 北向 `hsgt_top10` 当前接口样本中的 `net_amount/buy/sell` 字段部分为空，因此行业净额暂时可能为 0；活跃成交额可正常使用。
- 行业映射仍依赖关键词。当前审计为 28/31 个行业有股票映射；环保、综合、美容护理需要优先补齐。
- 融资融券和大宗交易已接入当日数据，但尚未建立足够长的历史序列。

## 6. 下一阶段计划

## Phase 5.0 - 5.4：数据可信度与研究增强（已完成）

目标：形成长期可维护的个人研究工具。

任务：

- Phase 5.0：新增 a-stock-data 适配器，直接接入 Tencent 最新行情和 Eastmoney 行业主力资金；行业主力资金按 AKShare -> Eastmoney/a-stock-data -> 本地缓存降级，来源写入数据源健康日志。
- Phase 5.1：看板可编辑观察板块、股票/情绪行业映射和 ETF 行业映射；新增 `scripts/rebuild_price_history.py`，只用历史价格与成交额重建研究序列，避免用实时 ETF/资金数据伪造历史信号。
- Phase 5.2：新增趋势状态（趋势确认、趋势启动、观察等待、趋势走弱）、数据置信度以及技术过热、情绪拥挤、炸板偏多、北向背离风险提示。
- Phase 5.3：回测改为评分日后的下一交易日进入，加入可配置换仓成本、成本前收益和行业等权基准超额；没有后续交易日的评分不会被交易。
- Phase 5.4：新增行业主力资金、融资融券、大宗交易汇总，以及大盘/中小盘/高股息/科创成长风格指数监控。

## Phase 6.0：研究可信度（已完成）

- 新增价格研究序列与 `scripts/rebuild_price_history.py`；最新产物覆盖 82 个交易日、62 个可用评分日，严格只使用当时可得价格和成交额。
- 新增行业映射审计表，并在数据质量页展示股票、ETF、涨停映射覆盖与待维护行业。
- 新增样本内外参数网格验证：比较 TopN 与持有期组合的训练期和测试期交易数、收益、胜率、累计收益及相对行业等权超额。

## Phase 7.0：历史覆盖与映射收口（已完成）

- 价格研究历史已扩展至 2023-07-31 至 2026-07-09，共 712 个有效评分日、22,072 条行业评分记录；样本内外参数网格已针对三年数据优化。
- 新增 `config/stock_industry_overrides.yaml`，股票代码强制映射优先于关键词；环保、综合、美容护理已补齐，当前 31 个申万一级行业全部覆盖。
- 新增 `scripts/backfill_market_structure.py`，可按区间、追加模式回填融资融券市场汇总和大宗交易行业汇总；已验证并写入最近 7 个交易日的历史种子。
- 主力资金和完整北向行业流目前不具备可靠的历史回填通路，只从系统运行日开始累计，不得用当前实时接口伪造历史值。

## Phase 8.0：执行与组合层（已完成）

- 行业日线与沪深300基准日线升级为开高低收字段，并通过缓存 schema 版本自动绕过旧字段缓存。
- 新增“组合风控”页：控制最多行业数、单行业上限、现金缓冲、集中度和风格暴露；该页输出研究配置而非账户级交易指令。
- 新增“候选个股”页：从强势行业内的涨停、龙虎榜、北向活跃等事件生成待研究池，并展示估值和 ST 风险提示。
- 回测加入沪深300外部基准、换手比例、实际权益暴露、单行业上限和跳空过滤；优先按次日开盘进入，缺少开盘价时明确标注回退口径。
- 完整历史快照回填仍暂缓；主力资金和北向行业流在没有可靠历史通路前不参与历史因子验证。

## Phase 9.0：后续研究深化

- ETF 资金页已升级为历史走势：按行业成交额最高的代表 ETF 汇总近 180 日累计涨跌、5 日成交额和 5/20 日量能比；Tushare `fund_daily` 为主源，AKShare 为故障兜底。
- 用滚动样本外窗口验证策略稳定性，并记录参数与数据版本。
- 分批扩展融资融券和大宗交易历史区间，增加断点续跑和完整性校验。
- 引入覆盖完整的行业资金流/北向行业数据源后，再纳入综合评分与回测。

## 优先操作优化（已完成）

- 左侧日期明确为“完整快照日期”，并显示评分平均完整度；价格研究序列继续在历史回看页独立选择，避免两类口径混淆。
- 综合评分按行业逐项识别趋势、热度、ETF、情绪因子是否可用。缺失因子不再按零分处理，而是自动剔除对应权重并重算，输出有效权重、可用因子与 `score_completeness`。
- 行业详情新增决策卡，集中展示趋势状态、资金状态、风险提示、估值状态和评分完整度，并给出观察/风险解释。
- 回测优先采用评分后的下一交易日开盘进入、持有期末收盘退出，并显示实际成交口径和完整换仓成本。当前中转站 `sw_daily` 未返回开盘字段，历史与现有快照自动标记为 `next_close_fallback`；后续数据源提供开盘价后会自动切换到 `next_open`。
