from pathlib import Path
import unittest

from github_trends.config import load_topics_config


class ConfigTests(unittest.TestCase):
    def test_topics_config_loads_expected_industries(self) -> None:
        items = load_topics_config(Path("config/topics.yaml"))
        self.assertEqual(len(items), 4)
        self.assertEqual(items[0].key, "education")
        self.assertIn("edtech", items[0].topics)


if __name__ == "__main__":
    unittest.main()

