from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main

RAW = """# Operations Risk Dashboard

Objective: operations leads review risk queues before the daily meeting.
Users: operations leads.
In scope: read-only dashboard for open queues.
"""

EARS = "When queue metrics are available, the system shall display open risk queues."


class GateOverrideDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        raw = self.temp / "raw.md"
        raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "OVERRIDE"]), 0)
        self.assertEqual(main(["ingest", "OVERRIDE", "--source", str(raw)]), 0)
        answers = self.temp / "answers.md"
        answers.write_text(
            "### GAP-ACCEPTANCE\n"
            f"- Answer: {EARS}\n"
            "- Owner / source: Client workshop\n"
            "- Evidence reference: Synthetic EARS response\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["resolve-gaps", "OVERRIDE", "--source", str(answers)]), 0)
        self.assertEqual(main(["brief", "OVERRIDE"]), 0)
        self.assertEqual(main(["specs", "OVERRIDE"]), 0)
        self.assertEqual(main(["backlog", "OVERRIDE"]), 0)
        self.ws = self.temp / "workspaces" / "OVERRIDE"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_backlog_status_without_override_creates_no_gate_decision_register(self) -> None:
        self.assertEqual(main(["backlog-status", "OVERRIDE"]), 0)
        self.assertFalse((self.ws / "06_traceability" / "gate_overrides").exists())

    def test_backlog_status_override_records_rationale(self) -> None:
        quote = self.quoted_line(self.ws / "04_backlog" / "US-001.md", "queue")
        source = self.write_override(
            "DEC-BACKLOG-DOR-OVERRIDE",
            "Proceed with backlog review even though DoR blockers remain visible.",
            quote,
            stem="backlog-status-override",
        )
        self.assertEqual(main(["backlog-status", "OVERRIDE", "--override", str(source)]), 0)
        self.assert_gate_override("backlog-status", "DEC-BACKLOG-DOR-OVERRIDE")

    def test_quality_override_records_rationale_without_changing_command_success(self) -> None:
        story_path = self.ws / "04_backlog" / "US-001.md"
        story_text = story_path.read_text(encoding="utf-8")
        story_path.write_text(
            "\n".join(line for line in story_text.splitlines() if not line.startswith("| AC-")),
            encoding="utf-8",
        )
        quote = self.quoted_line(self.ws / "02_requirements" / "project-brief.md", "queue")
        source = self.write_override(
            "DEC-QUALITY-UNDER-THRESHOLD",
            "Proceed with implementation planning while the story quality audit remains below PASS.",
            quote,
            stem="quality-override",
        )
        self.assertEqual(main(["quality", "OVERRIDE", "--override", str(source)]), 0)
        self.assert_gate_override("quality", "DEC-QUALITY-UNDER-THRESHOLD")

    def test_validate_override_records_rationale_but_keeps_invalid_exit_code(self) -> None:
        (self.ws / "sentinel.config.yaml").unlink()
        quote = self.quoted_line(self.ws / "02_requirements" / "project-brief.md", "queue")
        source = self.write_override(
            "DEC-VALIDATE-CONFIG-OVERRIDE",
            "Proceed with the structural review while configuration remediation is tracked separately.",
            quote,
            stem="validate-override",
        )
        self.assertEqual(main(["validate", "OVERRIDE", "--override", str(source)]), 1)
        self.assert_gate_override("validate", "DEC-VALIDATE-CONFIG-OVERRIDE")

    def write_override(self, decision_id: str, decision: str, evidence: str, *, stem: str) -> Path:
        path = self.temp / f"{stem}.json"
        path.write_text(
            json.dumps(
                {
                    "decisions": [
                        {
                            "id": decision_id,
                            "title": decision_id.replace("DEC-", "").replace("-", " ").title(),
                            "lens": "product",
                            "risk": "high",
                            "reversibility": "hard-to-reverse",
                            "decision": decision,
                            "evidence": evidence,
                            "consequence": "Downstream agents must keep the gate failure visible while the team proceeds.",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return path

    def assert_gate_override(self, gate: str, decision_id: str) -> None:
        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        entries = state.get("gate_override_decisions", [])
        self.assertTrue(entries)
        self.assertEqual(entries[-1]["gate"], gate)
        register = (self.ws / "06_traceability" / "gate_overrides" / "decision_register.md").read_text(encoding="utf-8")
        report_dir = self.ws / "06_traceability" / "gate_overrides"
        reports = sorted(report_dir.glob(f"{gate}-override-report*.md"))
        self.assertTrue(reports)
        self.assertIn(decision_id, register)
        self.assertIn(f"Gate: `/{gate}`", reports[-1].read_text(encoding="utf-8"))

    def quoted_line(self, path: Path, token: str) -> str:
        for line in path.read_text(encoding="utf-8").splitlines():
            if token.lower() in line.lower():
                return line.strip()
        self.fail(f"Could not find token {token!r} in {path}")


if __name__ == "__main__":
    unittest.main()
