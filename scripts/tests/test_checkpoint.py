import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "checkpoint.py"
SPEC = importlib.util.spec_from_file_location("checkpoint", MODULE_PATH)
checkpoint = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(checkpoint)


class CheckpointToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        source = self.repo / "student" / "00-starter"
        (source / ".claude").mkdir(parents=True)
        (source / ".claude" / "marker").write_text("hidden", encoding="utf-8")
        (source / "backend" / "data").mkdir(parents=True)
        (source / "backend" / "data" / "runtime.sqlite3").write_text("x", encoding="utf-8")
        self.workspace = self.repo / "practice" / "workspace"
        (self.workspace / ".venv").mkdir(parents=True)
        (self.workspace / ".venv" / "keep").write_text("yes", encoding="utf-8")
        self.patches = patch.multiple(checkpoint, REPO=self.repo, WORKSPACE=self.workspace)
        self.patches.start()

    def tearDown(self) -> None:
        self.patches.stop()
        self.temporary.cleanup()

    def test_reset_copies_hidden_files_preserves_environment_and_drops_runtime(self) -> None:
        checkpoint.reset("student/00-starter")
        self.assertTrue((self.workspace / ".claude" / "marker").is_file())
        self.assertTrue((self.workspace / ".venv" / "keep").is_file())
        self.assertFalse((self.workspace / "backend" / "data" / "runtime.sqlite3").exists())

    def test_promote_refuses_existing_target_and_outside_paths(self) -> None:
        with self.assertRaises(ValueError):
            checkpoint.promote("student/00-starter")
        with self.assertRaises(ValueError):
            checkpoint.checkpoint_path("../outside", must_exist=False)


if __name__ == "__main__":
    unittest.main()
