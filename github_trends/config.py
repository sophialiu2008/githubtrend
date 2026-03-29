from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_TIMEZONE = "Asia/Shanghai"
CACHE_TTL_HOURS = 12
NEWCOMER_WINDOW_DAYS = 90
SPARKLINE_WEEKS = 12
GROWTH_LOOKBACK_WEEKS = 4


@dataclass(frozen=True)
class IndustryConfig:
    key: str
    label: str
    description: str
    topics: list[str]
    keywords: list[str]


def load_topics_config(path: Path) -> list[IndustryConfig]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    industries = payload.get("industries", {})
    configs: list[IndustryConfig] = []
    for key, item in industries.items():
        configs.append(
            IndustryConfig(
                key=key,
                label=item["label"],
                description=item["description"],
                topics=list(item["topics"]),
                keywords=list(item.get("keywords", [])),
            )
        )
    return configs


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def iso_date_label(value: str) -> str:
    return value[:10]


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)

