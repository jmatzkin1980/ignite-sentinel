"""IMP-261: the governed glossary, its brief v2 annex and PRD section, and the
glossary/governance gap split."""

import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel.brief_model import V2_GAP_ROUTES, parse_brief
from sentinel.compilers.brief_v2 import render_brief_v2
from sentinel.discovery.workflow import PRD_SECTION_FOR_GAP, detect_gaps, question_for_gap
from sentinel.glossary import build_glossary, terms_from_answer

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from test_brief_v2_compiler import RAW, inputs  # noqa: E402

GLOSSARY_RAW = """# Risk Dashboard

A risk queue means a group of open cases sharing the same SLA, stored as `risk_queue` (not to be confused with a support ticket).
We track the Service Level Agreement (SLA) per queue.

## Glosario
- Caso: un pedido de un cliente.
"""


class ExtractionTests(unittest.TestCase):
    def test_definitions_sections_and_expansions(self):
        terms = {t["term"]: t for t in build_glossary([("F-01", "raw.md", GLOSSARY_RAW)], [])}
        self.assertEqual(set(terms), {"Risk queue", "SLA", "Caso"})
        queue = terms["Risk queue"]
        self.assertEqual(queue["canonical"], "risk_queue")
        self.assertEqual(queue["not_confuse"], "a support ticket")
        self.assertFalse(queue["inferred"])
        self.assertTrue(terms["SLA"]["inferred"])  # an expansion is not a definition
        self.assertEqual(terms["SLA"]["definition"], "Service Level Agreement")
        self.assertEqual(terms["Caso"]["definition"], "un pedido de un cliente")

    def test_confirmed_answer_wins_and_a_stated_definition_beats_an_expansion(self):
        answers = [{"gap": "GAP-PRD-GLOSSARY-GOVERNANCE", "source": "F-02",
                    "statement": "SLA: maximum hours to first response; Stale data: metrics older than 15 minutes"}]
        terms = {t["term"]: t for t in build_glossary([("F-01", "raw.md", GLOSSARY_RAW)], answers)}
        self.assertEqual(terms["SLA"]["definition"], "maximum hours to first response")
        self.assertEqual(terms["SLA"]["source"], "F-02")
        self.assertFalse(terms["SLA"]["inferred"])
        self.assertIn("Stale data", terms)
        self.assertEqual(terms_from_answer("Glosario: Caso: un pedido", "F-03")[0]["term"], "Caso")

    def test_nothing_is_invented(self):
        self.assertEqual(build_glossary([("F-01", "raw.md", RAW)], []), [])


class BriefAnnexTests(unittest.TestCase):
    def test_annex_renders_the_glossary_with_citations(self):
        data = inputs(raw_sources=[("F-01", "raw.md", GLOSSARY_RAW)])
        text, report = render_brief_v2(data)
        model = parse_brief(text)
        annex = "\n".join(text.splitlines()[model.sections["A.glossary"].start:model.sections["A.glossary"].end])
        self.assertIn("| Term | Definition | Canonical name | Do not confuse with | Source |", annex)
        self.assertIn("| Risk queue | a group of open cases sharing the same SLA, stored as `risk_queue` | `risk_queue` "
                      "| a support ticket | [[sources § Source log - V2_PURE # F-01", annex)
        self.assertIn("| SLA | (inferred) Service Level Agreement | (not given) | (not given) |", annex)
        self.assertNotIn("⏳", annex)
        self.assertTrue(any(p["id"] == "A.glossary" and p["fill"] == "covered" for p in report["places"]))
        self.assertTrue(any(row["place"] == "A.glossary" for row in report["inferred"]))

    def test_without_terms_the_annex_stays_pending(self):
        text, _ = render_brief_v2(inputs())
        model = parse_brief(text)
        annex = "\n".join(text.splitlines()[model.sections["A.glossary"].start:model.sections["A.glossary"].end])
        self.assertIn("⏳ PENDING (", annex)


class GapSplitTests(unittest.TestCase):
    def test_glossary_and_governance_are_two_gaps(self):
        fired = {g["id"] for g in detect_gaps("A dashboard for leads. Access is audited under the governance policy.")}
        self.assertIn("GAP-PRD-GLOSSARY-GOVERNANCE", fired)
        self.assertNotIn("GAP-PRD-GOVERNANCE", fired)
        fired = {g["id"] for g in detect_gaps("A risk queue means open cases with the same SLA.")}
        self.assertNotIn("GAP-PRD-GLOSSARY-GOVERNANCE", fired)
        self.assertIn("GAP-PRD-GOVERNANCE", fired)

    def test_routes_and_texts(self):
        self.assertEqual(V2_GAP_ROUTES["GAP-PRD-GLOSSARY-GOVERNANCE"], "A.glossary")
        self.assertEqual(V2_GAP_ROUTES["GAP-PRD-GOVERNANCE"], "5.11")
        self.assertEqual((PRD_SECTION_FOR_GAP["GAP-PRD-GLOSSARY-GOVERNANCE"], PRD_SECTION_FOR_GAP["GAP-PRD-GOVERNANCE"]), ("13", "11"))
        self.assertIn("nombre canónico", question_for_gap("GAP-PRD-GLOSSARY-GOVERNANCE", "es"))
        self.assertIn("audit", question_for_gap("GAP-PRD-GOVERNANCE", "en"))


class PrdSectionTests(unittest.TestCase):
    def test_prd_section_13_is_the_project_glossary(self):
        from sentinel.cli import main
        from sentinel.memory import ContextBroker
        from test_golden_artifacts import SCENARIOS

        scenario = SCENARIOS["en"]
        pid = "GLOSSARY_PRD"
        old_cwd = Path.cwd()
        tmp = Path(tempfile.mkdtemp())
        os.chdir(tmp)
        try:
            with patch.object(ContextBroker, "_connect_lancedb", lambda self: None), contextlib.redirect_stdout(io.StringIO()):
                raw = tmp / "raw.md"
                raw.write_text(scenario["raw"] + "\nA risk queue means a group of open cases sharing the same SLA.\n", encoding="utf-8")
                self.assertEqual(main(["init", pid, "--brief-version", "1"]), 0)
                self.assertEqual(main(["ingest", pid, "--source", str(raw)]), 0)
                for index, statement in enumerate(scenario["ears"], start=1):
                    answer = tmp / f"answer-{index}.md"
                    answer.write_text(scenario["answer"].format(s=statement, i=index), encoding="utf-8")
                    self.assertEqual(main(["resolve-gaps", pid, "--source", str(answer)]), 0)
                for command in ("brief", "specs"):
                    self.assertEqual(main([command, pid]), 0)
            base = tmp / "workspaces" / pid
            prd = (base / "03_specs" / "prd.md").read_text(encoding="utf-8")
            section = prd.split("## 13. Glossary", 1)[1].split("\n# ", 1)[0]
            self.assertIn("| Risk queue | a group of open cases sharing the same SLA |", section)
            self.assertNotIn("Mature requirement", section)
            self.assertTrue((base / "01_discovery" / "glossary.json").exists())
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
