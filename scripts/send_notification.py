from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from github_trends.notifier import deliver_report, send_failure_notice


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send dashboard notifications.")
    parser.add_argument("--status", choices=["success", "failure"], required=True)
    parser.add_argument("--message", help="Failure message or custom note.")
    parser.add_argument("--report", help="Path to the markdown report file.")
    parser.add_argument("--dashboard-json", help="Path to the generated dashboard.json file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.status == "failure":
        send_failure_notice(args.message or "Dashboard workflow failed.")
        return

    if not args.report or not args.dashboard_json:
        raise SystemExit("--report and --dashboard-json are required for success notifications.")

    report_text = Path(args.report).read_text(encoding="utf-8")
    import json

    dashboard = json.loads(Path(args.dashboard_json).read_text(encoding="utf-8"))
    deliver_report(report_text, dashboard)


if __name__ == "__main__":
    main()
