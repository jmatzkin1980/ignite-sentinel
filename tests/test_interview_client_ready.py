"""IMP-344 / IMP-349: the interview export is the list of questions a BA can send to the client.

IMP-344: it leaves out the BA's own brief settings gap (its question is a CLI command), names
no internal improvement id, and every catalogue gap it shows asks a specific question.
IMP-349: it shows no lens or severity label, its follow-ups are plain questions built from the
matched text (never the BA's "Confirm `x` is in scope" options), every lens check has its own
catalogue question, and an answered copy fed to /resolve-gaps closes the answered gaps.
"""
import contextlib
import io
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

GENERIC = ("What confirmed information resolves this uncertainty?", "¿Qué información confirmada resuelve esta incertidumbre?")
PRD_GAPS = ("GAP-PRD-PERSONA-DETAIL", "GAP-PRD-FR-AC", "GAP-PRD-NFR-KPI", "GAP-PRD-DEPENDENCIES-ROADMAP")
# BA-facing wording that must never reach the client
INTERNAL = ("severity", "severidad", "lens", "lente", "Probing", "profundizacion", "Local citation", "Cita local",
            "Confirm `", "Confirmar que `", "context-only", "solo contexto", "answer the missing", "detalle faltante",
            "this gap", "este gap", "READ-ONLY", "/stakeholders", "respondent_profile", "IMP-")


def rows():
    gaps = [{"id": "GAP-BRIEF-PROFILE", "lens": "product", "severity": "critical", "status": "OPEN",
             "question": "Confirm the brief profile(s) and genesis: /brief PROJECT_ID --profile UI,REG --genesis greenfield"},
            {"id": "GAP-ACCEPTANCE", "lens": "quality", "severity": "critical", "status": "OPEN", "question": ""}]
    gaps += [{"id": gap, "lens": "product", "severity": "medium", "status": "OPEN", "question": ""} for gap in PRD_GAPS]
    return gaps


def mention_rows():
    return [
        {"id": "GAP-CTP-EXCLUSION", "lens": "business", "severity": "medium", "status": "OPEN", "question": "",
         "evidence_mention": "out of scope"},
        {"id": "GAP-DESIGN-STATES", "lens": "design", "severity": "medium", "status": "OPEN", "question": "",
         "evidence_mention": "dashboard"},
        {"id": "GAP-METRIC-SOURCE", "lens": "business", "severity": "high", "status": "OPEN", "question": "",
         "evidence_mention": "30 percent"},
        # a path is not something the client wrote: no follow-up
        {"id": "GAP-FRONTEND-SURFACE", "lens": "technical", "severity": "medium", "status": "OPEN", "question": "",
         "evidence_mention": "02_requirements/series/partition.json"},
        # a gap with no follow-up template: no follow-up
        {"id": "GAP-CTP-DEADLINE", "lens": "business", "severity": "medium", "status": "OPEN", "question": "",
         "evidence_mention": "deadline"},
        # a row still carrying the old generic question gets the catalogue one
        {"id": "GAP-HYPOTHETICAL-ANCHOR", "lens": "product", "severity": "low", "status": "OPEN",
         "question": GENERIC[0], "evidence_mention": "It would be nice to export the list."},
    ]


