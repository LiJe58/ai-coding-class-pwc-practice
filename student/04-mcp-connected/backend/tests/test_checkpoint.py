import hashlib
import unittest
from pathlib import Path

from app.main import DAY2_SAMPLE_IDS
from mcp_server import get_control_population, select_day2_samples


ROOT = Path(__file__).resolve().parents[2]


class McpCheckpointTest(unittest.TestCase):
    def test_mock_erp_is_read_only_and_preserves_inputs(self) -> None:
        before = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT / "input" / "day-1").glob("*.csv"))
        }
        population = get_control_population("all")
        samples = select_day2_samples()
        self.assertEqual(list(population["summary"].values()), [30, 29, 21, 8, 1])
        self.assertEqual([row["change_id"] for row in samples["rows"]], DAY2_SAMPLE_IDS)
        self.assertEqual(samples["summary"], {"sample_count": 12, "normal_count": 4, "review_count": 8})
        self.assertEqual(before, {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT / "input" / "day-1").glob("*.csv"))
        })
        source = (ROOT / "backend" / "mcp_server.py").read_text(encoding="utf-8")
        self.assertNotIn("@mcp.tool()\ndef write", source)
        self.assertNotIn("@mcp.tool()\ndef delete", source)


if __name__ == "__main__":
    unittest.main()
