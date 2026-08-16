import sqlite3
import unittest
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import DB_PATH, app


ROOT = Path(__file__).resolve().parents[2]


class Day1CheckpointTest(unittest.TestCase):
    def setUp(self) -> None:
        DB_PATH.unlink(missing_ok=True)

    def tearDown(self) -> None:
        DB_PATH.unlink(missing_ok=True)

    def test_api_ui_and_sqlite_share_the_day1_contract(self) -> None:
        payload = TestClient(app).post("/api/control-test/run").json()
        self.assertEqual(list(payload["summary"].values()), [30, 29, 21, 8, 1])
        self.assertEqual([row["change_id"] for row in payload["exceptions"]], [f"CHG-2608-{index:03d}" for index in range(22, 30)])
        case_23 = next(row for row in payload["exceptions"] if row["change_id"] == "CHG-2608-023")
        self.assertEqual([item["result"] for item in case_23["rules"]], ["pass", "fail", "not_applicable", "not_applicable"])
        with closing(sqlite3.connect(DB_PATH)) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM population_results WHERE status='review'").fetchone()[0], 8)
        frontend = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
        for contract in ("/api/control-test/run", "다시 시도", "API 오류"):
            self.assertIn(contract, frontend)


if __name__ == "__main__":
    unittest.main()
