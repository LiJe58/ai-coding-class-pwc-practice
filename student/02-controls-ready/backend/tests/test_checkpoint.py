import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[2]


class ControlsCheckpointTest(unittest.TestCase):
    def test_input_errors_and_control_results_are_separate(self) -> None:
        client = TestClient(app)
        result = client.get("/api/control-test").json()
        expected = {"population_count": 30, "valid_count": 29, "normal_count": 21, "review_count": 8, "input_error_count": 1}
        self.assertEqual(result["summary"], expected)
        self.assertEqual([row["change_id"] for row in result["exceptions"]], [f"CHG-2608-{index:03d}" for index in range(22, 30)])
        self.assertEqual([row["change_id"] for row in result["input_errors"]], ["CHG-2608-030"])
        case_23 = next(row for row in result["population"] if row["change_id"] == "CHG-2608-023")
        self.assertEqual({item["rule_id"]: item["result"] for item in case_23["rules"]}, {"R-01": "pass", "R-02": "fail", "R-03": "not_applicable", "R-04": "not_applicable"})
        frontend = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
        self.assertIn("metric-grid", frontend)
        self.assertIn("예외 검토", frontend)
        self.assertIn("입력 오류 행", frontend)
        self.assertNotIn("/api/control-test/run", frontend)


if __name__ == "__main__":
    unittest.main()
