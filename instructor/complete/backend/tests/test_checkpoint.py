import csv
import hashlib
import io
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import DAY3_DB_PATH, app


ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "output" / "day-2" / "working-paper.json"
PAPER_SHA256 = "cf21cdfa95b743bce7afde3e22ca1bced3daa2c17d0c1b7f0cae2223615f77ae"


class InstructorCheckpointTest(unittest.TestCase):
    def setUp(self) -> None:
        DAY3_DB_PATH.unlink(missing_ok=True)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        DAY3_DB_PATH.unlink(missing_ok=True)

    def save(self, change_id: str, conclusion: str) -> None:
        response = self.client.post(f"/api/day3/reviews/{change_id}", json={
            "review_action_id": str(uuid.uuid4()),
            "reviewer_user_id": "U701",
            "conclusion": conclusion,
            "review_comment": f"{change_id} 강사 검토",
        })
        self.assertEqual(response.status_code, 200)

    def test_export_gate_and_final_totals(self) -> None:
        initial = self.client.get("/api/day3/reviews").json()["summary"]
        self.assertEqual([initial[key] for key in ("total_count", "reviewed_count", "pending_count")], [12, 0, 12])
        self.save("CHG-2608-001", "normal")
        self.assertEqual(self.client.get("/api/day3/export.csv", params={"reviewer_user_id": "U701"}).status_code, 409)

        ids = [f"CHG-2608-{index:03d}" for index in range(2, 5)] + [f"CHG-2608-{index:03d}" for index in range(22, 30)]
        conclusions = ["normal"] * 3 + ["follow_up"] + ["control_exception"] * 7
        for change_id, conclusion in zip(ids, conclusions, strict=True):
            self.save(change_id, conclusion)
        summary = self.client.get("/api/day3/reviews").json()["summary"]
        self.assertEqual(
            [summary[key] for key in ("total_count", "reviewed_count", "pending_count", "normal_count", "follow_up_count", "control_exception_count")],
            [12, 12, 0, 4, 1, 7],
        )
        self.assertTrue(summary["export_ready"])
        export = self.client.get("/api/day3/export.csv", params={"reviewer_user_id": "U701"})
        self.assertEqual(export.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(export.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 12)
        self.assertEqual(hashlib.sha256(PAPER.read_bytes()).hexdigest(), PAPER_SHA256)
        self.assertTrue((ROOT / "templates" / "application-scope.md").is_file())


if __name__ == "__main__":
    unittest.main()
