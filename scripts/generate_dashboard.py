from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from github_trends.config import CACHE_TTL_HOURS, load_topics_config
from github_trends.github_client import GitHubClient
from github_trends.history_store import HistoryStore
from github_trends.notifier import deliver_report
from github_trends.ranking_service import (
    answer_question,
    build_dashboard,
    collect_current_repositories,
    enrich_repositories,
)
from github_trends.site_renderer import write_dashboard_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the GitHub industry trends dashboard.")
    parser.add_argument("--config", default="config/topics.yaml")
    parser.add_argument("--template", default="templates/index.html.j2")
    parser.add_argument("--cache-dir", default="data/cache")
    parser.add_argument("--history-input", default="data/history/latest.json")
    parser.add_argument("--history-output", default="dist/data/history/latest.json")
    parser.add_argument("--history-archive-dir", default="dist/data/history/snapshots")
    parser.add_argument("--output-html", default="dist/index.html")
    parser.add_argument("--output-json", default="dist/dashboard.json")
    parser.add_argument("--output-report", default="dist/weekly-report.md")
    parser.add_argument("--snapshot-label", help="Optional YYYY-MM-DD label for manual backfill or reruns.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--deliver-subscriptions", action="store_true")
    parser.add_argument("--question", help="Answer a natural-language question after building the dashboard.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required to query the GitHub API.")

    industries = load_topics_config(Path(args.config))
    history_store = HistoryStore(
        latest_input_path=Path(args.history_input),
        latest_output_path=Path(args.history_output),
        archive_dir=Path(args.history_archive_dir),
    )
    historical_snapshots = history_store.load_snapshots(limit=12)
    latest_snapshot = history_store.load_latest()

    client = GitHubClient(
        token=token,
        cache_dir=Path(args.cache_dir),
        cache_ttl_hours=CACHE_TTL_HOURS,
    )
    repos, sections_raw = collect_current_repositories(client, industries)
    enrich_repositories(client, repos)

    page_data, snapshot, markdown_report = build_dashboard(
        repos=repos,
        sections_raw=sections_raw,
        industries=industries,
        latest_snapshot=latest_snapshot,
        historical_snapshots=historical_snapshots,
        snapshot_label=args.snapshot_label,
    )

    history_store.write_snapshot(snapshot)
    write_dashboard_files(
        template_path=Path(args.template),
        html_output_path=Path(args.output_html),
        json_output_path=Path(args.output_json),
        report_output_path=Path(args.output_report),
        page_data=page_data,
        markdown_report=markdown_report,
    )

    if args.deliver_subscriptions:
        delivered = deliver_report(markdown_report, page_data)
        print(f"Delivered subscriptions: {', '.join(delivered) if delivered else 'none'}")

    if args.question:
        print(answer_question(page_data, args.question))

    if args.strict and not page_data["validation"]["global_top_count_ok"]:
        raise SystemExit("Validation failed: global top list contains fewer than 100 repositories.")


if __name__ == "__main__":
    main()
