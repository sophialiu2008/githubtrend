import json
import tempfile
import unittest
from pathlib import Path

from github_trends.history_store import HistoryStore


class HistoryStoreTests(unittest.TestCase):
    def test_compare_section_detects_new_dropped_and_movers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = HistoryStore(
                latest_input_path=root / "latest.json",
                latest_output_path=root / "latest-out.json",
                archive_dir=root / "snapshots",
            )
            report = store.compare_section(
                ["a", "b", "c"],
                ["b", "d", "a"],
            )
            self.assertEqual(report["new_entries"][0]["full_name"], "c")
            self.assertEqual(report["dropped_entries"][0]["full_name"], "d")
            self.assertEqual(report["rank_movers"][0]["full_name"], "a")

    def test_write_snapshot_writes_latest_and_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = HistoryStore(
                latest_input_path=root / "latest.json",
                latest_output_path=root / "out" / "latest.json",
                archive_dir=root / "out" / "snapshots",
            )
            snapshot = {"snapshot_date": "2026-03-29", "repos": {}, "sections": {}}
            store.write_snapshot(snapshot)
            self.assertTrue((root / "out" / "latest.json").exists())
            self.assertTrue((root / "out" / "snapshots" / "2026-03-29.json").exists())


if __name__ == "__main__":
    unittest.main()

