import unittest

from github_trends.ranking_service import answer_question, current_time_strings


class RankingServiceTests(unittest.TestCase):
    def test_snapshot_label_override_is_used(self) -> None:
        _, snapshot_date, _ = current_time_strings("2026-03-22")
        self.assertEqual(snapshot_date, "2026-03-22")

    def test_answer_question_uses_requested_section(self) -> None:
        page_data = {
            "sections": {
                "weekly": {
                    "title": "周增长榜",
                    "label": "周增长榜",
                    "group": "overview",
                    "repos": [
                        {
                            "full_name": "foo/bar",
                            "weekly_stars": 100,
                            "heat_score": 90,
                            "qa_reason": "周增高",
                            "section_streak": 2,
                            "newcomer": False,
                            "anomaly": True,
                        }
                    ],
                },
                "newcomers": {
                    "title": "新秀榜",
                    "label": "新秀榜",
                    "group": "overview",
                    "repos": [
                        {
                            "full_name": "new/repo",
                            "weekly_stars": 30,
                            "heat_score": 88,
                            "qa_reason": "新秀",
                            "section_streak": 1,
                            "newcomer": True,
                            "anomaly": False,
                        }
                    ],
                },
                "heat": {"title": "热度榜", "label": "热度榜", "group": "overview", "repos": []},
                "global": {"title": "全球榜", "label": "全球榜", "group": "overview", "repos": []},
            }
        }
        text = answer_question(page_data, "给我 1 个新秀项目")
        self.assertIn("new/repo", text)


if __name__ == "__main__":
    unittest.main()
