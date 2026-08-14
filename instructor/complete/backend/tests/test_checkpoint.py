import csv
import hashlib
import io
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import DAY3_DB_PATH, app, day3_ready_payload, review_events
from app.agent import load_agent_settings


ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "output" / "day-2" / "working-paper.json"
PAPER_SHA256 = "2d702687e1f52ce475266ccf7df2a7a7acffdb799e098fba8b065fb8dc21616b"


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

    @staticmethod
    def agent_client(change_id: str, requester_user_id: str):
        responses = SimpleNamespace()
        responses.call_count = 0

        async def create(**request):
            responses.call_count += 1
            if responses.call_count == 1:
                return SimpleNamespace(
                    output=[SimpleNamespace(
                        type="function_call",
                        name="get_case_evidence",
                        arguments=json.dumps({"change_id": change_id, "requester_user_id": requester_user_id}),
                        call_id="call-1",
                    )],
                    output_text="",
                )
            return SimpleNamespace(output=[], output_text="근거를 확인했습니다. 사람 검토가 필요합니다.")

        responses.create = create
        return SimpleNamespace(responses=responses)

    def test_agent_preview_is_read_only_and_permission_checked(self) -> None:
        before = self.client.get("/api/day3/reviews").json()
        paper_hash = hashlib.sha256(PAPER.read_bytes()).hexdigest()
        environment = {"OPENAI_API_KEY": uuid.uuid4().hex, "OPENAI_MODEL": "test-model"}

        with patch.dict(os.environ, environment, clear=False), patch(
            "app.agent.AsyncOpenAI", return_value=self.agent_client("CHG-2608-023", "U701")
        ):
            response = self.client.post(
                "/api/day2/agent-preview/CHG-2608-023",
                json={"requester_user_id": "U701"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["tool_events"], [{
            "tool": "get_case_evidence",
            "arguments": {"change_id": "CHG-2608-023", "requester_user_id": "U701"},
            "status": "success",
        }])
        self.assertTrue(payload["requires_human_review"])
        self.assertEqual(self.client.get("/api/day3/reviews").json(), before)
        self.assertEqual(hashlib.sha256(PAPER.read_bytes()).hexdigest(), paper_hash)

        with patch.dict(os.environ, environment, clear=False), patch(
            "app.agent.AsyncOpenAI", return_value=self.agent_client("CHG-2608-023", "U601")
        ):
            denied = self.client.post(
                "/api/day2/agent-preview/CHG-2608-023",
                json={"requester_user_id": "U601"},
            )
        self.assertEqual(denied.status_code, 403)

    def test_agent_preview_stops_safely_without_api_settings(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch("app.agent.load_dotenv"):
            response = self.client.post(
                "/api/day2/agent-preview/CHG-2608-023",
                json={"requester_user_id": "U701"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Agent 실행에 필요한 API 설정이 없습니다.")

    def test_agent_settings_load_workspace_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".env").write_text("OPENAI_API_KEY=test-key\nOPENAI_MODEL=test-model\n", encoding="utf-8")
            with patch("app.agent.ROOT", root), patch.dict(os.environ, {}, clear=True):
                self.assertEqual(load_agent_settings(), ("test-key", "test-model", None))

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

        new_paper = json.loads(PAPER.read_text(encoding="utf-8"))
        new_paper["generated_at"] = "2026-08-14 09:00:00"
        self.assertEqual(day3_ready_payload(new_paper, review_events())["summary"]["reviewed_count"], 0)


if __name__ == "__main__":
    unittest.main()
