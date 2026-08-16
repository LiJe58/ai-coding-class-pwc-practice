import unittest

from app.main import DAY2_SAMPLE_IDS
from mcp_server import select_day2_samples


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


if __name__ == "__main__":
    unittest.main()
