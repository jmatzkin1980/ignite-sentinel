"""IMP-312: the same situation exits with the same code on every command.

`sentinel/errors.py` defines the codes: 3 is invalid input (a missing file, a refused
payload), 4 is a gate refusal (a prerequisite, the project's health or its phase).
Before this item a missing `--source` file and `/view` of an artifact not generated
yet ended with exit 1 and a traceback, and several prerequisite refusals used 3.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_cli, run_ok  # noqa: E402

PROJECT = "EXITS"

RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads.
"""


class ExitCodeMatrixTests(SnapshotWorkspaceCase):
    """A v2 project right after /ingest: no brief, specs, backlog, series or prototype inventory."""

    @classmethod
    def build_workspace(cls) -> None:
        root = Path.cwd()
        (root / "raw.md").write_text(RAW, encoding="utf-8")
        (root / "payload.json").write_text("{}", encoding="utf-8")
        run_ok(["init", PROJECT])
        run_ok(["ingest", PROJECT, "--source", str(root / "raw.md")])

    def code(self, *argv: str) -> int:
        return run_cli(list(argv))[0]

    def test_a_missing_source_file_is_invalid_input(self) -> None:
        for argv in (["ingest", PROJECT, "--source", "no/such/file.md"],
                     ["resolve-gaps", PROJECT, "--source", "missing.md"],
                     ["assume", PROJECT, "--source", "missing.json"]):
            with self.subTest(command=argv[0]):
                code, out = run_cli(argv)
                self.assertEqual(code, 3)
                self.assertNotIn("Traceback", out)

    def test_prerequisites_are_gate_refusals(self) -> None:
        payload = str(self.temp / "payload.json")
        cases = {
            "view an artifact not generated yet": ["view", PROJECT, "--artifact", "backlog"],
            "compose before /specs": ["compose", PROJECT, "--source", payload],
            "refine before /backlog": ["refine-backlog", PROJECT, "--source", payload],
            "feedback before /backlog": ["implementation-feedback", PROJECT, "--source", payload],
            "split --assess before a brief": ["split", PROJECT, "--assess"],
            "split --confirm before a proposal": ["split", PROJECT, "--confirm", "--ba", "Ana", "--tech", "Team"],
            "--release before a series": ["status", PROJECT, "--release", "r1"],
            "prototype --manual before an inventory": ["prototype", PROJECT, "--manual", "--source", payload],
            "prototype --trace before a brief": ["prototype", PROJECT, "--trace", "--source", payload],
            "scrutinize --mode anchors before a brief": ["scrutinize", PROJECT, "--source", payload, "--mode", "anchors"],
            "self-review --sufficiency before a brief": ["self-review", PROJECT, "--source", payload, "--sufficiency"],
        }
        for label, argv in cases.items():
            with self.subTest(label):
                self.assertEqual(self.code(*argv), 4)

    def test_assume_before_ingest_is_a_gate_refusal(self) -> None:
        run_ok(["init", "EMPTY"])
        self.assertEqual(self.code("assume", "EMPTY", "--source", str(self.temp / "payload.json")), 4)

    def test_a_refused_payload_stays_invalid_input(self) -> None:
        self.assertEqual(self.code("assume", PROJECT, "--source", str(self.temp / "payload.json")), 3)


if __name__ == "__main__":
    unittest.main()
