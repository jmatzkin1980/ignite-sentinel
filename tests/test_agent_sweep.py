"""IMP-271: the sweep protocol for agentic channels, and F7 (BA disposition)."""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from sentinel.agent_sweep import AGENTIC_ORIGINS, channel_dispositions
from sentinel.cli import main
from sentinel.discovery import AnnotationError, validate_agent_gaps
from sentinel.maturity import maturation_telemetry

ROOT = Path(__file__).resolve().parents[1]
RAW = (
    "# Reporting Portal\n\n"
    "We need a reporting portal for the operations team. The objective is to "
    "reduce manual work. Data is stored in the legacy billing system.\n"
)


def _gap(**over):
    base = {
        "id": "GAP-DATA-RETENTION",
        "lens": "technical",
        "severity": "high",
        "question": "How long must report data be retained and where is the source of truth?",
        "evidence": "legacy billing system",
    }
    base.update(over)
    return base


class ProtocolValidationTests(unittest.TestCase):
    def test_well_formed_payload_passes(self) -> None:
        payload = {
            "gaps": [_gap(blocks=True)],
            "absent": ["AUSENTE: retention period en 00_raw/portal.md", "ABSENT: report owners in 00_raw/portal.md"],
            "untouched": ["The billing system migration: out of scope for this pass."],
        }
        self.assertEqual(len(validate_agent_gaps(payload, RAW)), 1)

    def test_malformed_absent_is_rejected(self) -> None:
        for entry in ("retention period is missing", "AUSENTE: retention period", "AUSENTE:  en 00_raw/x.md",
                      "AUSENTE: ab en 00_raw/x.md", 42):
            with self.subTest(entry=entry), self.assertRaises(AnnotationError):
                validate_agent_gaps({"gaps": [_gap()], "absent": [entry]}, RAW)
        with self.assertRaisesRegex(AnnotationError, "must be a list"):
            validate_agent_gaps({"gaps": [_gap()], "absent": "AUSENTE: x en y"}, RAW)

    def test_an_absence_is_re_verified(self) -> None:
        with self.assertRaisesRegex(AnnotationError, "reported absent but it is in the grounding text"):
            validate_agent_gaps({"gaps": [_gap()], "absent": ["AUSENTE: \"operations team\" en 00_raw/portal.md"]}, RAW)

    def test_finding_without_re_verifiable_citation_is_still_rejected(self) -> None:
        with self.assertRaises(AnnotationError):
            validate_agent_gaps({"gaps": [_gap(evidence="the portal must export to PDF")]}, RAW)

    def test_agent_written_figures_are_rejected(self) -> None:
        for key in ("counts", "totals", "summary", "figures", "stats", "metrics"):
            with self.subTest(key=key), self.assertRaisesRegex(AnnotationError, "injected by the runtime"):
                validate_agent_gaps({"gaps": [_gap()], key: {"gaps": 1}}, RAW)

    def test_untouched_and_blocks_types(self) -> None:
        with self.assertRaises(AnnotationError):
            validate_agent_gaps({"gaps": [_gap()], "untouched": ["ok", ""]}, RAW)
        with self.assertRaises(AnnotationError):
            validate_agent_gaps({"gaps": [_gap()], "untouched": "just a string"}, RAW)
        with self.assertRaisesRegex(AnnotationError, "'blocks' must be true or false"):
            validate_agent_gaps({"gaps": [_gap(blocks="yes")]}, RAW)

    def test_every_channel_shares_the_check(self) -> None:
        for origin in AGENTIC_ORIGINS:
            with self.subTest(origin=origin), self.assertRaises(AnnotationError):
                validate_agent_gaps({"gaps": [_gap()], "absent": ["missing stuff"]}, RAW, origin=origin)


class FlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        raw = self.temp / "portal.md"
        raw.write_text(RAW, encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["init", "SWP", "--brief-version", "1"]), 0)
            self.assertEqual(main(["ingest", "SWP", "--source", str(raw)]), 0)
        self.ws = self.temp / "workspaces" / "SWP"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _annotate(self, payload: dict) -> int:
        source = self.temp / "annotation.json"
        source.write_text(json.dumps(payload), encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            return main(["annotate", "SWP", "--source", str(source)])

    def _run(self, argv: list[str]) -> tuple[int, dict]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(argv)
        text = out.getvalue()
        return code, (json.loads(text[text.index("{"):]) if "{" in text else {})

    def test_runtime_writes_the_figures_in_the_sweep_log(self) -> None:
        payload = {
            "gaps": [_gap(blocks=True), _gap(id="GAP-REPORT-OWNER", evidence="operations team", blocks=False)],
            "absent": ["AUSENTE: retention period en 00_raw/portal.md"],
            "untouched": ["The billing migration: raised elsewhere."],
        }
        self.assertEqual(self._annotate(payload), 0)
        log = (self.ws / "01_discovery" / "agent_sweep_log.md").read_text(encoding="utf-8")
        self.assertIn("## annotate", log)
        self.assertIn("Findings accepted (runtime count): 2", log)
        self.assertIn("Marked as blocking by the agent: 1 (GAP-DATA-RETENTION)", log)
        self.assertIn("Absences re-verified: 1", log)
        self.assertIn("Seen and NOT touched: 1", log)

    def test_rejected_payload_merges_nothing(self) -> None:
        before = (self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        self.assertEqual(self._annotate({"gaps": [_gap()], "absent": ["nothing here"]}), 3)  # IMP-302: invalid input
        self.assertEqual((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"), before)
        self.assertFalse((self.ws / "01_discovery" / "agent_sweep_log.md").exists())

    def test_f7_dispositions_and_false_alarm_rate(self) -> None:
        # IMP-257: distinct questions, or the topic dedup merges them into one row
        self.assertEqual(self._annotate({"gaps": [
            _gap(),
            _gap(id="GAP-REPORT-OWNER", evidence="operations team", lens="business",
                 question="Which team owns the monthly report once it ships?"),
            _gap(id="GAP-OBJECTIVE-METRIC", evidence="reduce manual work", lens="product",
                 question="By how many hours a week should manual work go down?"),
        ]}), 0)
        code, result = self._run(["gaps", "SWP", "--id", "GAP-DATA-RETENTION", "--disposition", "accepted"])
        self.assertEqual(code, 0)
        self.assertEqual(result["disposition"], "accepted")
        self.assertEqual(self._run(["gaps", "SWP", "--id", "GAP-REPORT-OWNER", "--disposition", "rejected"])[0], 3)  # no reason  # IMP-302: invalid input
        self.assertEqual(self._run(["gaps", "SWP", "--id", "GAP-REPORT-OWNER", "--disposition", "rejected",
                                    "--reason", "the team is named in the kickoff"])[0], 0)
        telemetry = maturation_telemetry("SWP")["agent_channel_dispositions"]
        self.assertEqual(telemetry["agent"], {"raised": 3, "accepted": 1, "rejected": 1, "irrelevant": 0,
                                              "undisposed": 1, "false_alarm_rate": 0.5})

    def test_disposition_only_on_agentic_gaps(self) -> None:
        checklist = next(row for row in (self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8").splitlines()
                         if row.startswith("| GAP-"))
        gap_id = checklist.split("|")[1].strip()
        self.assertEqual(self._run(["gaps", "SWP", "--id", gap_id, "--disposition", "accepted"])[0], 3)  # IMP-302: invalid input
        self.assertEqual(self._run(["gaps", "SWP", "--disposition", "accepted"])[0], 3)  # needs --id  # IMP-302: invalid input
        self.assertEqual(channel_dispositions(self.ws, []), {})

    def test_protocol_guide_is_shipped_and_cited(self) -> None:
        guide = ROOT / "sentinel" / "templates" / "agent_sweep_protocol.md"
        self.assertTrue(guide.exists())
        text = guide.read_text(encoding="utf-8")
        for rule in ("AUSENTE:", "untouched", "blocks", "runtime", "IMP-286", "/validate"):
            self.assertIn(rule, text)
        for skill in ("sentinel-annotate", "sentinel-challenge", "sentinel-scrutiny", "sentinel-self-review"):
            for root in (".codex", ".claude", ".agents"):
                body = (ROOT / root / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn("sentinel/templates/agent_sweep_protocol.md", body, f"{root}/{skill}")


if __name__ == "__main__":
    unittest.main()
