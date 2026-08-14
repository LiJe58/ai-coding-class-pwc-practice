import csv
import hashlib
import io
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as main


ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "output" / "day-2" / "working-paper.json"
PAPER_SHA256 = "2d702687e1f52ce475266ccf7df2a7a7acffdb799e098fba8b065fb8dc21616b"


class InstructorCheckpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temporary.name) / "day3_reviews.sqlite3"
        self.db_patch = patch.object(main, "DAY3_DB_PATH", self.db_path)
        self.db_patch.start()
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        self.db_patch.stop()
        self.temporary.cleanup()

    @staticmethod
    def model_responses(change_id: str = "CHG-2608-023") -> list[dict]:
        return [
            {
                "output": [{
                    "type": "function_call",
                    "name": "get_case_evidence",
                    "call_id": "call-1",
                    "arguments": json.dumps({"change_id": change_id, "requester_user_id": "U701"}),
                }],
                "output_text": "",
            },
            {"output": [], "output_text": "승인 기록이 없어 사람의 추가 확인이 필요합니다."},
        ]

    def run_agent(self, change_id: str = "CHG-2608-023"):
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret", "OPENAI_MODEL": "test-model"}, clear=True),
            patch.object(main, "call_model", side_effect=self.model_responses(change_id)) as model,
            patch.object(main, "call_evidence_tool", wraps=main.call_evidence_tool) as tool,
        ):
            response = self.client.post(f"/api/day2/agent-preview/{change_id}", json={"requester_user_id": "U701"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(model.call_count, 2)
        tool.assert_called_once_with(change_id, "U701")
        return response

    def agent_history(self, change_id: str = "CHG-2608-023") -> list[dict]:
        response = self.client.get("/api/day2/agent-runs", params={"change_id": change_id, "requester_user_id": "U701"})
        self.assertEqual(response.status_code, 200)
        return response.json()["runs"]

    def test_agent_success_appends_and_survives_new_connections(self) -> None:
        self.run_agent()
        first = self.agent_history()
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["status"], "success")
        self.assertEqual(first[0]["tool_name"], "get_case_evidence")
        self.assertEqual(json.loads(first[0]["tool_input_json"]), {"change_id": "CHG-2608-023", "requester_user_id": "U701"})

        self.run_agent()
        reopened = TestClient(main.app).get("/api/day2/agent-runs", params={"change_id": "CHG-2608-023", "requester_user_id": "U701"})
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(len(reopened.json()["runs"]), 2)

    def test_permission_is_denied_before_model_and_tool_and_saved_safely(self) -> None:
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "top-secret", "OPENAI_MODEL": "secret-model"}, clear=True),
            patch.object(main, "call_model") as model,
            patch.object(main, "call_evidence_tool") as tool,
        ):
            response = self.client.post("/api/day2/agent-preview/CHG-2608-023", json={"requester_user_id": "U601"})
        self.assertEqual(response.status_code, 403)
        model.assert_not_called()
        tool.assert_not_called()

        with self.db_path.open("rb") as file:
            stored = file.read()
        self.assertNotIn(b"top-secret", stored)
        self.assertNotIn(b"secret-model", stored)
        self.assertNotIn(b"vendor_change", stored)
        with patch.dict(os.environ, {}, clear=True):
            denied = self.client.get("/api/day2/agent-runs", params={"change_id": "CHG-2608-023", "requester_user_id": "U601"})
        self.assertEqual(denied.status_code, 403)
        runs = self.agent_history()
        self.assertEqual(runs[0]["status"], "permission_denied")

    def test_missing_config_is_503_and_saved_without_calls(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(main, "call_model") as model,
            patch.object(main, "call_evidence_tool") as tool,
        ):
            response = self.client.post("/api/day2/agent-preview/CHG-2608-023", json={"requester_user_id": "U701"})
        self.assertEqual(response.status_code, 503)
        model.assert_not_called()
        tool.assert_not_called()
        self.assertEqual(self.agent_history()[0]["status"], "config_error")

    def test_tool_and_model_failures_are_distinct(self) -> None:
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test-model"}, clear=True),
            patch.object(main, "call_model", side_effect=self.model_responses()),
            patch.object(main, "call_evidence_tool", side_effect=RuntimeError("raw ERP failure")),
        ):
            tool_failure = self.client.post("/api/day2/agent-preview/CHG-2608-023", json={"requester_user_id": "U701"})
        self.assertEqual(tool_failure.status_code, 502)
        self.assertEqual(self.agent_history()[0]["status"], "tool_error")

        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test-model"}, clear=True),
            patch.object(main, "call_model", side_effect=RuntimeError("raw model failure")),
            patch.object(main, "call_evidence_tool") as tool,
        ):
            model_failure = self.client.post("/api/day2/agent-preview/CHG-2608-023", json={"requester_user_id": "U701"})
        self.assertEqual(model_failure.status_code, 502)
        tool.assert_not_called()
        runs = self.agent_history()
        self.assertEqual([run["status"] for run in runs[:2]], ["model_error", "tool_error"])
        self.assertNotIn("raw", json.dumps(runs, ensure_ascii=False))

    def test_agent_runs_do_not_change_existing_artifacts_or_reviews(self) -> None:
        paper_before = PAPER.read_bytes()
        day1_before = self.client.get("/api/control-test").json()["summary"]
        review_before = self.client.get("/api/day3/reviews").json()["summary"]
        self.run_agent()
        self.run_agent()
        self.assertEqual(PAPER.read_bytes(), paper_before)
        self.assertEqual(self.client.get("/api/control-test").json()["summary"], day1_before)
        self.assertEqual(self.client.get("/api/day3/reviews").json()["summary"], review_before)
        self.assertEqual(day1_before, {"population_count": 30, "valid_count": 29, "normal_count": 21, "review_count": 8, "input_error_count": 1})
        self.assertEqual(len(self.client.get("/api/day2/working-paper").json()["working_paper"]["samples"]), 12)

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
