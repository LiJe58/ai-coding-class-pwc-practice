import sqlite3
import unittest
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import DB_PATH, app

ROOT = Path(__file__).resolve().parents[2]


class ControlsCheckpointTest(unittest.TestCase):
    def setUp(self) -> None:
        DB_PATH.unlink(missing_ok=True)

    def tearDown(self) -> None:
        DB_PATH.unlink(missing_ok=True)

    def test_rules_and_duplicate_free_sqlite_persistence(self) -> None:
        client = TestClient(app)
        first = client.post("/api/control-test/run").json()
        second = client.post("/api/control-test/run").json()
        expected = {"population_count": 30, "valid_count": 29, "normal_count": 21, "review_count": 8, "input_error_count": 1}
        self.assertEqual(first["summary"], expected)
        self.assertEqual(second["summary"], expected)
        self.assertEqual([row["change_id"] for row in first["population"] if row["status"] == "normal"], [f"CHG-2608-{index:03d}" for index in range(1, 22)])
        self.assertEqual([row["change_id"] for row in first["exceptions"]], [f"CHG-2608-{index:03d}" for index in range(22, 30)])
        case_23 = next(row for row in first["population"] if row["change_id"] == "CHG-2608-023")
        self.assertEqual({item["rule_id"]: item["result"] for item in case_23["rules"]}, {"R-01": "pass", "R-02": "fail", "R-03": "not_applicable", "R-04": "not_applicable"})
        with closing(sqlite3.connect(DB_PATH)) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM population_results").fetchone()[0], 29)
            self.assertIsNone(connection.execute("SELECT 1 FROM population_results WHERE change_id='CHG-2608-030'").fetchone())
        frontend = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
        self.assertIn("/api/control-test/run", frontend)
        self.assertIn("persistence-card", frontend)


if __name__ == "__main__":
    unittest.main()
