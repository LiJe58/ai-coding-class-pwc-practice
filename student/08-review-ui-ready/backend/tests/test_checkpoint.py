import sqlite3
import unittest
import uuid
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import DAY3_DB_PATH, app


ROOT = Path(__file__).resolve().parents[2]


class ReviewUiCheckpointTest(unittest.TestCase):
    def setUp(self) -> None:
        DAY3_DB_PATH.unlink(missing_ok=True)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        DAY3_DB_PATH.unlink(missing_ok=True)

    def event_count(self) -> int:
        with closing(sqlite3.connect(DAY3_DB_PATH)) as connection:
            return connection.execute("SELECT count(*) FROM review_events").fetchone()[0]

    def test_action_id_is_idempotent_and_full_history_is_visible(self) -> None:
        action_id = str(uuid.uuid4())
        first = {"review_action_id": action_id, "reviewer_user_id": "U701", "conclusion": "normal", "review_comment": "첫 검토"}
        endpoint = "/api/day3/reviews/CHG-2608-001"
        self.assertEqual(self.client.post(endpoint, json=first).status_code, 200)
        self.assertEqual(self.client.post(endpoint, json=first).status_code, 200)
        self.assertEqual(self.event_count(), 1)

        conflict = {**first, "review_comment": "충돌 요청"}
        self.assertEqual(self.client.post(endpoint, json=conflict).status_code, 409)
        self.assertEqual(self.event_count(), 1)

        revised = {**first, "review_action_id": str(uuid.uuid4()), "conclusion": "follow_up", "review_comment": "추가 확인"}
        self.assertEqual(self.client.post(endpoint, json=revised).status_code, 200)
        self.assertEqual(self.event_count(), 2)
        item = self.client.get("/api/day3/reviews").json()["items"][0]
        self.assertEqual(item["current_review"]["conclusion"], "follow_up")
        self.assertEqual(len(item["history"]), 2)

        denied = {**first, "review_action_id": str(uuid.uuid4()), "reviewer_user_id": "U601"}
        self.assertEqual(self.client.post("/api/day3/reviews/CHG-2608-002", json=denied).status_code, 403)
        frontend = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
        for contract in ("Agent 초안", "사람 결론", "전체 이력", "/api/day3/reviews"):
            self.assertIn(contract, frontend)


if __name__ == "__main__":
    unittest.main()
