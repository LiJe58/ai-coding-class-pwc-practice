import unittest
from pathlib import Path

from mcp_server import get_case_evidence

ROOT = Path(__file__).resolve().parents[2]


class EvidenceCheckpointTest(unittest.TestCase):
    def test_permissions_and_source_ids(self) -> None:
        allowed = get_case_evidence("CHG-2608-023", "U701")
        denied = get_case_evidence("CHG-2608-023", "U601")
        missing = get_case_evidence("CHG-0000-000", "U701")

        self.assertEqual(allowed["status"], "success")
        self.assertEqual(denied["status"], "permission_denied")
        self.assertEqual(missing["status"], "invalid_request")
        self.assertEqual(allowed["source_ids"]["approval_ids"], [])
        self.assertEqual(
            allowed["source_ids"]["evidence_ids"],
            [row["evidence_id"] for row in allowed["evidence"]["evidence_register"]],
        )
        self.assertEqual(
            allowed["source_ids"]["payment_ids"],
            [row["payment_id"] for row in allowed["evidence"]["payment_requests"]],
        )
        frontend = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
        self.assertIn("증적 참조 준비", frontend)


if __name__ == "__main__":
    unittest.main()
