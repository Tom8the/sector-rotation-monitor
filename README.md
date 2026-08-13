# A 股行业轮动监控

一个面向 A 股研究的行业轮动监控与分析工具。项目从申万一级行业、沪深 300 基准、ETF、涨停池、估值、北向资金、融资融券、龙虎榜等数据中提取信号，生成行业综合评分、风险提示、研究候选池、历史回看和日报，并通过 Streamlit 提供交互式看板。

> 本项目用于研究和信息整理，不构成任何投资建议，也不会连接交易账户或自动下单。市场数据的完整性、时效性和第三方接口稳定性可能影响结果，请结合原始数据和个人判断使用。

## 功能

- 行业轮动排名：综合趋势、热度、ETF 和涨停情绪计算行业评分。
- 行业详情分析：查看收益、超额收益、均线、RSI、评分贡献和数据完整度。
- 多维度市场观察：支持 ETF、估值、北向资金、涨停情绪、主力资金、融资融券、大宗交易和龙虎榜等信息。
- 风格与组合研究：观察成长、制造、消费、周期、金融等风格表现，生成带行业数量、单行业上限、现金缓冲和风格暴露约束的研究组合方案。
- 候选个股池：从强势行业中的涨停、龙虎榜和北向活跃等事件中生成待研究清单，并提示估值和 ST 风险。
- 历史回看：支持排名变化、热力图、强势持续性、市场扩散/收敛和行业历史评分查询。
- 策略回测：按综合排名进行 Top-N 轮动回测，输出交易次数、胜率、收益、回撤、换手和相对基准表现。
- 数据质量检查：记录数据源健康状态、字段缺失、映射覆盖率和评分完整度。
- 日报生成：输出 Markdown、HTML 和图表资源，可选通过 Webhook 推送。
- 本地缓存与历史库：原始数据保存为 CSV，加工结果写入 CSV 和 DuckDB，减少重复请求并支持历史查询。

## 项目截图

### 1. 行业轮动排名

<p align="center">
  <img src="https://raw.githubusercontent.com/Tom8the/sector-rotation-monitor/main/docs/images/dashboard-overview.png" alt="行业轮动排名" width="100%">
</p>

### 2. 板块走势对比

<p align="center">
  <img src="https://raw.githubusercontent.com/Tom8the/sector-rotation-monitor/main/docs/images/sector-trend-comparison.png" alt="板块走势对比" width="100%">
</p>

### 3. 北向资金分析

<p align="center">
  <img src="https://raw.githubusercontent.com/Tom8the/sector-rotation-monitor/main/docs/images/northbound-capital.png" alt="北向资金分析" width="100%">
</p>

### 4. 情绪异动监控

<p align="center">
  <img src="https://raw.githubusercontent.com/Tom8the/sector-rotation-monitor/main/docs/images/sentiment-anomaly.png" alt="情绪异动监控" width="100%">
</p>

## 技术栈

- Python 3.11+（已在 Python 3.14 环境验证）
- pandas、requests、PyYAML
- Tushare 中转站、AKShare、Tencent/a-stock-data 等数据源
- DuckDB：历史数据存储与查询
- Streamlit + Plotly：交互式看板和图表
- pytest：自动化测试
- Kaleido：报告图表导出

## 环境要求

- Windows、macOS 或 Linux
- Python 3.11 或更高版本
- 能够访问项目配置的数据接口
- Tushare 中转站 API Key（用于主要行情、行业、估值和资金数据）

项目当前提供了 Windows PowerShell 命令；在 macOS/Linux 下将 `.venv\Scripts\python.exe` 替换为 `.venv/bin/python` 即可。

## 安装

### 1. 获取项目

```bash
git clone https://github.com/<your-account>/<your-repository>.git
cd sector-rotation-monitor
```

### 2. 创建虚拟环境

Windows PowerShell：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. 配置环境变量

复制 `.env.example` 为 `.env`，并填入数据接口 Key：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`：

```dotenv
TUSHARE_API_KEY=你的_datahubco_api_key
TUSHARE_URL=http://datahubco.com/app-api/openapi/v1/tushare
SECTOR_ROTATION_WEBHOOK_URL=
```

`.env` 只保存在本地，不要提交到 GitHub。项目默认从 `TUSHARE_API_KEY` 读取凭据，不需要把 Key 写入 Python 或 YAML 文件。

## 快速开始

### 运行一次数据任务

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe scripts\daily_run.py
```

指定数据截止日期（格式为 `YYYYMMDD`）：

```powershell
.\.venv\Scripts\python.exe scripts\daily_run.py --date 20260812
```

忽略本地原始数据缓存并重新请求远端数据：

```powershell
.\.venv\Scripts\python.exe scripts\daily_run.py --date 20260812 --refresh
```

### 启动交互式看板

建议先成功运行一次数据任务，再启动看板：

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

启动后访问 Streamlit 输出的本地地址，通常为 `http://localhost:8501`。

### 推荐的每日运行入口

`run_daily_job.py` 会根据配置进行失败重试，并检查近期缺失的快照后补数：

```powershell
.\.venv\Scripts\python.exe scripts\run_daily_job.py
```

常用参数：

```powershell
# 指定日期
.\.venv\Scripts\python.exe scripts\run_daily_job.py --date 20260812

# 强制刷新远端数据
.\.venv\Scripts\python.exe scripts\run_daily_job.py --refresh

# 覆盖最大重试次数和重试间隔（秒）
.\.venv\Scripts\python.exe scripts\run_daily_job.py --max-retries 3 --retry-delay 180
```

## Windows 定时任务

