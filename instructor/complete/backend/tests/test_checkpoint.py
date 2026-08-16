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
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import DAY3_DB_PATH, app, day3_ready_payload, review_events
from app.agent import load_agent_settings


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

    def test_all_read_and_control_test_apis_share_the_course_contract(self) -> None:
        self.assertEqual(self.client.get("/api/health").json()["status"], "ready")
        day1 = self.client.get("/api/control-test").json()
        self.assertEqual(
            [day1["summary"][key] for key in ("population_count", "valid_count", "normal_count", "review_count", "input_error_count")],
            [30, 29, 21, 8, 1],
        )
        persisted = self.client.post("/api/control-test/run")
        self.assertEqual(persisted.status_code, 200)
        self.assertEqual(persisted.json()["persistence"]["valid_population_rows"], 29)
        day2 = self.client.get("/api/day2/working-paper").json()
        self.assertEqual((day2["status"], day2["validation"]["valid"], len(day2["working_paper"]["samples"])), ("ready", True, 12))
        day3 = self.client.get("/api/day3/reviews").json()
        self.assertEqual((day3["status"], day3["total_count"], day3["pending_count"]), ("ready", 12, 12))
        runs = self.client.get(
            "/api/day2/agent-runs",
            params={"change_id": "CHG-2608-023", "requester_user_id": "U701"},
        )
        self.assertEqual(runs.json(), {"items": []})
        self.assertEqual(self.client.post(
            "/api/day2/agent-preview/not-a-sample", json={"requester_user_id": "U701"}
        ).status_code, 404)

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
        self.assertTrue(payload["run_id"])
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

        history = self.client.get(
            "/api/day2/agent-runs",
            params={"change_id": "CHG-2608-023", "requester_user_id": "U701"},
        )
        self.assertEqual(history.status_code, 200)
        items = history.json()["items"]
        self.assertEqual([item["status"] for item in items], ["permission_denied", "success"])
        self.assertEqual(items[0]["model_status"], "not_called")
        self.assertEqual(items[0]["tool_status"], "not_called")
        self.assertNotIn("api_key", json.dumps(items).lower())
        self.assertEqual(
            self.client.get(
                "/api/day2/agent-runs",
                params={"change_id": "CHG-2608-023", "requester_user_id": "U601"},
            ).status_code,
            403,
        )

    def test_agent_preview_stops_safely_without_api_settings(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch("app.agent.load_dotenv"):
            response = self.client.post(
                "/api/day2/agent-preview/CHG-2608-023",
                json={"requester_user_id": "U701"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Agent 실행에 필요한 API 설정이 없습니다.")
        item = self.client.get(
            "/api/day2/agent-runs",
            params={"change_id": "CHG-2608-023", "requester_user_id": "U701"},
        ).json()["items"][0]
        self.assertEqual(item["status"], "config_error")
        self.assertEqual(item["configuration_status"], "missing")

    def test_agent_run_history_accumulates_and_separates_model_failure(self) -> None:
        environment = {"OPENAI_API_KEY": uuid.uuid4().hex, "OPENAI_MODEL": "test-model"}
        with patch.dict(os.environ, environment, clear=False):
            for _ in range(2):
                with patch("app.agent.AsyncOpenAI", return_value=self.agent_client("CHG-2608-023", "U701")):
                    self.assertEqual(self.client.post(
                        "/api/day2/agent-preview/CHG-2608-023",
                        json={"requester_user_id": "U701"},
                    ).status_code, 200)

        failing_client = SimpleNamespace(responses=SimpleNamespace())
        failing_client.responses.create = AsyncMock(side_effect=RuntimeError("secret upstream text"))
        with patch.dict(os.environ, environment, clear=False), patch(
            "app.agent.AsyncOpenAI", return_value=failing_client
        ):
            failed = self.client.post(
                "/api/day2/agent-preview/CHG-2608-023",
                json={"requester_user_id": "U701"},
            )
        self.assertEqual(failed.status_code, 502)

        with patch.dict(os.environ, environment, clear=False), patch(
            "app.agent.AsyncOpenAI", return_value=self.agent_client("CHG-2608-023", "U701")
        ), patch("app.agent.fetch_case_evidence", AsyncMock(side_effect=RuntimeError("raw tool detail"))):
            tool_failed = self.client.post(
                "/api/day2/agent-preview/CHG-2608-023",
                json={"requester_user_id": "U701"},
            )
        self.assertEqual(tool_failed.status_code, 502)

        items = self.client.get(
            "/api/day2/agent-runs",
            params={"change_id": "CHG-2608-023", "requester_user_id": "U701"},
        ).json()["items"]
        self.assertEqual([item["status"] for item in items], ["tool_error", "model_error", "success", "success"])
        self.assertEqual(items[0]["error_code"], "tool_error")
        self.assertEqual(items[1]["error_code"], "model_error")
        self.assertNotIn("secret upstream text", json.dumps(items))
        self.assertNotIn("raw tool detail", json.dumps(items))

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
