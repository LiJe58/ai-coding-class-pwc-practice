import unittest
from pathlib import Path

from app.main import DAY2_SAMPLE_IDS
from mcp_server import get_case_evidence, select_day2_samples


ROOT = Path(__file__).resolve().parents[2]


class EvidenceSkillCheckpointTest(unittest.TestCase):
    def test_fixed_samples_permissions_citations_and_skill_contract(self) -> None:
        samples = select_day2_samples()
        self.assertEqual([row["change_id"] for row in samples["rows"]], DAY2_SAMPLE_IDS)
        self.assertEqual([row["status"] for row in samples["rows"]].count("normal"), 4)
        self.assertEqual([row["status"] for row in samples["rows"]].count("review"), 8)
        self.assertNotIn("CHG-2608-030", DAY2_SAMPLE_IDS)

        allowed = get_case_evidence("CHG-2608-023", "U701")
        denied = get_case_evidence("CHG-2608-023", "U601")
        self.assertEqual(allowed["status"], "success")
        self.assertEqual(denied["status"], "permission_denied")
        cited = allowed["source_ids"]
        actual = allowed["evidence"]
        self.assertEqual(cited["approval_ids"], [row["approval_id"] for row in actual["approvals"]])
        self.assertEqual(cited["evidence_ids"], [row["evidence_id"] for row in actual["evidence_register"]])
        self.assertEqual(cited["payment_ids"], [row["payment_id"] for row in actual["payment_requests"]])

        skill = (ROOT / ".claude" / "skills" / "control-test" / "SKILL.md").read_text(encoding="utf-8")
        for signature in (
            'get_control_population(status="all")',
            "select_day2_samples()",
            'get_case_evidence(change_id, requester_user_id="U701")',
        ):
            self.assertIn(signature, skill)


if __name__ == "__main__":
    unittest.main()
