import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[2]


class PopulationCheckpointTest(unittest.TestCase):
    def test_population_contract(self) -> None:
        payload = TestClient(app).get("/api/control-test").json()
        self.assertEqual(payload["summary"], {"population_count": 30})
        self.assertEqual((payload["first_change_id"], payload["last_change_id"]), ("CHG-2608-001", "CHG-2608-030"))
        self.assertNotIn("input_errors", payload)
        frontend = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
        self.assertIn("app-shell", frontend)
        self.assertIn("/api/control-test", frontend)
        self.assertNotIn("/api/control-test/run", frontend)


if __name__ == "__main__":
    unittest.main()
