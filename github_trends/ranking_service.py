from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .config import (
    APP_TIMEZONE,
    GROWTH_LOOKBACK_WEEKS,
    NEWCOMER_WINDOW_DAYS,
    SPARKLINE_WEEKS,
    IndustryConfig,
)


def current_time_strings(snapshot_label: str | None = None) -> tuple[str, str, datetime]:
    zone = ZoneInfo(APP_TIMEZONE)
    now = datetime.now(zone)
    snapshot_date = snapshot_label or now.strftime("%Y-%m-%d")
    return now.strftime("%Y-%m-%d %H:%M:%S %Z"), snapshot_date, now


def collect_current_repositories(
    client: Any,
    industries: list[IndustryConfig],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    discovered: dict[str, dict[str, Any]] = {}
    sections_raw: dict[str, list[str]] = {}

    global_items = client.search_repositories(
        "stars:>1 is:public fork:false archived:false",
        limit=100,
    )
    sections_raw["global"] = []
    for item in global_items:
        repo = _seed_repo(discovered, item)
        sections_raw["global"].append(repo["full_name"])

    for industry in industries:
        industry_key = f"industry.{industry.key}"
        sector_pool: dict[str, None] = {}
        for topic in industry.topics:
            items = client.search_repositories(
                f"topic:{topic} is:public fork:false archived:false",
                limit=50,
            )
            for item in items:
                repo = _seed_repo(discovered, item)
                repo["matched_topics"].add(topic)
                repo["industry_keys"].add(industry.key)
                sector_pool[repo["full_name"]] = None
        sections_raw[industry_key] = list(sector_pool.keys())

    return discovered, sections_raw


def enrich_repositories(client: Any, repos: dict[str, dict[str, Any]]) -> None:
    for repo in repos.values():
        details = client.get_repository(repo["full_name"])
        repo["created_at"] = details.get("created_at") or repo["created_at"]
        repo["updated_at"] = details.get("updated_at") or repo["updated_at"]
        repo["pushed_at"] = details.get("pushed_at") or repo["pushed_at"]
        repo["language"] = details.get("language") or repo["language"] or "Unknown"
        repo["homepage"] = details.get("homepage") or ""
        repo["license_name"] = (details.get("license") or {}).get("spdx_id") or "N/A"
        repo["forks_total"] = int(details.get("forks_count") or 0)
        repo["watchers_total"] = int(details.get("subscribers_count") or 0)
        repo["open_issues_count"] = int(details.get("open_issues_count") or repo["open_issues_count"] or 0)
        repo["topics"] = sorted(set(details.get("topics") or []) | repo["matched_topics"])
        repo["readme_excerpt"] = client.get_readme_excerpt(repo["full_name"])
        repo["last_release_tag"] = (details.get("default_branch") or "main")


def build_dashboard(
    repos: dict[str, dict[str, Any]],
    sections_raw: dict[str, list[str]],
    industries: list[IndustryConfig],
    latest_snapshot: dict[str, Any],
    historical_snapshots: list[dict[str, Any]],
    snapshot_label: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    generated_at, snapshot_date, now = current_time_strings(snapshot_label)
    previous_repos = latest_snapshot.get("repos", {})
    history_by_repo = {
        full_name: _collect_history_points(full_name, historical_snapshots, snapshot_date, repo["stars_total"])
        for full_name, repo in repos.items()
    }

    _compute_repo_metrics(repos, previous_repos, history_by_repo, now)
    _compute_heat_scores(repos)

    sections = _build_sections(repos, sections_raw, industries)
    _attach_streaks(repos, sections, historical_snapshots)
    _attach_related_repos(repos, sections)
    _attach_change_reports(sections, latest_snapshot)
    executive_summary, industry_observations = _build_summaries(sections, industries)
    _attach_insights(sections, executive_summary, industry_observations)
    questions = _build_qa_examples()
    summary_cards = _build_summary_cards(repos, sections)

    page_data = {
        "title": "GitHub 行业趋势看板 AI",
        "generated_at": generated_at,
        "snapshot_date": snapshot_date,
        "has_history": bool(previous_repos),
        "tracked_repo_count": len(repos),
        "global_repo_count": len(sections["global"]["repos"]),
        "weekly_repo_count": len(sections["weekly"]["repos"]),
        "summary_cards": summary_cards,
        "primary_tabs": [
            {
                "key": "global",
                "label": "全球",
                "secondary": ["global"],
            },
            {
                "key": "weekly",
                "label": "周增长",
                "secondary": ["weekly"],
            },
            {
                "key": "heat",
                "label": "热度",
                "secondary": ["heat"],
            },
            {
                "key": "newcomers",
                "label": "新秀",
                "secondary": ["newcomers"],
            },
            {
                "key": "industries",
                "label": "行业",
                "secondary": [f"industry.{item.key}" for item in industries],
            },
        ],
        "sections": sections,
        "executive_summary": executive_summary,
        "weekly_changes": {
            key: section["change_report"]
            for key, section in sections.items()
            if section["change_report"]["new_entries"]
            or section["change_report"]["dropped_entries"]
            or section["change_report"]["rank_movers"]
        },
        "qa_examples": questions,
        "data_notes": [
            "热度评分 = Star 规模 + 周增长 + 增长率 + 最近推送时间 + Issue 活跃度代理。",
            "周增长基于当前快照与上一次归档快照的 Star 差值。",
            "4 周 / 12 周增长使用近 4 / 12 个周快照估算，不足时退化到当前已有历史。",
            "PR 活跃度在当前版本使用最近更新时间作为代理，避免对 API 造成过高压力。",
        ],
        "validation": {
            "global_top_count_ok": len(sections["global"]["repos"]) >= 100,
            "errors": [] if len(sections["global"]["repos"]) >= 100 else ["全球总榜结果少于 100 条。"],
        },
    }

    snapshot = build_snapshot(page_data, repos, sections, generated_at, snapshot_date)
    markdown_report = build_markdown_report(page_data)
    return page_data, snapshot, markdown_report


def answer_question(page_data: dict[str, Any], question: str) -> str:
    text = question.lower()
    desired = 5
    for token in text.split():
        if token.isdigit():
            desired = max(1, min(int(token), 10))
            break

    target_section = "weekly"
    if "新秀" in question:
        target_section = "newcomers"
    elif "热度" in question:
        target_section = "heat"
    elif "全球" in question:
        target_section = "global"
    else:
        for key, section in page_data["sections"].items():
            if section["group"] == "industries" and (section["label"] in question or section["title"] in question):
                target_section = key
                break

    section = page_data["sections"][target_section]
    repos = sorted(
        section["repos"],
        key=lambda item: (
            item.get("heat_score", 0),
            item.get("weekly_stars", 0),
            item.get("stars_total", 0),
        ),
        reverse=True,
    )[:desired]
    lines = [f"{section['title']}里当前最值得关注的 {len(repos)} 个项目："]
    for repo in repos:
        lines.append(
            f"- {repo['full_name']}：周增 {repo.get('weekly_stars', 0)}，热度 {repo.get('heat_score', 0)}，"
            f"主要语言 {repo.get('language', 'Unknown')}，原因是 {repo.get('qa_reason', '具备关注价值')}"
        )
    return "\n".join(lines)


def build_snapshot(
    page_data: dict[str, Any],
    repos: dict[str, dict[str, Any]],
    sections: dict[str, dict[str, Any]],
    generated_at: str,
    snapshot_date: str,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "snapshot_date": snapshot_date,
        "summary_cards": page_data["summary_cards"],
        "repos": {
            name: {
                "full_name": repo["full_name"],
                "stars_total": repo["stars_total"],
                "weekly_stars": repo["weekly_stars"],
                "growth_4w": repo["growth_4w"],
                "growth_12w": repo["growth_12w"],
                "heat_score": repo["heat_score"],
                "language": repo["language"],
                "created_at": repo["created_at"],
                "updated_at": repo["updated_at"],
                "pushed_at": repo["pushed_at"],
                "topics": repo["topics"],
                "industry_keys": sorted(repo["industry_keys"]),
                "open_issues_count": repo["open_issues_count"],
                "description": repo["description"],
                "html_url": repo["html_url"],
            }
            for name, repo in sorted(repos.items())
        },
        "sections": {
            key: [repo["full_name"] for repo in section["repos"]]
            for key, section in sections.items()
        },
    }


def build_markdown_report(page_data: dict[str, Any]) -> str:
    lines = [
        f"# {page_data['title']} 周报",
        "",
        f"- 生成时间: {page_data['generated_at']}",
        f"- 观测仓库数: {page_data['tracked_repo_count']}",
        "",
        "## 本周摘要",
    ]
    lines.extend(f"- {item}" for item in page_data["executive_summary"])
    lines.extend(["", "## 趋势卡片"])
    lines.extend(
        f"- {card['label']}: {card['value']} ({card['description']})"
        for card in page_data["summary_cards"]
    )
    lines.extend(["", "## 行业观察"])
    for key, section in page_data["sections"].items():
        if section["group"] != "industries":
            continue
        lines.append(f"### {section['title']}")
        lines.extend(f"- {insight}" for insight in section["insights"])
    lines.extend(["", "## 本周变化报告"])
    for key, report in page_data["weekly_changes"].items():
        lines.append(f"### {page_data['sections'][key]['title']}")
        if report["new_entries"]:
            lines.append("- 新上榜: " + "、".join(item["full_name"] for item in report["new_entries"]))
        if report["dropped_entries"]:
            lines.append("- 掉榜: " + "、".join(item["full_name"] for item in report["dropped_entries"]))
        if report["rank_movers"]:
            lines.append(
                "- 排名变化: "
                + "、".join(
                    f"{item['full_name']} ({item['previous_rank']}→{item['current_rank']})"
                    for item in report["rank_movers"]
                )
            )
    return "\n".join(lines) + "\n"


def _seed_repo(repo_map: dict[str, dict[str, Any]], item: dict[str, Any]) -> dict[str, Any]:
    full_name = item["full_name"]
    if full_name not in repo_map:
        repo_map[full_name] = {
            "id": item["id"],
            "name": item["name"],
            "full_name": full_name,
            "html_url": item["html_url"],
            "description": (item.get("description") or "No description provided.").strip(),
            "stars_total": int(item.get("stargazers_count") or 0),
            "language": item.get("language") or "Unknown",
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
            "pushed_at": item.get("pushed_at"),
            "open_issues_count": int(item.get("open_issues_count") or 0),
            "owner_login": item.get("owner", {}).get("login", ""),
            "owner_avatar_url": item.get("owner", {}).get("avatar_url", ""),
            "matched_topics": set(),
            "industry_keys": set(),
            "topics": [],
            "readme_excerpt": "",
            "homepage": "",
            "license_name": "N/A",
            "forks_total": 0,
            "watchers_total": 0,
            "last_release_tag": "",
        }
    repo_map[full_name]["stars_total"] = max(repo_map[full_name]["stars_total"], int(item.get("stargazers_count") or 0))
    return repo_map[full_name]


def _collect_history_points(
    full_name: str,
    snapshots: list[dict[str, Any]],
    snapshot_date: str,
    current_stars: int,
) -> list[dict[str, Any]]:
    points = []
    for snapshot in snapshots[-SPARKLINE_WEEKS:]:
        repo = snapshot.get("repos", {}).get(full_name)
        if not repo:
            continue
        points.append({"date": snapshot.get("snapshot_date"), "stars_total": int(repo.get("stars_total", 0))})
    if not points or points[-1]["date"] != snapshot_date:
        points.append({"date": snapshot_date, "stars_total": current_stars})
    return points[-SPARKLINE_WEEKS:]


def _compute_repo_metrics(
    repos: dict[str, dict[str, Any]],
    previous_repos: dict[str, Any],
    history_by_repo: dict[str, list[dict[str, Any]]],
    now: datetime,
) -> None:
    for repo in repos.values():
        previous = previous_repos.get(repo["full_name"], {})
        previous_stars = int(previous.get("stars_total", 0) or 0)
        repo["weekly_stars"] = max(repo["stars_total"] - previous_stars, 0)
        repo["growth_rate"] = round(repo["weekly_stars"] / max(previous_stars, 1), 4) if previous_stars else 1.0

        history = history_by_repo[repo["full_name"]]
        repo["sparkline"] = [point["stars_total"] for point in history]
        repo["growth_4w"] = _historical_growth(history, GROWTH_LOOKBACK_WEEKS)
        repo["growth_12w"] = _historical_growth(history, SPARKLINE_WEEKS)
        repo["newcomer"] = _days_since(repo.get("created_at"), now) <= NEWCOMER_WINDOW_DAYS
        repo["push_days"] = _days_since(repo.get("pushed_at"), now)
        repo["update_days"] = _days_since(repo.get("updated_at"), now)
        repo["anomaly"] = _detect_anomaly(history, repo["weekly_stars"], repo["growth_rate"])
        repo["history_points"] = history
        repo["section_streaks"] = {}
        repo["related_repos"] = []
        repo["all_topics"] = sorted(set(repo["topics"]) | set(repo["matched_topics"]))
        repo["activity_proxy"] = round(
            min(repo["open_issues_count"], 120) / 120 * 0.5
            + _recency_score(repo["update_days"], scale=14) * 0.5,
            4,
        )


def _compute_heat_scores(repos: dict[str, dict[str, Any]]) -> None:
    star_values = [math.log10(repo["stars_total"] + 1) for repo in repos.values()]
    weekly_values = [repo["weekly_stars"] for repo in repos.values()]
    growth_values = [min(repo["growth_rate"], 1.0) for repo in repos.values()]
    max_star = max(star_values) or 1
    max_weekly = max(weekly_values) or 1
    max_growth = max(growth_values) or 1

    for repo in repos.values():
        star_component = math.log10(repo["stars_total"] + 1) / max_star
        weekly_component = repo["weekly_stars"] / max_weekly
        growth_component = min(repo["growth_rate"], 1.0) / max_growth
        recency_component = _recency_score(repo["push_days"], scale=21)
        activity_component = repo["activity_proxy"]
        repo["heat_score"] = round(
            35 * star_component
            + 30 * weekly_component
            + 15 * growth_component
            + 10 * recency_component
            + 10 * activity_component,
            1,
        )
        repo["qa_reason"] = _build_reason(repo)


def _build_sections(
    repos: dict[str, dict[str, Any]],
    sections_raw: dict[str, list[str]],
    industries: list[IndustryConfig],
) -> dict[str, dict[str, Any]]:
    industry_lookup = {item.key: item for item in industries}
    sections: dict[str, dict[str, Any]] = {}

    sections["global"] = _make_section(
        key="global",
        title="全球总榜 Top 100",
        label="全球总榜",
        group="overview",
        description="按 GitHub Star 总量排序的公开仓库。",
        repos=_sorted_payloads(repos, sections_raw["global"], "stars_total", 100),
    )
    sections["weekly"] = _make_section(
        key="weekly",
        title="周增长榜 Top 20",
        label="周增长榜",
        group="overview",
        description="基于当前快照与上周快照做差后的 Star 增长榜。",
        repos=_sorted_payloads(
            repos,
            [name for name, repo in repos.items() if repo["weekly_stars"] > 0],
            "weekly_stars",
            20,
        ),
    )
    sections["heat"] = _make_section(
        key="heat",
        title="热度评分榜 Top 25",
        label="热度评分榜",
        group="overview",
        description="综合总 Star、周增长、增长率、更新活跃度计算的热度榜。",
        repos=_sorted_payloads(repos, list(repos.keys()), "heat_score", 25),
    )
    sections["newcomers"] = _make_section(
        key="newcomers",
        title="新秀榜 Top 20",
        label="新秀榜",
        group="overview",
        description="近 90 天创建且增长较快的高潜力项目。",
        repos=_sorted_payloads(
            repos,
            [name for name, repo in repos.items() if repo["newcomer"] and repo["weekly_stars"] > 0],
            "heat_score",
            20,
        ),
    )

    for industry_key, names in sections_raw.items():
        if not industry_key.startswith("industry."):
            continue
        slug = industry_key.split(".", 1)[1]
        industry = industry_lookup[slug]
        sections[industry_key] = _make_section(
            key=industry_key,
            title=f"{industry.label}行业榜 Top 50",
            label=industry.label,
            group="industries",
            description=industry.description,
            topics=industry.topics,
            repos=_sorted_payloads(repos, names, "stars_total", 50),
        )

    return sections


def _attach_streaks(
    repos: dict[str, dict[str, Any]],
    sections: dict[str, dict[str, Any]],
    historical_snapshots: list[dict[str, Any]],
) -> None:
    prior_sections = [snapshot.get("sections", {}) for snapshot in historical_snapshots]
    for section_key, section in sections.items():
        for repo in section["repos"]:
            streak = 1
            for previous in reversed(prior_sections):
                names = previous.get(section_key, [])
                if repo["full_name"] in names:
                    streak += 1
                else:
                    break
            repo["section_streak"] = streak
            repos[repo["full_name"]]["section_streaks"][section_key] = streak


def _attach_related_repos(
    repos: dict[str, dict[str, Any]],
    sections: dict[str, dict[str, Any]],
) -> None:
    repo_list = list(repos.values())
    for repo in repo_list:
        candidates = []
        for other in repo_list:
            if other["full_name"] == repo["full_name"]:
                continue
            shared_topics = len(set(repo["all_topics"]) & set(other["all_topics"]))
            shared_industries = len(repo["industry_keys"] & other["industry_keys"])
            same_language = 1 if repo["language"] == other["language"] else 0
            score = shared_topics * 3 + shared_industries * 2 + same_language + other["heat_score"] / 100
            if score > 0:
                candidates.append((score, other))
        top_related = [
            {
                "full_name": item["full_name"],
                "html_url": item["html_url"],
                "heat_score": item["heat_score"],
            }
            for _, item in sorted(candidates, key=lambda pair: pair[0], reverse=True)[:3]
        ]
        repo["related_repos"] = top_related
    for section in sections.values():
        for repo in section["repos"]:
            repo["related_repos"] = repos[repo["full_name"]]["related_repos"]


def _attach_change_reports(sections: dict[str, dict[str, Any]], latest_snapshot: dict[str, Any]) -> None:
    previous_sections = latest_snapshot.get("sections", {})
    for key, section in sections.items():
        current_names = [repo["full_name"] for repo in section["repos"]]
        previous_names = previous_sections.get(key, [])
        change_report = {
            "new_entries": [
                {"full_name": name, "rank": index + 1}
                for index, name in enumerate(current_names)
                if name not in previous_names
            ][:5],
            "dropped_entries": [
                {"full_name": name, "previous_rank": index + 1}
                for index, name in enumerate(previous_names)
                if name not in current_names
            ][:5],
            "rank_movers": _rank_movers(current_names, previous_names),
        }
        section["change_report"] = change_report


def _build_summaries(
    sections: dict[str, dict[str, Any]],
    industries: list[IndustryConfig],
) -> tuple[list[str], dict[str, list[str]]]:
    hottest_industry = max(
        (sections[f"industry.{item.key}"] for item in industries),
        key=lambda section: sum(repo["weekly_stars"] for repo in section["repos"][:10]),
    )
    top_weekly = sections["weekly"]["repos"][0] if sections["weekly"]["repos"] else None
    newcomers = sections["newcomers"]["repos"]
    anomalies = [repo for repo in sections["heat"]["repos"] if repo["anomaly"]]

    executive = [
        f"本周最热行业是 {hottest_industry['label']}，前 10 名累计新增 {sum(repo['weekly_stars'] for repo in hottest_industry['repos'][:10])} Star。",
        f"增长最快的项目是 {top_weekly['full_name']}，本周新增 {top_weekly['weekly_stars']} Star。"
        if top_weekly
        else "本周没有检测到有效的周增长数据。",
        f"本周共有 {len(newcomers)} 个近 90 天新项目进入新秀候选池，其中 {min(len(newcomers), 5)} 个热度表现突出。",
    ]
    if anomalies:
        executive.append(f"检测到 {len(anomalies)} 个异常增长项目，说明榜单中存在明显的爆发型仓库。")

    industry_observations: dict[str, list[str]] = {}
    for item in industries:
        key = f"industry.{item.key}"
        section = sections[key]
        top_growth = sorted(section["repos"], key=lambda repo: repo["weekly_stars"], reverse=True)[:10]
        topic_counter = Counter(
            topic
            for repo in top_growth
            for topic in (repo["matched_topics"] or repo["topics"])
        )
        lang_counter = Counter(repo["language"] for repo in section["repos"][:15])
        newcomer_count = sum(1 for repo in section["repos"] if repo["newcomer"])
        anomaly_names = [repo["full_name"] for repo in section["repos"] if repo["anomaly"]][:2]
        dominant_topics = " / ".join(topic for topic, _ in topic_counter.most_common(2)) or "跨主题"
        dominant_language = " / ".join(lang for lang, _ in lang_counter.most_common(2)) or "多语言"
        notes = [
            f"本周增长主要由 {dominant_topics} 驱动，说明该行业的热门仓库更集中在这些子赛道。",
            f"榜单头部主要语言是 {dominant_language}，技术栈集中度比较明显。",
            f"当前行业榜中有 {newcomer_count} 个近 90 天新项目，适合关注新秀信号。",
        ]
        if anomaly_names:
            notes.append(f"异常增长项目包括 {', '.join(anomaly_names)}，存在短期爆发机会。")
        industry_observations[key] = notes[:3]
    return executive, industry_observations


def _attach_insights(
    sections: dict[str, dict[str, Any]],
    executive_summary: list[str],
    industry_observations: dict[str, list[str]],
) -> None:
    sections["global"]["insights"] = executive_summary[:3]
    sections["weekly"]["insights"] = [
        "周增长榜适合发现短期爆发的项目，排名更能反映近期势能。",
        "如果某项目同时出现在热度榜和行业榜，往往意味着它既有规模也有增量。",
        "增长胶囊颜色会帮助你区分持续上涨、新上榜和热度回落项目。",
    ]
    sections["heat"]["insights"] = [
        "热度评分会弱化单纯大盘 Star 的影响，更多强调近期活跃度。",
        "持续上榜项目通常在热度榜也会维持稳定高位。",
        "异常增长标记可帮助识别由热点事件驱动的项目。",
    ]
    sections["newcomers"]["insights"] = [
        "新秀榜聚焦近 90 天创建的仓库，用来捕捉早期成长机会。",
        "如果新秀项目同时具备高增长率和较高热度分，后续值得持续追踪。",
        "连续上榜的新秀更可能从短期爆发转成长期趋势。",
    ]
    for key, notes in industry_observations.items():
        sections[key]["insights"] = notes


def _build_summary_cards(repos: dict[str, dict[str, Any]], sections: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    hottest_industry = max(
        [section for key, section in sections.items() if key.startswith("industry.")],
        key=lambda section: sum(repo["weekly_stars"] for repo in section["repos"][:10]),
    )
    fastest_repo = sections["weekly"]["repos"][0] if sections["weekly"]["repos"] else None
    newcomer_count = sum(1 for repo in repos.values() if repo["newcomer"] and repo["weekly_stars"] > 0)
    anomaly_count = sum(1 for repo in repos.values() if repo["anomaly"])
    new_entry_count = len(
        {
            item["full_name"]
            for report in [section["change_report"] for section in sections.values()]
            for item in report["new_entries"]
        }
    )
    return [
        {
            "label": "本周最热行业",
            "value": hottest_industry["label"],
            "description": "按前 10 名累计周增长计算",
            "tone": "mint",
        },
        {
            "label": "增长最快项目",
            "value": fastest_repo["full_name"] if fastest_repo else "暂无",
            "description": f"周增 {fastest_repo['weekly_stars']} Star" if fastest_repo else "历史不足",
            "tone": "coral",
        },
        {
            "label": "新上榜数量",
            "value": str(new_entry_count),
            "description": "统计所有榜单中的新进入项目",
            "tone": "sky",
        },
        {
            "label": "异常项目数",
            "value": str(anomaly_count),
            "description": "周增长明显偏离历史中枢",
            "tone": "coral",
        },
        {
            "label": "新秀项目数",
            "value": str(newcomer_count),
            "description": "近 90 天创建且本周仍在上涨",
            "tone": "sky",
        },
        {
            "label": "总监控仓库数",
            "value": str(len(repos)),
            "description": "当前周用于分析与推荐的仓库池",
            "tone": "slate",
        },
    ]


def _make_section(
    *,
    key: str,
    title: str,
    label: str,
    group: str,
    description: str,
    repos: list[dict[str, Any]],
    topics: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "label": label,
        "group": group,
        "description": description,
        "topics": topics or [],
        "sort_options": [
            {"value": "heat_score", "label": "热度评分"},
            {"value": "weekly_stars", "label": "周增长"},
            {"value": "stars_total", "label": "总 Star"},
            {"value": "language", "label": "语言"},
            {"value": "pushed_at", "label": "最近更新"},
        ],
        "repos": repos,
        "insights": [],
        "change_report": {"new_entries": [], "dropped_entries": [], "rank_movers": []},
    }


def _sorted_payloads(
    repos: dict[str, dict[str, Any]],
    names: list[str],
    sort_key: str,
    limit: int,
) -> list[dict[str, Any]]:
    unique_names = list(dict.fromkeys(names))
    selected = [repos[name] for name in unique_names if name in repos]
    selected.sort(key=lambda repo: _sort_value(repo, sort_key), reverse=True)
    return [_repo_payload(repo) for repo in selected[:limit]]


def _repo_payload(repo: dict[str, Any]) -> dict[str, Any]:
    return {
        "full_name": repo["full_name"],
        "name": repo["name"],
        "html_url": repo["html_url"],
        "description": repo["description"],
        "language": repo["language"],
        "stars_total": repo["stars_total"],
        "weekly_stars": repo["weekly_stars"],
        "growth_4w": repo["growth_4w"],
        "growth_12w": repo["growth_12w"],
        "growth_rate": repo["growth_rate"],
        "heat_score": repo["heat_score"],
        "created_at": repo["created_at"],
        "updated_at": repo["updated_at"],
        "pushed_at": repo["pushed_at"],
        "open_issues_count": repo["open_issues_count"],
        "watchers_total": repo["watchers_total"],
        "forks_total": repo["forks_total"],
        "license_name": repo["license_name"],
        "homepage": repo["homepage"],
        "matched_topics": sorted(repo["matched_topics"]),
        "topics": repo["topics"],
        "all_topics": repo["all_topics"],
        "readme_excerpt": repo["readme_excerpt"] or repo["description"],
        "sparkline": repo["sparkline"],
        "history_points": repo["history_points"],
        "newcomer": repo["newcomer"],
        "anomaly": repo["anomaly"],
        "section_streak": 1,
        "related_repos": [],
        "owner_login": repo["owner_login"],
        "owner_avatar_url": repo["owner_avatar_url"],
        "qa_reason": repo["qa_reason"],
    }


def _build_qa_examples() -> list[str]:
    return [
        "本周 AI 赛道最值得关注的 5 个项目是什么？",
        "教育行业里哪些仓库在持续上榜？",
        "帮我找增长异常但还比较新的项目。",
    ]


def _build_reason(repo: dict[str, Any]) -> str:
    reasons = []
    if repo["weekly_stars"] > 0:
        reasons.append(f"周增 {repo['weekly_stars']} Star")
    if repo["newcomer"]:
        reasons.append("近 90 天创建")
    if repo["anomaly"]:
        reasons.append("存在异常增长")
    reasons.append(f"最近 {repo['push_days']} 天有代码推送")
    return "、".join(reasons)


def _historical_growth(points: list[dict[str, Any]], lookback: int) -> int:
    if len(points) <= 1:
        return 0
    baseline_index = max(0, len(points) - lookback - 1)
    return max(points[-1]["stars_total"] - points[baseline_index]["stars_total"], 0)


def _detect_anomaly(points: list[dict[str, Any]], current_weekly: int, growth_rate: float) -> bool:
    if current_weekly <= 0:
        return False
    deltas = []
    for previous, current in zip(points, points[1:]):
        deltas.append(max(current["stars_total"] - previous["stars_total"], 0))
    historical = deltas[:-1] if len(deltas) > 1 else []
    if not historical:
        return current_weekly >= 300 or growth_rate >= 0.25
    avg = sum(historical) / len(historical)
    variance = sum((value - avg) ** 2 for value in historical) / max(len(historical), 1)
    std = variance ** 0.5
    threshold = max(80, avg + std * 2.5, avg * 3)
    return current_weekly >= threshold or growth_rate >= 0.18


def _rank_movers(current_names: list[str], previous_names: list[str]) -> list[dict[str, Any]]:
    previous_index = {name: idx + 1 for idx, name in enumerate(previous_names)}
    movers = []
    for idx, name in enumerate(current_names):
        if name not in previous_index:
            continue
        current_rank = idx + 1
        previous_rank = previous_index[name]
        delta = previous_rank - current_rank
        if delta != 0:
            movers.append(
                {
                    "full_name": name,
                    "current_rank": current_rank,
                    "previous_rank": previous_rank,
                    "delta": delta,
                }
            )
    return sorted(movers, key=lambda item: (abs(item["delta"]), -item["current_rank"]), reverse=True)[:5]


def _sort_value(repo: dict[str, Any], sort_key: str) -> Any:
    if sort_key == "language":
        return repo["language"].lower()
    if sort_key == "pushed_at":
        return repo["pushed_at"] or ""
    return repo.get(sort_key, 0)


def _days_since(timestamp: str | None, now: datetime) -> int:
    if not timestamp:
        return 365
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return 365
    delta = now.astimezone(dt.tzinfo) - dt
    return max(delta.days, 0)


def _recency_score(days: int, scale: int) -> float:
    return round(1 / (1 + days / max(scale, 1)), 4)
