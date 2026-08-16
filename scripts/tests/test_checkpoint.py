import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "checkpoint.py"
SPEC = importlib.util.spec_from_file_location("checkpoint", MODULE_PATH)
checkpoint = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(checkpoint)


EXPECTED_CHECKPOINTS = [
    "student/00-starter",
    "student/01-population-ready",
    "student/02-controls-ready",
    "student/03-controls-persisted",
    "student/04-day1-ui-ready",
    "student/05-day1-complete",
    "student/06-mcp-connected",
    "student/07-samples-ready",
    "student/08-evidence-ready",
    "student/09-evidence-skill-ready",
    "student/10-working-paper-api-ready",
    "student/11-day2-complete",
    "student/12-review-storage-ready",
    "student/13-review-ui-ready",
    "student/14-agent-history-ready",
    "instructor/complete",
]
WORKING_PAPER_CHECKPOINTS = EXPECTED_CHECKPOINTS[9:]
REVIEW_CHECKPOINTS = EXPECTED_CHECKPOINTS[12:]


class CheckpointToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        source = self.repo / "student" / "00-starter"
        (source / ".claude").mkdir(parents=True)
        (source / ".claude" / "marker").write_text("hidden", encoding="utf-8")
        instructor = self.repo / "instructor" / "complete"
        instructor.mkdir(parents=True)
        (instructor / ".env.example").write_text("OPENAI_API_KEY=\nOPENAI_MODEL=gpt-5.6-terra\n", encoding="utf-8")
        (source / "backend" / "data").mkdir(parents=True)
        (source / "backend" / "data" / "runtime.sqlite3").write_text("x", encoding="utf-8")
        (source / "output" / "day-2").mkdir(parents=True)
        (source / "output" / "day-2" / "working-paper.json").write_text("{}", encoding="utf-8")
        (source / "output" / "temporary.json").write_text("runtime", encoding="utf-8")
        scenario = self.repo / "assets" / "scenario"
        scenario.mkdir(parents=True)
        (scenario / "control-card.md").write_text("# controls", encoding="utf-8")
        (scenario / "case-matrix.xlsx").write_bytes(b"matrix")
        self.workspace = self.repo / "practice" / "workspace"
        (self.workspace / ".venv").mkdir(parents=True)
        (self.workspace / ".venv" / "keep").write_text("yes", encoding="utf-8")
        (self.workspace / "frontend" / "node_modules").mkdir(parents=True)
        (self.workspace / "frontend" / "node_modules" / "keep").write_text("yes", encoding="utf-8")
        (self.workspace / ".env").write_text("OPENAI_API_KEY=keep-me\n", encoding="utf-8")
        self.patches = patch.multiple(checkpoint, REPO=self.repo, WORKSPACE=self.workspace)
        self.patches.start()

    def tearDown(self) -> None:
        self.patches.stop()
        self.temporary.cleanup()

    def test_reset_copies_hidden_files_preserves_environment_and_drops_runtime(self) -> None:
        checkpoint.reset("student/00-starter")
        self.assertTrue((self.workspace / ".claude" / "marker").is_file())
        self.assertTrue((self.workspace / ".venv" / "keep").is_file())
        self.assertTrue((self.workspace / "frontend" / "node_modules" / "keep").is_file())
        self.assertEqual((self.workspace / ".env").read_text(encoding="utf-8"), "OPENAI_API_KEY=keep-me\n")
        self.assertTrue((self.workspace / ".env.example").is_file())
        self.assertFalse((self.workspace / "backend" / "data" / "runtime.sqlite3").exists())
        self.assertFalse((self.workspace / "backend" / "data").exists())
        self.assertTrue((self.workspace / "output" / "day-2" / "working-paper.json").is_file())
        self.assertFalse((self.workspace / "output" / "temporary.json").exists())
        self.assertTrue((self.workspace / "assets" / "scenario" / "control-card.md").is_file())
        self.assertTrue((self.workspace / "assets" / "scenario" / "case-matrix.xlsx").is_file())

    def test_promote_refuses_existing_target_and_outside_paths(self) -> None:
        with self.assertRaises(ValueError):
            checkpoint.promote("student/00-starter")
        with self.assertRaises(ValueError):
            checkpoint.checkpoint_path("../outside", must_exist=False)

    def test_promote_copies_hidden_and_reference_file_but_not_runtime(self) -> None:
        checkpoint.reset("student/00-starter")
        (self.workspace / "runtime.log").write_text("ignored", encoding="utf-8")
        checkpoint.promote("student/01-new")
        target = self.repo / "student" / "01-new"
        self.assertTrue((target / ".claude" / "marker").is_file())
        self.assertTrue((target / "output" / "day-2" / "working-paper.json").is_file())
        self.assertFalse((target / ".venv").exists())
        self.assertFalse((target / ".env").exists())
        self.assertFalse((target / "runtime.log").exists())
        self.assertFalse((target / "assets").exists())


