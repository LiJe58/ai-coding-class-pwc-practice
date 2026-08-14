import hashlib
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[2]


class PopulationCheckpointTest(unittest.TestCase):
    def test_population_and_input_error_contract(self) -> None:
        payload = TestClient(app).get("/api/control-test").json()
        self.assertEqual(payload["summary"], {"population_count": 30, "valid_count": 29, "input_error_count": 1})
        self.assertEqual((payload["first_change_id"], payload["last_change_id"]), ("CHG-2608-001", "CHG-2608-030"))
        self.assertEqual(payload["input_errors"][0]["change_id"], "CHG-2608-030")
        source = ROOT / "input" / "day-1" / "vendor_changes.csv"
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), "bf63d81e2aef1fcf1e0452915a3cc5b162f1f95a419ff2249e535b16236ba88f")


if __name__ == "__main__":
    unittest.main()
