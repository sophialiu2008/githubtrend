import json
import tempfile
import unittest
from pathlib import Path

from github_trends.site_renderer import write_dashboard_files


class SiteRendererTests(unittest.TestCase):
    def test_write_dashboard_files_outputs_html_json_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.html"
            template.write_text("<html><head><title>__TITLE__</title></head><body><script>const data = __DASHBOARD_JSON__;</script></body></html>", encoding="utf-8")
            page_data = {
                "title": "Test Dashboard",
                "executive_summary": [],
            }
            write_dashboard_files(
                template_path=template,
                html_output_path=root / "dist" / "index.html",
                json_output_path=root / "dist" / "dashboard.json",
                report_output_path=root / "dist" / "weekly-report.md",
                page_data=page_data,
                markdown_report="# report",
            )
            html = (root / "dist" / "index.html").read_text(encoding="utf-8")
            data = json.loads((root / "dist" / "dashboard.json").read_text(encoding="utf-8"))
            self.assertIn("Test Dashboard", html)
            self.assertEqual(data["title"], "Test Dashboard")
            self.assertEqual((root / "dist" / "weekly-report.md").read_text(encoding="utf-8"), "# report")


if __name__ == "__main__":
    unittest.main()

