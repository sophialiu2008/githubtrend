from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_dashboard_files(
    *,
    template_path: Path,
    html_output_path: Path,
    json_output_path: Path,
    report_output_path: Path,
    page_data: dict[str, Any],
    markdown_report: str,
) -> None:
    html_output_path.parent.mkdir(parents=True, exist_ok=True)
    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    report_output_path.parent.mkdir(parents=True, exist_ok=True)

    dashboard_json = json.dumps(page_data, ensure_ascii=False)
    json_output_path.write_text(
        json.dumps(page_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_output_path.write_text(markdown_report, encoding="utf-8")

    html = render_html(template_path, page_data["title"], dashboard_json)
    html_output_path.write_text(html, encoding="utf-8")


def render_html(template_path: Path, title: str, dashboard_json: str) -> str:
    safe_json = dashboard_json.replace("</", "<\\/")
    template = template_path.read_text(encoding="utf-8")
    return template.replace("__TITLE__", title).replace("__DASHBOARD_JSON__", safe_json)