class InterviewClientReadyTest(unittest.TestCase):
    def test_interview_script_reads_for_a_client(self):
        from sentinel.discovery import render_interview_script

        for language in ("en", "es"):
            text = render_interview_script("CLIENT", rows(), language)
            self.assertNotIn("GAP-BRIEF-PROFILE", text, language)
            self.assertNotIn("/brief", text, language)
            self.assertNotIn("IMP-", text, language)
            for generic in GENERIC:
                self.assertNotIn(generic, text, language)
            for gap in PRD_GAPS:
                self.assertIn(gap, text, language)

    def test_prd_gaps_have_their_own_question(self):
        from sentinel.gaps import question_for_gap

        for language in ("en", "es"):
            for gap in PRD_GAPS:
                self.assertNotIn(question_for_gap(gap, language), GENERIC, (gap, language))

    def test_no_internal_labels_but_each_question_keeps_its_reference(self):
        from sentinel.discovery import render_interview_script

        stakeholders = [{"id": "STK-001", "name": "Ops", "domain": "product", "respondent_profile": "business",
                         "topic": "", "notes": ""}]
        for language in ("en", "es"):
            for registry in (None, stakeholders):
                text = render_interview_script("CLIENT", rows() + mention_rows(), language, registry)
                with self.subTest(language=language, registry=bool(registry)):
                    for word in INTERNAL:
                        self.assertNotIn(word, text)
                    for lens in ("business", "product", "design", "technical", "quality"):
                        self.assertNotIn(f"`{lens}`", text)
                        self.assertNotIn(f"### {lens}", text)
                    for gap in [row["id"] for row in rows() + mention_rows()][1:]:
                        self.assertRegex(text, rf"(?m)^### {gap}$")
                    self.assertIn("`GAP-SCOPE`", text.split("## ")[0])  # the header explains the reference code

    def test_follow_ups_are_plain_questions_from_the_matched_text(self):
        from sentinel.discovery import interview_probing_for_gap, render_interview_script

        for language in ("en", "es"):
            text = render_interview_script("CLIENT", mention_rows(), language)
            with self.subTest(language=language):
                self.assertIn('"out of scope"', text)
                self.assertIn('"dashboard"', text)
                self.assertIn('"30 percent"', text)
                self.assertIn('"It would be nice to export the list"', text)
                self.assertNotIn("partition.json", text)
                self.assertNotIn('"deadline"', text)
            probes = {row["id"]: interview_probing_for_gap(row, language) for row in mention_rows()}
            self.assertEqual(probes["GAP-FRONTEND-SURFACE"], [])
            self.assertEqual(probes["GAP-CTP-DEADLINE"], [])
            for gap_id in ("GAP-CTP-EXCLUSION", "GAP-DESIGN-STATES", "GAP-METRIC-SOURCE", "GAP-HYPOTHETICAL-ANCHOR"):
                self.assertEqual(len(probes[gap_id]), 1, gap_id)
                self.assertTrue(probes[gap_id][0]["text"].rstrip().endswith("?"), probes[gap_id])

    def test_every_lens_check_has_a_catalogue_question(self):
        from sentinel.gaps import question_for_gap
        from sentinel.lens_registry import load_lens_checks

        ids = sorted({check["id"] for check in load_lens_checks()})
        self.assertGreater(len(ids), 40)
        for gap_id in ids:
            for language in ("en", "es"):
                question = question_for_gap(gap_id, language)
                with self.subTest(gap=gap_id, language=language):
                    self.assertNotIn(question, GENERIC)
                    self.assertTrue(question.strip())


class InterviewRoundTripTest(unittest.TestCase):
    RAW = (
        "# Risk Dashboard\n\n"
        "We need a dashboard for operations leads to see queue risk before standup. "
        "Success means reducing missed SLAs."
    )

    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_answered_interview_closes_the_answered_gaps(self):
        from sentinel.cli import main
        from sentinel.gaps import parse_gap_rows

        raw = self.temp / "raw.md"
        raw.write_text(self.RAW, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["init", "RT", "--brief-version", "1"]), 0)
            self.assertEqual(main(["ingest", "RT", "--source", str(raw)]), 0)
            self.assertEqual(main(["export", "RT", "--artifact", "gaps", "--format", "interview"]), 0)
        ws = self.temp / "workspaces" / "RT"
        script = (ws / "08_context_packs" / "exports" / "gaps-interview.md").read_text(encoding="utf-8")
        asked = re.findall(r"(?m)^### (GAP-[A-Z0-9-]+)$", script)
        self.assertGreaterEqual(len(asked), 2)
        answered = asked[:2]
        filled = script
        for gap_id in answered:
            block = filled.index(f"### {gap_id}\n")
            at = filled.index("- Answer:", block)
            filled = (filled[:at] + "- Answer: The operations lead confirmed this in the kickoff workshop."
                      + filled[at + len("- Answer:"):])
            for label, value in (("- Owner / source:", " Operations lead"),
                                 ("- Evidence or reference:", " Kickoff workshop minutes"),
                                 ("- Decision status:", " confirmed")):
                at = filled.index(label, block)
                filled = filled[:at + len(label)] + value + filled[at + len(label):]
        answers = self.temp / "client-answers.md"
        answers.write_text(filled, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["resolve-gaps", "RT", "--source", str(answers)]), 0)
        status = {gap["id"]: gap["status"].strip("`") for gap in
                  parse_gap_rows((ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))}
        for gap_id in answered:
            self.assertEqual(status[gap_id], "CLOSED", gap_id)
        for gap_id in asked[2:]:
            self.assertNotEqual(status[gap_id], "CLOSED", gap_id)


if __name__ == "__main__":
    unittest.main()
