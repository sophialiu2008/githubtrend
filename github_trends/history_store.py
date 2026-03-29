from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class HistoryStore:
    latest_input_path: Path
    latest_output_path: Path
    archive_dir: Path

    def load_latest(self) -> dict[str, Any]:
        return self._read_json(self.latest_input_path) or {
            "generated_at": None,
            "snapshot_date": None,
            "repos": {},
            "sections": {},
        }

    def load_snapshots(self, limit: int | None = None) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        if self.archive_dir.exists():
            for file in sorted(self.archive_dir.glob("*.json")):
                payload = self._read_json(file)
                if payload:
                    snapshots.append(payload)
        latest = self._read_json(self.latest_input_path)
        if latest and (not snapshots or snapshots[-1].get("snapshot_date") != latest.get("snapshot_date")):
            snapshots.append(latest)
        return snapshots[-limit:] if limit else snapshots

    def repo_history(self, full_name: str, snapshots: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
        points: list[dict[str, Any]] = []
        for snapshot in snapshots[-limit:]:
            repo = snapshot.get("repos", {}).get(full_name)
            if not repo:
                continue
            points.append(
                {
                    "date": snapshot.get("snapshot_date"),
                    "stars_total": int(repo.get("stars_total", 0)),
                    "weekly_stars": int(repo.get("weekly_stars", 0)),
                    "heat_score": float(repo.get("heat_score", 0)),
                }
            )
        return points

    def write_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.latest_output_path.parent.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        content = json.dumps(snapshot, ensure_ascii=False, indent=2)
        self.latest_output_path.write_text(content, encoding="utf-8")
        snapshot_date = snapshot["snapshot_date"]
        (self.archive_dir / f"{snapshot_date}.json").write_text(content, encoding="utf-8")

    def compare_section(
        self,
        current_names: list[str],
        previous_names: list[str],
        limit: int = 5,
    ) -> dict[str, list[dict[str, Any]]]:
        previous_index = {name: idx + 1 for idx, name in enumerate(previous_names)}
        current_index = {name: idx + 1 for idx, name in enumerate(current_names)}
        new_entries = [
            {"full_name": name, "rank": current_index[name]}
            for name in current_names
            if name not in previous_index
        ][:limit]
        dropped = [
            {"full_name": name, "previous_rank": previous_index[name]}
            for name in previous_names
            if name not in current_index
        ][:limit]
        movers = sorted(
            [
                {
                    "full_name": name,
                    "current_rank": current_index[name],
                    "previous_rank": previous_index[name],
                    "delta": previous_index[name] - current_index[name],
                }
                for name in current_names
                if name in previous_index and previous_index[name] != current_index[name]
            ],
            key=lambda item: (abs(item["delta"]), item["current_rank"]),
            reverse=True,
        )[:limit]
        return {
            "new_entries": new_entries,
            "dropped_entries": dropped,
            "rank_movers": movers,
        }

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
