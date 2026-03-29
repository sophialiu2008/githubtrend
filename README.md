# GitHub 行业趋势看板生成器

一个面向 GitHub 趋势分析的静态智能看板。它除了生成排行榜，还会输出多周历史、热度评分、新秀榜、异常增长检测、连续上榜标记、自动摘要、变化报告、问答入口、Markdown 周报和可选订阅分发。

## 关键文件

- 架构图: [docs/ARCHITECTURE.md](C:\Users\liuli\Desktop\github\docs\ARCHITECTURE.md)
- 主入口: [scripts/generate_dashboard.py](C:\Users\liuli\Desktop\github\scripts\generate_dashboard.py)
- 通知入口: [scripts/send_notification.py](C:\Users\liuli\Desktop\github\scripts\send_notification.py)
- 主题配置: [config/topics.yaml](C:\Users\liuli\Desktop\github\config\topics.yaml)
- 前端模板: [templates/index.html.j2](C:\Users\liuli\Desktop\github\templates\index.html.j2)
- 工作流: [.github/workflows/update_site.yml](C:\Users\liuli\Desktop\github\.github\workflows\update_site.yml)

## 当前能力

- 多周历史库与按周归档快照
- 全球总榜 / 周增长榜 / 热度榜 / 新秀榜 / 行业榜
- 热度评分
  - 总 Star
  - 周增长
  - 增长率
  - 最近更新时间
  - Issue 活跃度代理
- 异常增长检测与连续上榜标记
- 自动生成执行摘要、行业观察结论、本周变化报告
- 导出 `dashboard.json` 与 `weekly-report.md`
- 支持 Feishu / 企业微信 / Telegram / SMTP 邮件订阅
- 页面支持双层导航、排序、语言筛选、Topic 筛选、实时搜索、移动卡片、Sparkline、详情弹层和问答入口

## 项目结构

```text
.
|-- .github/workflows/update_site.yml
|-- config/topics.yaml
|-- data/
|   |-- cache/
|   `-- history/
|-- docs/ARCHITECTURE.md
|-- github_trends/
|   |-- config.py
|   |-- github_client.py
|   |-- history_store.py
|   |-- notifier.py
|   |-- ranking_service.py
|   `-- site_renderer.py
|-- scripts/
|   |-- generate_dashboard.py
|   `-- send_notification.py
|-- templates/index.html.j2
`-- tests/
```

## 快速开始

1. 配置令牌。

```powershell
$env:GITHUB_TOKEN = "ghp_your_token_here"
```

2. 生成页面与数据文件。

```powershell
& 'C:\Users\liuli\AppData\Local\Programs\Python\Python310\python.exe' `
  scripts\generate_dashboard.py `
  --config config/topics.yaml `
  --template templates/index.html.j2 `
  --cache-dir data/cache `
  --history-input data/history/latest.json `
  --history-output dist/data/history/latest.json `
  --history-archive-dir dist/data/history/snapshots `
  --output-html dist/index.html `
  --output-json dist/dashboard.json `
  --output-report dist/weekly-report.md `
  --strict
```

3. 查看输出文件。

- 页面: [dist/index.html](C:\Users\liuli\Desktop\github\dist\index.html)
- 数据: [dist/dashboard.json](C:\Users\liuli\Desktop\github\dist\dashboard.json)
- 周报: [dist/weekly-report.md](C:\Users\liuli\Desktop\github\dist\weekly-report.md)
- 最新快照: [dist/data/history/latest.json](C:\Users\liuli\Desktop\github\dist\data\history\latest.json)

## 订阅推送

如果环境变量存在，生成脚本会把周报推送到对应渠道。

- `FEISHU_WEBHOOK_URL`
- `WECOM_WEBHOOK_URL`
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
- `REPORT_EMAIL_SMTP_HOST` / `REPORT_EMAIL_USERNAME` / `REPORT_EMAIL_PASSWORD` / `REPORT_EMAIL_TO`

## 手动问答

可以在生成时直接附带一个问题：

```powershell
& 'C:\Users\liuli\AppData\Local\Programs\Python\Python310\python.exe' `
  scripts\generate_dashboard.py `
  --question "本周 AI 赛道最值得关注的 5 个项目是什么？"
```

## 工作流说明

- GitHub Actions 每周一 00:00（Asia/Shanghai）自动运行
- 自动从 `gh-pages` 恢复历史快照
- 生成预览 artifact
- 严格校验全球榜不少于 100 条
- 自动部署到 `gh-pages`
- 失败时可选发送通知

GitHub Actions 的 `cron` 使用 UTC，因此工作流里采用 `0 16 * * 0`，对应北京时间每周一 00:00。

## 测试

```powershell
& 'C:\Users\liuli\AppData\Local\Programs\Python\Python310\python.exe' -m unittest discover -s tests -v
```
