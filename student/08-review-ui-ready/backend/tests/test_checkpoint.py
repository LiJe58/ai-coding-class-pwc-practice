import csv
import io
import json
import sqlite3
import unittest
import uuid
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import DAY3_DB_PATH, WORKING_PAPER_PATH, app, day3_payload, review_events


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

    def test_action_id_prevents_duplicates_and_full_history_is_visible(self) -> None:
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

        new_paper = json.loads(WORKING_PAPER_PATH.read_text(encoding="utf-8"))
        new_paper["generated_at"] = "2026-08-14 09:00:00"
        self.assertIsNone(day3_payload(new_paper, review_events())["items"][0]["current_review"])

    def test_completion_summary_and_csv_export_gate(self) -> None:
        initial = self.client.get("/api/day3/reviews").json()["summary"]
        self.assertEqual([initial["total_count"], initial["reviewed_count"], initial["pending_count"]], [12, 0, 12])
        self.assertFalse(initial["export_ready"])
        self.assertEqual(self.client.get("/api/day3/export.csv", params={"reviewer_user_id": "U701"}).status_code, 409)

        conclusions = ["normal"] * 4 + ["control_exception", "follow_up"] + ["control_exception"] * 6
        for change_id, conclusion in zip((sample["change_id"] for sample in json.loads(WORKING_PAPER_PATH.read_text(encoding="utf-8"))["samples"]), conclusions, strict=True):
            response = self.client.post(f"/api/day3/reviews/{change_id}", json={
                "review_action_id": str(uuid.uuid4()),
                "reviewer_user_id": "U701",
                "conclusion": conclusion,
                "review_comment": f"{change_id} 검토",
            })
            self.assertEqual(response.status_code, 200)

        summary = self.client.get("/api/day3/reviews").json()["summary"]
        self.assertEqual(
            [summary[key] for key in ("total_count", "reviewed_count", "pending_count", "normal_count", "follow_up_count", "control_exception_count")],
            [12, 12, 0, 4, 1, 7],
        )
        export = self.client.get("/api/day3/export.csv", params={"reviewer_user_id": "U701"})
        self.assertEqual(export.status_code, 200)
        self.assertEqual(len(list(csv.DictReader(io.StringIO(export.content.decode("utf-8-sig"))))), 12)
        self.assertEqual(self.client.get("/api/day3/export.csv", params={"reviewer_user_id": "U601"}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
