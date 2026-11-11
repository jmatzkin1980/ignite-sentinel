"""IMP-254: one normalized reading of the project brief, v1 or v2.

`sentinel.brief_model` reads either brief generation into the six canonical
lenses ("1".."6") the readers already use. v1 maps one to one; v2 maps through a
tested table (§5.11 moves to lens 6 with §6). The v1 path is pinned against the
pre-IMP-254 algorithm, copied verbatim below, over the golden briefs.
"""

import re
import unittest
from pathlib import Path

from sentinel import brief_model
from sentinel.brief_schema import load_brief_schema
from sentinel.maturity import brief_section_readiness

ROOT = Path(__file__).resolve().parent
GOLDEN = ROOT / "fixtures" / "golden"
V2_FIXTURE = ROOT / "fixtures" / "brief_v2" / "project-brief.md"


def v2_text(project_id: str = "BRIEF_V2") -> str:
    return V2_FIXTURE.read_text(encoding="utf-8").replace("{project_id}", project_id)


# --- the pre-IMP-254 reader, frozen ------------------------------------------
_LEGACY_RE = re.compile(r"^## (\d+)\.", re.M)
_LEGACY_MARKERS = ("[PENDING INPUT]", "TBD", "PENDING DOMAIN", "No structured evidence", "Documentar el", "Documentar la")


def legacy_lens_bodies(text: str) -> dict[str, str]:
    bodies: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        match = _LEGACY_RE.match(line)
        if match:
            current = match.group(1)
            bodies.setdefault(current, [])
        elif current is not None:
            bodies[current].append(line)
    return {key: "\n".join(lines) for key, lines in bodies.items()}


def legacy_status(body: str) -> tuple[str, int]:
    pending = (not body.strip()) or any(marker in body for marker in _LEGACY_MARKERS)
    return ("pending" if pending else "populated", body.count("00_raw/") + body.count("`GAP-") + body.count("`CHG-"))


class V1CharacterizationTests(unittest.TestCase):
    def briefs(self):
        yield from ((lang, (GOLDEN / lang / "project-brief.md").read_text(encoding="utf-8")) for lang in ("en", "es"))
        yield "inline", "## 1. Identidad\n\n## 2. Negocio\n\nActors cited _(source: `00_raw/`)_\n## Extra\nTBD\n"

    def test_v1_lens_bodies_match_the_legacy_reader(self):
        for name, text in self.briefs():
            model = brief_model.parse_brief(text)
            self.assertEqual(model.version, 1, name)
            legacy = legacy_lens_bodies(text)
            for lens in brief_model.LENSES:
                with self.subTest(brief=name, lens=lens):
                    self.assertEqual(model.lens_body(lens), legacy.get(lens, ""))

    def test_v1_readiness_matches_the_legacy_classification(self):
        for name, text in self.briefs():
            readiness = brief_section_readiness(text)
            self.assertNotIn("brief_version", readiness)
            legacy = legacy_lens_bodies(text)
            for lens in brief_model.LENSES:
                status, citations = legacy_status(legacy.get(lens, ""))
                with self.subTest(brief=name, lens=lens):
                    self.assertEqual(readiness["sections"][lens]["status"], status)
                    self.assertEqual(readiness["sections"][lens]["evidence_citations"], citations)


class LensMapTests(unittest.TestCase):
    def test_every_v2_body_section_maps_to_exactly_one_lens(self):
        schema = load_brief_schema()
        owners: dict[str, list[str]] = {}
        for section in schema["sections"]:
            for entry in section.get("subsections", []):
                owners[entry["id"]] = brief_model.lenses_for_v2_id(entry["id"])
        for sid, lenses in owners.items():
            top = sid.split(".")[0]
            with self.subTest(id=sid):
                if top in {"0", "7", "8", "9"}:
                    self.assertEqual(lenses, [], "header and closing sections feed no lens")
                else:
                    self.assertEqual(len(lenses), 1)
        self.assertEqual(owners["5.11"], ["6"])
        self.assertEqual(owners["5.7"], ["5"])
        self.assertEqual(owners["6.1"], ["6"])
        self.assertEqual(owners["1.3"], ["1"])

    def test_lens_titles_come_from_the_model(self):
        self.assertEqual(tuple(brief_model.LENS_TITLES), brief_model.LENSES)
        self.assertEqual(brief_model.LENS_TITLES["6"], "Gobernanza y Restricciones")

    def test_gap_routes_to_v2_sections_through_its_lens(self):
        self.assertEqual(brief_model.v2_sections_for_gap("GAP-USERS"), ["2.1"])
        self.assertEqual(brief_model.v2_sections_for_gap("GAP-GOVERNANCE-CONSTRAINTS"), ["5.11"])
        self.assertEqual(brief_model.v2_sections_for_gap("GAP-UNKNOWN"), [])


