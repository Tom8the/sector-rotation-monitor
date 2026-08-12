# 自动化与推送

更新时间：2026-07-09

## 日常运行入口

推荐使用带重试的任务入口：

```powershell
.\.venv\Scripts\python.exe scripts\run_daily_job.py
```

指定日期：

```powershell
.\.venv\Scripts\python.exe scripts\run_daily_job.py --date 20260709
```

强制刷新数据源缓存：

```powershell
.\.venv\Scripts\python.exe scripts\run_daily_job.py --refresh
```

重试参数来自 `config/settings.yaml`：

```yaml
automation:
  run_time: "18:30"
  max_retries: 2
  retry_delay_seconds: 300
  webhook_url_env: "SECTOR_ROTATION_WEBHOOK_URL"
```

## Windows 任务计划

安装每日任务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows_task.ps1
```

指定任务名和时间：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows_task.ps1 -TaskName SectorRotationDaily -RunTime 18:30
```

任务会调用：

```text
scripts\run_daily_job.py
```

运行日志：

```text
data/logs/scheduler_job_log.csv
data/logs/daily_run_log.csv
```

## 报告输出

每次日跑会生成：

```text
data/reports/sector_rotation_YYYYMMDD.md
data/reports/sector_rotation_YYYYMMDD.html
data/reports/assets/YYYYMMDD/*.png
data/reports/assets/YYYYMMDD/*.html
```

HTML 日报包含：

- 综合轮动 TOP10
- 核心图表快照
- ETF资金观察
- 估值温度
- 北向活跃成交
- 龙虎榜净买入
- 情绪异动

## Webhook 推送

默认不发送推送。配置环境变量后自动发送：

```powershell
$env:SECTOR_ROTATION_WEBHOOK_URL = "https://your-webhook-url"
.\.venv\Scripts\python.exe scripts\run_daily_job.py
```

长期保存环境变量：

```powershell
setx SECTOR_ROTATION_WEBHOOK_URL "https://your-webhook-url"
```

当前推送 payload 会依次尝试常见文本格式，适配企业微信、飞书、钉钉等普通机器人 Webhook。没有配置 Webhook 时，运行结果会显示：

```text
Notification: {'sent': False, 'reason': 'webhook_not_configured'}
```