安装默认的每日任务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows_task.ps1
```

指定任务名称和执行时间：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows_task.ps1 `
  -TaskName SectorRotationDaily `
  -RunTime 18:30
```

默认配置位于 `config/settings.yaml`：

```yaml
automation:
  run_time: "18:30"
  max_retries: 2
  retry_delay_seconds: 300
  recovery_lookback_days: 7
```

## 输出文件

运行成功后，主要输出如下：

```text
data/
├── raw/                         # 数据源原始响应缓存（默认不提交）
├── processed/                   # 每日加工 CSV（默认不提交）
├── reports/
│   ├── sector_rotation_YYYYMMDD.md
│   ├── sector_rotation_YYYYMMDD.html
│   └── assets/YYYYMMDD/         # 报告图表
├── research/                    # 价格、ETF 和市场结构研究历史
├── logs/                        # 运行日志和数据源健康日志
└── sector_rotation.duckdb       # 历史快照数据库
```

常见加工结果包括：

- `rotation_scores_YYYYMMDD.csv`：行业综合评分与排名。
- `trend_scores_YYYYMMDD.csv`：趋势、收益、超额收益和 RSI 等指标。
- `comparison_series_YYYYMMDD.csv`：行业与沪深 300 的走势对比序列。
- `etf_summary_YYYYMMDD.csv`：行业 ETF 观察结果。
- `valuation_summary_YYYYMMDD.csv`：行业 PE/PB 和历史分位信息。
- `northbound_summary_YYYYMMDD.csv`：北向活跃成交行业汇总。
- `zt_summary_YYYYMMDD.csv`：涨停情绪与连板信息。
- `data_quality_YYYYMMDD.csv`、`source_health_YYYYMMDD.csv`：数据质量和数据源状态。

将已生成的 CSV 加载到 DuckDB：

```powershell
.\.venv\Scripts\python.exe scripts\sync_history_db.py
```

只同步某个快照：

```powershell
.\.venv\Scripts\python.exe scripts\sync_history_db.py --date 20260812
```

## 配置说明

主要配置文件：

| 文件 | 用途 |
| --- | --- |
| `config/settings.yaml` | 数据源、市场基准、评分权重、路径、自动化和风格分组 |
| `config/etf_industry_mapping.yaml` | ETF 到申万行业的映射规则 |
| `config/stock_industry_overrides.yaml` | 个股行业映射的人工覆盖规则 |
| `.env` | 本地 API Key 和可选 Webhook 地址 |

默认综合评分权重为：趋势 `50%`、热度 `20%`、ETF `15%`、涨停情绪 `15%`。看板中的“参数配置”页面可以调整配置；修改后需要重新运行数据任务才会生成新的结果。

如果需要接收日报推送，可在 `.env` 中设置：

```dotenv
SECTOR_ROTATION_WEBHOOK_URL=https://your-webhook-url
```

未配置 Webhook 时不会发送网络通知，日报仍会正常生成。

## 研究历史回填

价格研究历史回填示例：

```powershell
.\.venv\Scripts\python.exe scripts\rebuild_price_history.py `
  --start 20230101 `
  --end 20260812
```

融资融券和大宗交易研究历史回填示例：

```powershell
.\.venv\Scripts\python.exe scripts\backfill_market_structure.py `
  --start 20230101 `
  --end 20260812 `
  --append
```

历史回填会访问较多远端数据，建议遵守数据源的请求频率限制，并根据网络和接口配额调整脚本参数。

## 测试

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

测试覆盖趋势、评分、资金流、ETF 历史、历史库、回测、数据质量、映射和组合等核心模块。数据源联网 smoke test 可使用：

```powershell
.\.venv\Scripts\python.exe scripts\test_data_sources.py
```

## 项目结构

```text
sector-rotation-monitor/
├── config/                      # YAML 配置和映射
├── dashboard/app.py             # Streamlit 看板
├── docs/                        # 开发、数据源和存储说明
├── scripts/                     # 日常任务、回填、同步和定时任务脚本
├── src/
│   ├── core/                    # 数据服务、缓存、报告、通知和历史库
│   ├── engines/                 # 趋势、评分、情绪、估值、回测等分析引擎
│   ├── fetchers/                # Tushare、AKShare 和 A 股数据适配器
│   └── utils/                   # 配置和日期工具
├── tests/                       # pytest 测试
├── data/                        # 本地缓存、结果、研究数据和日志
├── requirements.txt
└── README.md
```

## 数据源与限制

- Tushare 中转站是主要数据源，AKShare 和其他适配器用于补位或增强。
- 数据接口可能出现限流、字段变化、连接失败或历史数据缺失；系统会尽量使用缓存和降级源，并在数据质量页面记录缺失情况。
- 北向活跃股接口的净买入字段可能为空，此时相关行业净额可能为 0，但活跃成交额仍可能可用。
- 行业映射依赖关键字和人工覆盖规则，新增股票、ETF 或行业后应检查映射审计结果。
- 历史回测只用于验证研究假设，不代表未来收益；请关注样本量、换仓成本、滑点、数据缺失和未来数据泄露等问题。

## 开发建议

1. 修改配置或分析逻辑后，先运行对应 pytest 测试。
2. 使用小日期区间验证数据源和字段，再进行长周期回填。
3. 不要提交 `.env`、API Key、原始缓存和运行日志。
4. 提交前确认 README 中的仓库地址、许可证和数据源授权信息符合你的发布方式。

## 许可证

当前仓库未声明许可证。公开发布前，请根据代码、数据源和第三方依赖的授权情况补充合适的 `LICENSE` 文件。
