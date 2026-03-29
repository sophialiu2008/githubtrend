# 项目架构图

```mermaid
flowchart LR
    A["GitHub Actions / 本地 CLI"] --> B["scripts/generate_dashboard.py"]
    B --> C["config/topics.yaml"]
    B --> D["github_trends/github_client.py"]
    B --> E["github_trends/history_store.py"]
    B --> F["github_trends/ranking_service.py"]
    B --> G["github_trends/site_renderer.py"]
    B --> H["github_trends/notifier.py"]
    D --> I["GitHub Search API / Repo API"]
    E --> J["多周快照 latest + snapshots/*.json"]
    F --> K["热度评分 / 新秀榜 / 异常检测 / 连续上榜 / 自动摘要 / Q&A"]
    G --> L["dist/index.html"]
    G --> M["dist/dashboard.json"]
    G --> N["dist/weekly-report.md"]
    E --> O["dist/data/history/latest.json"]
    E --> P["dist/data/history/snapshots/*.json"]
    H --> Q["Feishu / WeCom / Telegram / Email"]
    L --> R["gh-pages 部署"]
    M --> R
    N --> R
    O --> R
    P --> R
```

## 模块职责

- `github_trends/config.py`
  - 加载行业配置、常量与基础路径参数。
- `github_trends/github_client.py`
  - GitHub API 访问、缓存、限流与 README 抓取。
- `github_trends/history_store.py`
  - 最新快照、历史归档、榜单变化对比。
- `github_trends/ranking_service.py`
  - 热度评分、新秀榜、异常检测、连续上榜、自动摘要、问答逻辑。
- `github_trends/site_renderer.py`
  - 输出 HTML、`dashboard.json` 和 Markdown 周报。
- `github_trends/notifier.py`
  - 报告订阅推送与失败通知。