class CheckpointIndexTest(unittest.TestCase):
    def test_manifest_and_stage_metadata_use_the_complete_ordered_index(self) -> None:
        self.assertEqual(checkpoint.manifest()["checkpoints"], EXPECTED_CHECKPOINTS)
        for name in EXPECTED_CHECKPOINTS:
            root = checkpoint.checkpoint_path(name, must_exist=True)
            metadata = json.loads((root / ".course-workspace.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["stage"], name.split("/", 1)[1] if name.startswith("student/") else "complete")


class PublishedContentContractTest(unittest.TestCase):
    def test_agent_drafts_are_case_specific_and_do_not_expose_course_stages(self) -> None:
        for name in WORKING_PAPER_CHECKPOINTS:
            root = checkpoint.checkpoint_path(name, must_exist=True)
            paper = json.loads((root / "output" / "day-2" / "working-paper.json").read_text(encoding="utf-8"))
            procedures = []
            assessments = []
            for sample in paper["samples"]:
                draft = sample["agent_draft"]
                text = json.dumps(draft, ensure_ascii=False)
                self.assertNotIn("Day 1", text, name)
                self.assertNotIn("?", text, name)
                self.assertIn(sample["change_id"], draft["procedure"], name)
                self.assertIn(sample["vendor_name"], draft["procedure"], name)
                self.assertIn(sample["vendor_name"], draft["draft_assessment"], name)
                self.assertTrue(any(source_id in draft["procedure"] for ids in sample["source_ids"].values() for source_id in ids), name)
                procedures.append(draft["procedure"])
                assessments.append(draft["draft_assessment"])
            self.assertEqual(len(set(procedures)), 12, name)
            self.assertEqual(len(set(assessments)), 12, name)

            skill = (root / ".claude" / "skills" / "control-test" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("단계명인 `Day 1`", skill, name)
            self.assertIn("사례별로 구체적으로", skill, name)

    def test_review_permission_errors_name_the_user_and_recovery_action(self) -> None:
        expected = "U701 · 내부통제 검토자를 선택해 주세요."
        for name in REVIEW_CHECKPOINTS:
            root = checkpoint.checkpoint_path(name, must_exist=True)
            backend = (root / "backend" / "app" / "main.py").read_text(encoding="utf-8")
            self.assertIn("검토자 {user_id}에게 CONTROL_REVIEW 권한이 없습니다.", backend, name)
            self.assertIn(expected, backend, name)

        frontend = (checkpoint.checkpoint_path("student/13-review-ui-ready", must_exist=True) / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
        self.assertIn("await response.json()", frontend)
        self.assertIn("권한 거부", frontend)

    def test_agent_run_history_renders_markdown(self) -> None:
        expected = '<div className="agent-review-markdown"><ReactMarkdown>{run.answer ?? run.error_message}</ReactMarkdown></div>'
        for name in ("student/14-agent-history-ready", "instructor/complete"):
            root = checkpoint.checkpoint_path(name, must_exist=True)
            frontend = (root / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
            styles = (root / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")
            self.assertIn(expected, frontend, name)
            self.assertNotIn("<p>{run.answer ?? run.error_message}</p>", frontend, name)
            self.assertIn(".timeline .agent-review-markdown { width: 100%; min-width: 0;", styles, name)
            self.assertIn(".timeline > li {", styles, name)
            self.assertNotIn(".timeline li {", styles, name)


if __name__ == "__main__":
    unittest.main()
