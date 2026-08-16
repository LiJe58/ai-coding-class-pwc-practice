import unittest
from pathlib import Path

from app.main import DAY2_SAMPLE_IDS
from mcp_server import select_day2_samples

ROOT = Path(__file__).resolve().parents[2]


class SamplesCheckpointTest(unittest.TestCase):
    def test_fixed_samples_are_repeatable(self) -> None:
        first = select_day2_samples()
        second = select_day2_samples()
        expected = [
            *[f"CHG-2608-{index:03d}" for index in range(1, 5)],
            *[f"CHG-2608-{index:03d}" for index in range(22, 30)],
        ]
        self.assertEqual(DAY2_SAMPLE_IDS, expected)
        self.assertEqual([row["change_id"] for row in first["rows"]], expected)
        self.assertEqual(first, second)
        self.assertEqual(first["summary"], {"sample_count": 12, "normal_count": 4, "review_count": 8})
        frontend = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
        self.assertIn("고정 샘플 12건 선택", frontend)


if __name__ == "__main__":
    unittest.main()
