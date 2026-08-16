import sqlite3
import unittest
import uuid
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import DAY3_DB_PATH, app


ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "output" / "day-2" / "working-paper.json"


class ReviewStorageCheckpointTest(unittest.TestCase):
    def setUp(self) -> None:
        DAY3_DB_PATH.unlink(missing_ok=True)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        DAY3_DB_PATH.unlink(missing_ok=True)

    def payload(self, user: str = "U701", conclusion: str = "normal", comment: str = "검토 완료") -> dict:
        return {"review_action_id": str(uuid.uuid4()), "reviewer_user_id": user, "conclusion": conclusion, "review_comment": comment}

    def event_count(self) -> int:
        if not DAY3_DB_PATH.exists():
            return 0
        with closing(sqlite3.connect(DAY3_DB_PATH)) as connection:
            return connection.execute("SELECT count(*) FROM review_events").fetchone()[0]

    def test_review_events_are_authorized_validated_and_append_only(self) -> None:
        saved = self.client.post("/api/day3/reviews/CHG-2608-001", json=self.payload())
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(self.event_count(), 1)

        for change_id, payload, status in (
            ("CHG-2608-002", self.payload(user="U601"), 403),
            ("CHG-2608-002", self.payload(conclusion="maybe"), 422),
            ("CHG-2608-002", self.payload(comment="   "), 422),
            ("CHG-2608-030", self.payload(), 404),
        ):
            self.assertEqual(self.client.post(f"/api/day3/reviews/{change_id}", json=payload).status_code, status)
            self.assertEqual(self.event_count(), 1)

        frontend = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
        self.assertIn("/api/day2/working-paper", frontend)
        self.assertIn("최종 검토 화면은 다음 단계에서 연결됩니다", frontend)
        self.assertNotIn("/api/day3/reviews", frontend)

        methods = {(route.path, method) for route in app.routes for method in getattr(route, "methods", set())}
        self.assertNotIn(("/api/day3/reviews/{change_id}", "PUT"), methods)
        self.assertNotIn(("/api/day3/reviews/{change_id}", "DELETE"), methods)


if __name__ == "__main__":
    unittest.main()
