"""IMP-406 (H27 inc 1) task 1: re-recording a cross-read retires the questions whose claims vanished."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_h26_cross_record import CID, PID, CrossCase, set_language  # noqa: E402

from sentinel.changes import list_changes  # noqa: E402
from sentinel.crosses import run_cross  # noqa: E402
from sentinel.crosses.record import RETIRE_NOTE, close_change_gap, record_cross  # noqa: E402

NOTE_ES = "afirmación retirada al re-registrar el cruce"
NOTE_EN = "claim withdrawn when the cross-read was re-recorded"
DROPPED_TAGS = ("- [SIN RESPALDO EN DISEÑO]", "- [DIVERGENCIA]")


class RetireCase(CrossCase):
    def write_without(self, prefixes: tuple[str, ...], translate: bool = False) -> Path:
        full = self.write("cruce_diseno.md")
        lines = full.read_text(encoding="utf-8").splitlines()
        kept: list[str] = []
        skipping = False
        for line in lines:
            if line.startswith("- ["):
                skipping = line.startswith(prefixes)
            if not skipping:
                kept.append(line)
        text = "\n".join(kept) + "\n"
        if translate:
            for es, en in (("RESPALDADO", "BACKED"), ("SOLO EN DISEÑO", "ONLY IN DESIGN")):
                text = text.replace(f"[{es}]", f"[{en}]")
        out = full.with_name("sin-" + full.name)
        out.write_text(text, encoding="utf-8")
        return out

    def first_gaps(self) -> dict[str, str]:
        first = record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        return {g[:8]: g for g in first["gaps"]}


class Retiring(RetireCase):
    def test_vanished_claims_are_retired(self):
        ids = self.first_gaps()
        result = record_cross(PID, CID, "diseno", self.write_without(DROPPED_TAGS))
        self.assertEqual(sorted(result["retired_gaps"]), sorted([ids["GAP-SRD-"], ids["GAP-DIS-"]]))
        gaps = self.gaps()
        for gap_id in result["retired_gaps"]:
            self.assertEqual(gaps[gap_id]["status"], "CLOSED")
            self.assertEqual(gaps[gap_id]["resolution_note"], NOTE_ES)
        self.assertEqual(list_changes(PID)[CID]["gap_counts"]["blocking_open"], 0)
        self.assertEqual(gaps[ids["GAP-SED-"]]["status"], "OPEN")

    def test_answered_question_is_not_touched(self):
        ids = self.first_gaps()
        sed = ids["GAP-SED-"]
        self.assertTrue(close_change_gap(PID, CID, sed, "respondida"))
        result = record_cross(PID, CID, "diseno", self.write_without(("- [SOLO EN DISEÑO]",)))
        self.assertEqual(result["retired_gaps"], [])
        self.assertEqual(self.gaps()[sed]["resolution_note"], "respondida")

    def test_claim_back_reopens(self):
        ids = self.first_gaps()
        dis = ids["GAP-DIS-"]
        record_cross(PID, CID, "diseno", self.write_without(("- [DIVERGENCIA]",)))
        self.assertEqual(self.gaps()[dis]["status"], "CLOSED")
        result = record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        self.assertEqual(result["reopened_gaps"], [dis])
        self.assertEqual(self.gaps()[dis]["status"], "OPEN")
        self.assertEqual(self.gaps()[dis].get("resolution_note", ""), "")

    def test_english_note_and_message(self):
        ids = self.first_gaps()
        set_language(PID, "en")
        path = self.write_without(DROPPED_TAGS, translate=True)
        result = run_cross(PID, CID, kind="diseno", claims=str(path))
        self.assertIn("question(s) withdrawn", result["message"])
        self.assertEqual(self.gaps()[ids["GAP-SRD-"]]["resolution_note"], NOTE_EN)
        self.assertEqual(RETIRE_NOTE["en"], NOTE_EN)


if __name__ == "__main__":
    unittest.main()
