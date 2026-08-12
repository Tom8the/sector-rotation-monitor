# 数据源获取规则

本文记录板块轮动监控系统的数据源分工、调用规则、降级顺序和 smoke test 方法。不要把真实 API Key 写入仓库；运行时统一从环境变量读取。

## 1. 数据源分工

| 数据域 | 主源 | 补位 | 增强/兜底 |
| --- | --- | --- | --- |
| 交易日历 | Tushare 中转站 `trade_cal` | AKShare 交易日历 | 本地缓存 |
| 基准指数日线 | Tushare 中转站 `index_daily` | AKShare 指数日线 | a-stock-data 的 Tencent/mootdx 指数行情 |
| 申万行业指数日线 | Tushare 中转站申万相关接口 | AKShare 东财行业板块行情 | 本地缓存 |
| 个股日线/估值 | Tushare 中转站 `daily` / `daily_basic` | AKShare 个股行情/指标 | Tencent 实时行情 |
| ETF 行情/份额 | Tushare 基金/ETF接口 | AKShare `fund_etf_spot_em` / `fund_etf_hist_em` | Tencent ETF 实时行情 |
| 涨停/情绪 | Tushare `stk_limit` / `top_list` | AKShare `stock_zt_pool_em` | a-stock-data 东财涨停池 |
| 盘中实时行情 | 不作为主源 | AKShare 实时接口 | a-stock-data mootdx / Tencent |

## 2. Tushare 中转站规则

中转站不是标准 `api.tushare.pro`，当前可用代理地址：

```text
http://datahubco.com/app-api/openapi/v1/tushare
```

项目 fetcher 的请求路径是：

```text
GET http://datahubco.com/app-api/openapi/v1/tushare/{api-name}
```

请求示例：

```python
import os
import requests

os.environ["NO_PROXY"] = "*"
response = requests.get(
    "http://datahubco.com/app-api/openapi/v1/tushare/index-daily",
    headers={"X-API-Key": os.environ["TUSHARE_API_KEY"]},
    params={
        "ts_code": "000300.SH",
        "start_date": "20260701",
        "end_date": "20260709",
        "fields": "ts_code,trade_date,close,pct_chg,vol,amount",
    },
    timeout=20,
)
```
注意：

- 不要同时设置旧的官方 `TUSHARE_TOKEN` 环境变量和错误代理地址。
- 模块级 `ts.pro_bar()` 需要显式传入 `api=pro`。
- 每次请求间隔建议 `>= 0.5s`，批量任务建议 `1s`。
- 当前实测：新中转站的 `stock-basic` 返回 `code=0`，项目 fetcher 可自动按 `limit/offset` 分页。

当前系统实际调用的 Tushare 数据集：

| 数据集 | 接口 | 用途 | 当前口径 |
| --- | --- | --- | --- |
| 申万行业列表 | `index_classify` / 申万分类封装 | 31 个申万一级行业 | `SW2021` / `L1` |
| 申万行业日线 | 申万行业日线封装 | 趋势、热度、走势对比 | 默认回看 120 个自然日 |
| 沪深300日线 | `index_daily` | 基准指数与超额收益 | `000300.SH` |
| A股基础信息 | `stock_basic` | 股票到行业映射、行业股票数量 | 上市状态 `L` |
| 个股估值 | `daily_basic` | 行业 PE/PB 聚合 | 最新有效交易日 |
| 沪深港通资金流 | `moneyflow_hsgt` | 北向资金总流序列 | 默认回看 120 个自然日 |
| 沪深股通十大活跃股 | `hsgt_top10` | 北向活跃成交行业聚合 | `market_type=1/3` |
| 龙虎榜 | `top_list` | 龙虎榜行业净买入 | 最新有效交易日 |

注意：

- `hsgt_top10` 当前样本中 `net_amount/buy/sell` 可能为空，因此北向行业净额可能为 0；活跃成交额可正常使用。
- `daily_basic` 是个股层估值，行业 PE/PB 由系统按映射行业聚合。
- `stock_basic` 的行业字段不是申万一级行业，系统通过 `zt_industry_mapping_keywords` 做关键字映射。

## 3. AKShare 规则

AKShare 作为补位源，优先用于：

- ETF 实时列表：`ak.fund_etf_spot_em()`
- ETF 历史日线：优先 Tushare 中转站 `fund_daily`，按 ETF 代码补齐交易所后缀；AKShare `fund_etf_hist_em` 仅在主源异常时兜底。