class V2ReadTests(unittest.TestCase):
    def setUp(self):
        self.model = brief_model.parse_brief(v2_text())

    def test_detects_v2_and_its_sections(self):
        self.assertEqual(self.model.version, 2)
        self.assertIn("5.11", self.model.sections)
        self.assertIn("1", self.model.sections)
        self.assertEqual(self.model.sections["1.1"].title, "1.1 Identity and Value")

    def test_lens_five_excludes_governance_and_lens_six_takes_it(self):
        five, six = self.model.lens_body("5"), self.model.lens_body("6")
        self.assertIn("5.1 Architecture", five)
        self.assertNotIn("Governance and Constraints", five)
        self.assertIn("Governance and Constraints", six)
        self.assertIn("6.1 In Scope", six)
        self.assertNotIn("7.2", six)

    def test_markers_and_citations(self):
        kinds = sorted({m["kind"] for m in self.model.markers})
        self.assertEqual(kinds, ["pending", "pending_domain"])
        self.assertEqual(len(self.model.citations), 6)

    def test_readiness_reads_v2_marks(self):
        readiness = brief_section_readiness(v2_text())
        self.assertEqual(readiness["brief_version"], 2)
        sections = readiness["sections"]
        self.assertEqual(sections["1"], {"status": "populated", "evidence_citations": 4})
        self.assertEqual(sections["2"]["status"], "pending")  # 2.5 waits on the client
        self.assertEqual(sections["3"]["status"], "populated")
        self.assertEqual(sections["4"]["status"], "pending")
        self.assertEqual(sections["5"]["status"], "pending")
        self.assertEqual(sections["6"], {"status": "populated", "evidence_citations": 1})
        self.assertEqual(readiness["coverage_score"], 0.5)

    def test_section_id_at_line(self):
        lines = v2_text().splitlines()
        line = next(i for i, text in enumerate(lines, start=1) if text.startswith("Dashboard access is recorded"))
        self.assertEqual(self.model.section_id_at_line(line), "5.11")
        self.assertEqual(self.model.section_id_at_line(1), "")

    def test_excerpt_maps_v1_heading_terms(self):
        self.assertIn("Operations leads review risk queues", brief_model.excerpt(v2_text(), "Identidad"))
        technical = brief_model.excerpt(v2_text(), "Lente Tecnico")
        self.assertTrue(technical.startswith("## 5. Technical Lens"))
        self.assertIn("1.3 Success Metrics / Scope", brief_model.excerpt(v2_text(), "Scope"))
        self.assertEqual(brief_model.excerpt(v2_text(), "Nothing Like This"), "")


