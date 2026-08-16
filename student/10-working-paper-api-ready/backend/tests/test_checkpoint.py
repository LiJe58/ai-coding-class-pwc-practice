import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "output" / "day-2" / "working-paper.json"


class WorkingPaperApiCheckpointTest(unittest.TestCase):
    def test_working_paper_is_available_from_the_api(self) -> None:
        paper = json.loads(PAPER.read_text(encoding="utf-8"))
        self.assertEqual(paper["schema_version"], "1.0")
        self.assertEqual(
            [paper["summary"][key] for key in ("sample_count", "normal_sample_count", "review_sample_count", "draft_count")],
            [12, 4, 8, 12],
        )
        self.assertTrue(all(sample["requires_human_review"] is True for sample in paper["samples"]))
        self.assertTrue(all("human_conclusion" not in sample for sample in paper["samples"]))

        response = TestClient(app).get("/api/day2/working-paper")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["working_paper"], paper)
        self.assertNotIn("/api/day2/working-paper", (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