历史走势以每个已映射行业成交额最高的 1 只 ETF 为代表，首次回填近 180 个自然日，后续从已保存的最后交易日向前 7 天增量刷新。原始明细保存于 `data/research/etf_history_detail.csv`，行业汇总走势保存于 `data/research/etf_industry_series.csv`。
- 涨停池：`ak.stock_zt_pool_em(date="YYYYMMDD")`
- 行业资金流向：`ak.stock_sector_fund_flow_rank(...)`
- 东财行业板块行情：`ak.stock_board_industry_name_em()` / `ak.stock_board_industry_hist_em(...)`

调用规则：

```python
import akshare as ak

etf_df = ak.fund_etf_spot_em()
zt_df = ak.stock_zt_pool_em(date="20260709")
```

注意：

- AKShare 很多接口底层仍然依赖东财，字段和连接稳定性会变化。
- 所有 AKShare 调用必须包裹 `try/except`。
- 失败时不要阻断日报，标记该指标缺失并读取本地缓存。
- 当前实测：`fund_etf_spot_em`、`stock_zt_pool_em` 可成功返回；部分行业板块/指数接口出现远端断开，需要作为不稳定补位源处理。

## 4. a-stock-data 规则

a-stock-data 不是普通 pip 包，本质是一个带内嵌代码的 Skill/参考实现。系统已将稳定通路封装在 `src/fetchers/astock_fetcher.py`，而不是直接依赖为包。

优先级：

1. Tencent 行情：实时指数、个股、ETF，稳定且不易封 IP。
2. mootdx：K 线、五档盘口、实时行情，需先探测可用通达信服务器。
3. Eastmoney：涨停池、龙虎榜、资金流、行业排名等独有数据，必须限流。

Tencent 行情：

```python
import requests

resp = requests.get(
    "https://qt.gtimg.cn/q=sh000001,sz399300,sh000300",
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=12,
)
```

mootdx 行情：

```python
import socket
from mootdx.quotes import Quotes

servers = [
    ("119.97.185.59", 7709),
    ("124.70.133.119", 7709),
    ("116.205.183.150", 7709),
]

client = None
for ip, port in servers:
    try:
        with socket.create_connection((ip, port), timeout=2):
            client = Quotes.factory(market="std", server=(ip, port))
            break
    except Exception:
        continue

df = client.bars(symbol="000001", frequency=9, start=0, offset=5)
```

Eastmoney 涨停池：

```python
import random
import time
import requests

time.sleep(1 + random.random() * 0.3)
resp = requests.get(
    "https://push2ex.eastmoney.com/getTopicZTPool",
    params={
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wz.ztzt",
        "Pageindex": 0,
        "pagesize": 10,
        "sort": "fbt:asc",
        "date": "20260709",
    },
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=12,
)
```

注意：

- Eastmoney 请求必须串行限流，最小间隔 `>= 1s`，批量建议 `1.5-2s`。
- 连接被断开时不要立即高频重试，先退避。
- 当前运行时用途：Tencent 用于最新行情探测；Eastmoney 用于行业主力资金流的 AKShare 降级源。主力资金的实际降级顺序是 `AKShare -> a-stock-data Eastmoney -> 本地缓存`，每一次尝试均记录在 `source_health_YYYYMMDD.csv`。

## 5. 降级顺序

每个数据获取函数统一返回：

```python
{
    "source": "tushare|akshare|astock|cache",
    "data": dataframe,
    "status": "ok|missing|stale",
    "message": "...",
}
```

降级顺序：

1. 调用主源 Tushare 中转站。
2. 主源失败后调用 AKShare 对应接口。
3. AKShare 失败后调用 a-stock-data 对应通路。
4. 三者均失败时读取本地最近有效缓存。
5. 缓存也没有时返回空数据，并在日报中标注数据缺失。

## 6. Smoke Test

运行前设置环境变量：

```powershell
$env:TUSHARE_API_KEY="你的中转站 API Key"
.\.venv\Scripts\python.exe scripts\test_data_sources.py
```

不要把 API Key 写进脚本、配置样例或测试结果。

当前已验证依赖：

```text
pandas
requests
tushare
akshare
mootdx
stockstats
curl_cffi
```