class ReaderMigrationTests(unittest.TestCase):
    def test_retrieval_reads_v2_by_alias_and_v1_unchanged(self):
        from sentinel.retrieval_plans import section_excerpt, select_source_context

        plan = {"source_sections": ["Identidad"], "budget_chars": 4000, "query": "x"}
        context = select_source_context({"requirements-context": v2_text()}, plan)
        self.assertIn("Operations leads review risk queues", context)
        v1 = (GOLDEN / "es" / "project-brief.md").read_text(encoding="utf-8")
        self.assertEqual(
            select_source_context({"requirements-context": v1}, plan),
            f"[requirements-context:Identidad]\n{section_excerpt(v1, 'Identidad')}"[:4000].rstrip(),
        )

    def test_backlog_anchor_uses_section_id_for_a_v2_brief(self):
        import tempfile

        from sentinel.compilers.backlog import anchor_for_context_row, render_anchor_inline

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "project-brief.md"
            path.write_text(v2_text(), encoding="utf-8")
            line = next(i for i, text in enumerate(v2_text().splitlines(), start=1) if text.startswith("Dashboard access"))
            row = {"source_path": str(path), "section_path": "5. Technical Lens > 5.11 Governance and Constraints",
                   "line_start": line, "line_end": line}
            anchor = anchor_for_context_row(row)
            self.assertEqual(anchor["section_id"], "5.11")
            rendered = render_anchor_inline(anchor)
            self.assertTrue(rendered.startswith(f"Anchor: {path} § 5.11; section: "), rendered)
            self.assertNotIn(f":{line}-", rendered)

            v1_path = Path(tmp) / "v1.md"
            v1_path.write_text("# Brief\n\n## 1. Identidad\n\nText\n", encoding="utf-8")
            v1_anchor = anchor_for_context_row({"source_path": str(v1_path), "section_path": "1. Identidad",
                                                "line_start": 3, "line_end": 5})
            self.assertNotIn("section_id", v1_anchor)
            self.assertEqual(render_anchor_inline(v1_anchor), f"Anchor: {v1_path}:3-5; section: 1. Identidad")

    def test_view_counts_structured_citations_only_in_v2(self):
        from sentinel.view import citation_pattern

        self.assertIsNotNone(citation_pattern(v2_text()).search("[[raw § Users # RAW-001 — supports: x]]"))
        self.assertIsNone(citation_pattern("# v1\n").search("[[raw § Users # RAW-001 — supports: x]]"))


class V2WorkspaceTests(unittest.TestCase):
    """Acceptance: a v2 brief drives maturity, specs and the view, and survives them."""

    def test_v2_brief_compiles_maturity_specs_and_view(self):
        import contextlib
        import io
        import json
        import os
        import shutil
        import sys
        import tempfile
        from unittest.mock import patch

        from sentinel.cli import main
        from sentinel.memory import ContextBroker
        from sentinel.view import collect_artifact_model

        sys.path.insert(0, str(ROOT))
        from test_golden_artifacts import SCENARIOS

        scenario = SCENARIOS["en"]
        pid = "BRIEF_V2_E2E"
        old_cwd = Path.cwd()
        tmp = Path(tempfile.mkdtemp())
        os.chdir(tmp)
        try:
            with patch.object(ContextBroker, "_connect_lancedb", lambda self: None), \
                    contextlib.redirect_stdout(io.StringIO()):
                raw = tmp / "raw.md"
                raw.write_text(scenario["raw"], encoding="utf-8")
                self.assertEqual(main(["init", pid, "--brief-version", "1"]), 0)
                self.assertEqual(main(["ingest", pid, "--source", str(raw)]), 0)
                for index, statement in enumerate(scenario["ears"], start=1):
                    answer = tmp / f"answer-{index}.md"
                    answer.write_text(scenario["answer"].format(s=statement, i=index), encoding="utf-8")
                    self.assertEqual(main(["resolve-gaps", pid, "--source", str(answer)]), 0)
                brief = tmp / "workspaces" / pid / "02_requirements" / "project-brief.md"
                brief.parent.mkdir(parents=True, exist_ok=True)
                brief.write_text(v2_text(pid), encoding="utf-8")
                for command in ("maturity", "brief", "specs"):
                    self.assertEqual(main([command, pid]), 0, command)
                model = collect_artifact_model(pid, "brief")
            self.assertEqual(brief.read_text(encoding="utf-8"), v2_text(pid), "the v1 compiler must not overwrite v2")
            state = json.loads((tmp / "workspaces" / pid / "state.json").read_text(encoding="utf-8"))
            readiness = state["maturity_metrics"]["brief_section_readiness"]
            self.assertEqual(readiness["brief_version"], 2)
            self.assertEqual(readiness["coverage_score"], 0.5)
            self.assertTrue((tmp / "workspaces" / pid / "03_specs" / "specs.md").exists())
            self.assertGreaterEqual(len(model["citations"]), 6)
            self.assertTrue(any("5.11" in section["title"] for section in model["sections"]))
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
