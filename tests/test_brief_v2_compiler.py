"""IMP-253a: the brief v2 compiler.

Pure rendering over synthetic inputs (determinism, coverage of every applicable
place, §0.2 = §7, grouped N/A, §6.3 deltas, unused sources) and one workspace run
(opt-in, GAP-BRIEF-PROFILE, citations that resolve, IMP-145 still satisfied).
"""

import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel.brief_model import V2_GAP_ROUTES, lenses_for_v2_id, parse_brief
from sentinel.brief_schema import applicability, schema_ids
from sentinel.compilers.brief_v2 import BriefInputs, render_brief_v2
from sentinel.discovery import brief_section_for_gap

ROOT = Path(__file__).resolve().parent

RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads.

In scope: read-only risk dashboard for open queues. Out of scope: editing cases.

Today the queues are exported by hand every morning.
"""


def inputs(**overrides) -> BriefInputs:
    base = dict(
        project_id="V2_PURE",
        language="en",
        profiles=["UI"],
        genesis="greenfield",
        raw_sources=[("F-01", "raw.md", RAW), ("F-03", "notes.md", "Unrelated meeting logistics.\n")],
        gap_answers=[{"gap": "GAP-ACCEPTANCE", "statement": "The dashboard shows every open queue.", "source": "F-02"}],
        gaps=[{"id": "GAP-OBJECTIVE", "severity": "high", "status": "OPEN", "origin": ""},
              {"id": "GAP-ACCEPTANCE", "severity": "high", "status": "CLOSED", "origin": ""}],
        assumptions=[{"id": "ASM-QUEUE", "statement": "Queue metrics refresh hourly.", "status": "OPEN"}],
        registry=[{"id": "F-01", "paths": ["raw.md"], "validity": "current"},
                  {"id": "F-02", "paths": ["a1.md"], "validity": "current"},
                  {"id": "F-03", "paths": ["notes.md"], "validity": "current"}],
        source_log_title="Source log - V2_PURE",
    )
    base.update(overrides)
    return BriefInputs(**base)


class RenderTests(unittest.TestCase):
    def test_two_runs_are_identical_and_a_rerun_over_itself_too(self):
        first, report = render_brief_v2(inputs())
        self.assertEqual(first, render_brief_v2(inputs())[0])
        again, _ = render_brief_v2(inputs(previous_text=first))
        self.assertEqual(again, first)
        self.assertTrue(first.startswith("<!-- sentinel-artifact: v2 -->"))
        self.assertEqual(parse_brief(first).version, 2)

    def test_no_applicable_subsection_is_omitted(self):
        text, report = render_brief_v2(inputs(profiles=["UI", "BAT"]))
        app = applicability(["UI", "BAT"], "greenfield")
        for sid, entry in app["entries"].items():
            level = "##" if sid.startswith("A.") else "###"
            with self.subTest(id=sid):
                self.assertRegex(text, rf"(?m)^{level} {re.escape(sid)} ")
        placed = {place["id"] for place in report["places"]}
        for sid, entry in app["entries"].items():
            if sid in {"0.1", "0.2", "6.3", "7.1", "7.2", "8.1", "9.1", "A.provenance"}:
                continue
            with self.subTest(place=sid):
                self.assertTrue(sid in placed or any(p.startswith(sid + "/") for p in placed))

    def test_facts_cite_their_source_and_answers_name_their_gap(self):
        text, report = render_brief_v2(inputs())
        self.assertIn("Objective: let operations leads review risk queues before the daily meeting. "
                      "[[sources § Source log - V2_PURE # F-01 — supports: Identity and Value]]", text)
        self.assertIn("The dashboard shows every open queue. (`GAP-ACCEPTANCE`) "
                      "[[sources § Source log - V2_PURE # F-02 — supports: Release Acceptance Criteria (GAP-ACCEPTANCE)]]", text)
        self.assertIn("Today the queues are exported by hand every morning.", parse_brief(text).lens_body("3"))
        self.assertIn("`ASM-QUEUE` — Queue metrics refresh hourly.", text)
        for line in text.splitlines():
            if line.startswith("- ") and "F-0" in line and "`F-0" not in line:
                self.assertIn("[[sources §", line)

    def test_status_and_open_items_count_the_same_marks(self):
        text, report = render_brief_v2(inputs())
        client = len(re.findall(r"⏳ PENDING \(", text))
        domain = len(re.findall(r"⏳ PENDING DOMAIN \(", text))
        summary = report["summary"]
        self.assertEqual((summary["pending_client"], summary["pending_domain"]), (client, domain))
        self.assertIn(f"{client} client marks (block) and {domain} domain marks (deferrable) in the body.", text)
        self.assertIn(f"Ready to build: no. {client} pending marks block (§7).", text)
        rows = [line for line in text.splitlines() if re.match(r"^\| (\d|A) \| \d", line)]
        cells = [[cell.strip() for cell in row.strip("|").split("|")] for row in rows]
        self.assertEqual(len(cells), 11)
        self.assertEqual([sum(int(row[2]) for row in cells), sum(int(row[3]) for row in cells)], [client, domain])
        self.assertEqual(len(report["fill_sites"]), client + domain)
        self.assertTrue(all(site["produces"] for site in report["fill_sites"]))
        self.assertIn("⚠ Low reliability", text)
        self.assertIn("`GAP-OBJECTIVE` | high", text)
        self.assertNotIn("`GAP-ACCEPTANCE` | high", text)

    def test_grouped_na_with_counterfactual(self):
        text, report = render_brief_v2(inputs(profiles=["BAT"]))
        model = parse_brief(text)
        lines = text.splitlines()
        body_41 = "\n".join(lines[model.sections["4.1"].start:model.sections["4.1"].end])
        body_42 = "\n".join(lines[model.sections["4.2"].start:model.sections["4.2"].end])
        self.assertIn("N/A — the project has no user surface of its own.", body_41)
        self.assertIn("N/A — see 4.1.", body_42)
        self.assertGreater(report["summary"]["na"], 5)

    def test_spanish(self):
        text, _ = render_brief_v2(inputs(language="es"))
        self.assertIn("## 2. Lente de Negocio", text)
        self.assertIn("⏳ PENDIENTE (", text)
        self.assertIn("— sostiene: Identidad y Valor]]", text)
        self.assertIn("Listo para construir: no.", text)

    def test_cascade_marks_what_changed(self):
        first, _ = render_brief_v2(inputs())
        changed = inputs(previous_text=first, gap_answers=[
            {"gap": "GAP-ACCEPTANCE", "statement": "The dashboard shows every open queue.", "source": "F-02"},
            {"gap": "GAP-USERS", "statement": "Team leads also read the dashboard.", "source": "F-02"},
        ])
        text, _ = render_brief_v2(changed)
        self.assertIn("| 2.1 | `MODIFIED` | prd, specs |", text)
        self.assertIn("First v2 compilation", first)

    def test_unused_sources_are_reported(self):
        _, report = render_brief_v2(inputs())
        self.assertEqual(report["unused_sources"], ["F-03"])
        self.assertEqual(report["sources_cited"]["F-01"] >= 1, True)


class RouteTests(unittest.TestCase):
    def test_routes_point_at_schema_ids_and_agree_with_the_lens_map(self):
        known = set(schema_ids())
        exceptions = set()
        for gap, sid in V2_GAP_ROUTES.items():
            self.assertIn(sid, known, gap)
            lens = brief_section_for_gap(gap)
            if lens and lenses_for_v2_id(sid) != [lens]:
                exceptions.add(gap)
        self.assertEqual(exceptions, {"GAP-SCOPE", "GAP-BUSINESS-RULES", "GAP-DELIVERY-READINESS"})


class WorkspaceTests(unittest.TestCase):
    def test_opt_in_profile_gap_and_compiled_brief(self):
        from sentinel.citations import validate_structured_citations
        from sentinel.cli import main
        from sentinel.memory import ContextBroker

        sys.path.insert(0, str(ROOT))
        from test_golden_artifacts import SCENARIOS

        scenario = SCENARIOS["en"]
        pid = "BRIEF_V2_COMPILE"
        old_cwd = Path.cwd()
        tmp = Path(tempfile.mkdtemp())
        os.chdir(tmp)
        out = io.StringIO()
        try:
            with patch.object(ContextBroker, "_connect_lancedb", lambda self: None), contextlib.redirect_stdout(out):
                raw = tmp / "raw.md"
                raw.write_text(scenario["raw"], encoding="utf-8")
                self.assertEqual(main(["init", pid, "--brief-version", "1"]), 0)
                self.assertEqual(main(["ingest", pid, "--source", str(raw)]), 0)
                for index, statement in enumerate(scenario["ears"], start=1):
                    answer = tmp / f"answer-{index}.md"
                    answer.write_text(scenario["answer"].format(s=statement, i=index), encoding="utf-8")
                    self.assertEqual(main(["resolve-gaps", pid, "--source", str(answer)]), 0)
                base = tmp / "workspaces" / pid
                brief = base / "02_requirements" / "project-brief.md"
                gaps = base / "01_discovery" / "gaps.md"

                self.assertEqual(main(["brief", pid, "--brief-version", "2"]), 0)
                self.assertNotIn("sentinel-artifact: v2", brief.read_text(encoding="utf-8"))
                self.assertRegex(gaps.read_text(encoding="utf-8"), r"\| `?GAP-BRIEF-PROFILE`? \|[^\n]*\| OPEN \|")

                out.truncate(0)
                out.seek(0)
                self.assertEqual(main(["brief", pid, "--profile", "UI", "--genesis", "greenfield"]), 0)
                result = json.loads(out.getvalue())
                first = brief.read_text(encoding="utf-8")
                self.assertTrue(first.startswith("<!-- sentinel-artifact: v2 -->"))
                self.assertRegex(gaps.read_text(encoding="utf-8"), r"\| `?GAP-BRIEF-PROFILE`? \|[^\n]*\| CLOSED \|")
                self.assertEqual(result["self_correction"]["findings"], [])
                self.assertEqual(result["brief_settings"]["brief_version"], 2)
                self.assertEqual(result["brief_section_readiness"]["brief_version"], 2)
                report = json.loads((base / "02_requirements" / "brief_compile_report.json").read_text(encoding="utf-8"))
                self.assertGreater(report["summary"]["covered"], 0)
                self.assertEqual(validate_structured_citations(base), [])

                self.assertEqual(main(["brief", pid]), 0)
                self.assertEqual(brief.read_text(encoding="utf-8"), first, "a re-run is byte-identical")
                self.assertEqual(main(["specs", pid]), 0)
                self.assertEqual(brief.read_text(encoding="utf-8"), first)
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
