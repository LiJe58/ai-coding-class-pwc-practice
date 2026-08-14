import csv
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[2]


class StarterCheckpointTest(unittest.TestCase):
    def test_health_inputs_and_day_features_absent(self) -> None:
        client = TestClient(app)
        self.assertEqual(client.get("/api/health").json()["status"], "ready")
        self.assertEqual(client.get("/api/control-test").status_code, 404)
        csvs = sorted((ROOT / "input" / "day-1").glob("*.csv"))
        self.assertEqual(len(csvs), 6)
        with (ROOT / "input" / "day-1" / "vendor_changes.csv").open(encoding="utf-8-sig", newline="") as file:
            self.assertEqual(len(list(csv.DictReader(file))), 30)


if __name__ == "__main__":
    unittest.main()
