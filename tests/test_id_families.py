"""IMP-249: the central registry of id families and structured citations.

Fixtures are written here: a v2 artifact with structured citations against a v2
brief, plus a v1 workspace that must validate exactly as before.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from sentinel.citations import (
    Citation,
    citation_from_dict,
    is_v2_artifact,
    line_citations,
    parse_citations,
    section_text,
    validate_citation,
    validate_v2_artifact,
)
from sentinel.cli import main
from sentinel.ids import (
    ID_PREFIXES,
    catalog_key_kind,
    family_of,
    graph_node_id_pattern,
    id_registry,
    load_retired_ids,
    next_id,
    prefix_for_node_type,
    retire_id,
    split_release,
)
from sentinel.validation import validate_project

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "sentinel" / "schemas"
MARKER = "<!-- sentinel-artifact: v2 -->"

BRIEF_V2 = f"""{MARKER}
# Project brief - Billing

## 1. Objetivo

### 1.3 Métricas de éxito

- SC-01: tiempo de aprobación, línea base 5 días, meta 2 días.

### 1.5 Criterios de aceptación

- CA-03: una factura de $ 1.000 queda aprobada con doble firma.
- CA-03.1: el rechazo deja el motivo.

## 2. Negocio

### 2.2 Reglas de negocio

#### Alta

- RN-04: el alta exige doble firma.

#### Baja

- RN-05: la baja requiere motivo.

## 9. Próximo release

- C-04: conciliación bancaria. Depende de I-2.
"""


def _schema_pattern(name: str, *path: str) -> str:
    node = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    for key in path:
        node = node[key]
    return node["pattern"]


class RegistryTests(unittest.TestCase):
    def test_every_family_example_matches_its_own_family(self) -> None:
        for name, spec in id_registry()["families"].items():
            self.assertEqual(family_of(spec["example"]), name, name)

    def test_kept_new_and_view_families(self) -> None:
        families = id_registry()["families"]
        for name in ("GAP", "ASM", "DEC", "US", "SPEC-U", "CTX"):
            self.assertEqual(families[name]["status"], "kept")
        for name in ("RN", "CA", "HU", "SC", "I", "F", "P", "E", "C", "R", "PDef"):
            self.assertIn(name, families)
        self.assertEqual(families["D"], {**families["D"], "status": "view", "view_of": "DEC"})
        edges = {(e["from"], e["to"]) for e in id_registry()["edges"]}
        self.assertEqual(edges, {("HU", "SPEC-U"), ("SPEC-U", "US")})

    def test_release_prefix_only_for_rn_ca_hu(self) -> None:
        self.assertEqual(split_release("r2-RN-04"), (2, "RN-04"))
        self.assertEqual(family_of("r2-CA-03"), "CA")
        self.assertEqual(family_of("r12-HU-07"), "HU")
        self.assertIsNone(family_of("r2-GAP-OBJECTIVE"))  # gaps stay global
        self.assertIsNone(family_of("r2-US-001"))
        self.assertEqual(split_release("GAP-X"), (None, "GAP-X"))

    def test_unknown_and_near_miss_ids(self) -> None:
        for value in ("XYZ-1", "SPEC-U-1", "US-1", "gap-objective", "RN-4", "D-2", ""):
            self.assertIsNone(family_of(value), value)
        self.assertEqual(family_of("SPEC-U-001"), "SPEC-U")
        self.assertEqual(family_of("DEC-AUTH-TOKEN"), "DEC")

    def test_catalog_keys(self) -> None:
        self.assertEqual(catalog_key_kind("ERR_PAYMENT_DECLINED"), "error_code")
        self.assertEqual(catalog_key_kind("evt.invoice.approved"), "event")
        self.assertEqual(catalog_key_kind("ff.double_signature"), "flag")
        self.assertEqual(catalog_key_kind("/invoices/{id}/approve"), "route")
        self.assertIsNone(catalog_key_kind("PaymentDeclined"))
        for kind, spec in id_registry()["catalog_keys"].items():
            self.assertEqual(catalog_key_kind(spec["example"]), kind)

    def test_graph_prefixes_cover_every_node_type(self) -> None:
        ids_source = (ROOT / "sentinel" / "ids.py").read_text(encoding="utf-8")
        types = re.findall(r'^\s+"([a-z_]+)": "[A-Z]+",$', ids_source, re.M)
        self.assertTrue(types)
        for node_type in types:
            self.assertIn(prefix_for_node_type(node_type), ID_PREFIXES, node_type)


class SchemaAlignmentTests(unittest.TestCase):
    """The documentary schemas say what the code writes (the DEC drift is fixed)."""

    def test_decision_schema_accepts_named_decisions(self) -> None:
        pattern = _schema_pattern("decision.schema.json", "properties", "id")
        for value in ("DEC-001", "DEC-AUTH-TOKEN"):
            self.assertRegex(value, pattern)

    def test_traceability_schema_matches_the_registry(self) -> None:
        pattern = _schema_pattern("traceability.schema.json", "properties", "nodes", "items", "properties", "id")
        self.assertEqual(pattern, graph_node_id_pattern())
        for value in ("CTX-001", "DISC-004", "SEED-001", "EV-001", "RU-001", "SPEC-U-001", "REQ-EARS-001", "GAP-OBJECTIVE"):
            self.assertRegex(value, pattern)

    def test_schema_id_patterns_accept_the_family_examples(self) -> None:
        families = id_registry()["families"]
        checks = {
            ("gap.schema.json", ("properties", "id")): "GAP",
            ("assumption.schema.json", ("properties", "id")): "ASM",
            ("story.schema.json", ("properties", "id")): "US",
            ("requirement.schema.json", ("properties", "id")): "REQ",
            ("acceptance_criteria.schema.json", ("properties", "id")): "AC",
        }
        for (schema, path), family in checks.items():
            if not (SCHEMAS / schema).exists():
                continue
            try:
                pattern = _schema_pattern(schema, *path)
            except KeyError:
                continue
            example = families[family]["example"] if family != "AC" else "AC-001"
            self.assertRegex(example, pattern, f"{schema} rejects {example}")


class RetiredIdTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.base, ignore_errors=True)

    def test_retired_ids_are_never_reused(self) -> None:
        retire_id(self.base, "US-003", "merged into US-002", "US-002")
        retired = load_retired_ids(self.base)
        self.assertEqual(retired["US-003"]["replacement"], "US-002")
        self.assertEqual(next_id("US", ["US-001", "US-002"], retired), "US-004")
        first = retired["US-003"]["retired_at"]
        retire_id(self.base, "US-003", "again")
        self.assertEqual(load_retired_ids(self.base)["US-003"]["retired_at"], first)  # stays retired once
        with self.assertRaises(ValueError):
            retire_id(self.base, "NOPE-1", "x")
        with self.assertRaises(ValueError):
            retire_id(self.base, "US-009", " ")


class CitationTests(unittest.TestCase):
    docs = {"brief": BRIEF_V2}

    def test_parse_inline_and_dict_forms(self) -> None:
        text = "x [[brief § 2.2 › Alta # RN-04 — sostiene: el alta exige doble firma]] y [[prd § Alcance # US-001 -- supports: scope]]"
        first, second = parse_citations(text)
        self.assertEqual((first.doc, first.section, first.subblock, first.id), ("brief", "2.2", "Alta", "RN-04"))
        self.assertEqual(first.supports, "el alta exige doble firma")
        self.assertEqual((second.section, second.id, second.supports), ("Alcance", "US-001", "scope"))
        data = citation_from_dict({"doc": "brief", "seccion": "2.2", "subbloque": "Alta", "id": "RN-04", "que_sostiene": "x"})
        self.assertEqual(data, Citation(doc="brief", section="2.2", subblock="Alta", id="RN-04", supports="x"))

    def test_sections_by_number_or_title(self) -> None:
        self.assertIn("RN-04", section_text(BRIEF_V2, "2.2"))
        self.assertIn("RN-04", section_text(BRIEF_V2, "Reglas de negocio"))
        self.assertNotIn("SC-01", section_text(BRIEF_V2, "2.2"))
        self.assertIsNone(section_text(BRIEF_V2, "2.3"))
        self.assertIn("RN-05", section_text(BRIEF_V2, "2"))  # "2" is the number of "2. Negocio"
        self.assertIn("RN-05", section_text(BRIEF_V2, "2. Negocio"))
        self.assertNotIn("C-04", section_text(BRIEF_V2, "2"))
        self.assertNotIn("RN-05", section_text(BRIEF_V2, "2.2", "Alta"))
        self.assertIsNone(section_text(BRIEF_V2, "2.2", "Modificación"))

    def test_valid_citation_has_no_findings(self) -> None:
        citation = Citation("brief", "2.2", "RN-04", "el alta exige doble firma", "Alta")
        self.assertEqual(validate_citation(citation, self.docs), [])
        self.assertEqual(validate_citation(Citation("brief", "1.5", "CA-03", "x"), self.docs), [])

    def test_id_outside_its_section_is_a_finding(self) -> None:
        findings = validate_citation(Citation("brief", "1.3", "RN-04", "x"), self.docs)
        self.assertEqual(len(findings), 1)
        self.assertIn("not in the cited section (it is elsewhere in the document)", findings[0])
        sub = validate_citation(Citation("brief", "2.2", "RN-05", "x", "Alta"), self.docs)
        self.assertIn("not in the cited section", sub[0])
        # CA-03 must not resolve against CA-03.1 only
        self.assertEqual(validate_citation(Citation("brief", "1.5", "CA-03.1", "x"), self.docs), [])

    def test_other_findings(self) -> None:
        self.assertIn("says nothing about what the id supports", validate_citation(Citation("brief", "2.2", "RN-04"), self.docs)[0])
        self.assertIn("not an id of any registered family", validate_citation(Citation("brief", "2.2", "XYZ-1", "x"), self.docs)[0])
        self.assertIn("not found in brief", validate_citation(Citation("brief", "7.1", "RN-04", "x"), self.docs)[0])
        self.assertIn("document 'prd' not found", validate_citation(Citation("prd", "1", "US-001", "x"), self.docs)[0])
        retired = {"RN-04": {"reason": "merged"}}
        self.assertIn("is retired", validate_citation(Citation("brief", "2.2", "RN-04", "x"), self.docs, retired)[0])

    def test_line_citations_in_a_v2_artifact(self) -> None:
        text = (f"{MARKER}\n# Specs\n\nVer project-brief.md:120 y la línea 14.\n"
                "Según L30-L32 del acta.\n```\ncode.md:5\n```\n"
                "[[brief § 2.2 # RN-04 — sostiene: alta]]\n")
        self.assertEqual([n for n, _ in line_citations(text)], [4, 4, 5])
        findings = validate_v2_artifact("03_specs/specs.md", text, self.docs)
        self.assertEqual(sum("cites by line number" in f for f in findings), 3)
        self.assertFalse([f for f in findings if "RN-04" in f])

    def test_v2_marker(self) -> None:
        self.assertTrue(is_v2_artifact(BRIEF_V2))
        self.assertFalse(is_v2_artifact("# Project brief\n\nVersión del documento: `1.0`\n"))


class ValidateFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        raw = self.temp / "billing.md"
        raw.write_text("# Billing Portal\n\nFinance users review monthly invoices before approval.\n", encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["init", "IDS", "--brief-version", "1"]), 0)
            self.assertEqual(main(["ingest", "IDS", "--source", str(raw)]), 0)
        self.ws = self.temp / "workspaces" / "IDS"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_v1_artifacts_do_not_change_the_verdict(self) -> None:
        result = validate_project("IDS")
        self.assertFalse([f for f in result["findings"] if "cites by line number" in f or "cited section" in f])

    def test_v2_artifact_findings_reach_validate(self) -> None:
        (self.ws / "02_requirements" / "project-brief.md").write_text(BRIEF_V2, encoding="utf-8")
        specs = self.ws / "03_specs" / "specs.md"
        specs.parent.mkdir(parents=True, exist_ok=True)
        specs.write_text(
            f"{MARKER}\n# Specs\n\n"
            "- [[brief § 2.2 › Alta # RN-04 — sostiene: el alta exige doble firma]]\n"
            "- [[brief § 1.3 # RN-05 — sostiene: la baja requiere motivo]]\n"
            "- Ver project-brief.md:40.\n",
            encoding="utf-8",
        )
        findings = validate_project("IDS")["findings"]
        self.assertTrue(any("RN-05 is not in the cited section" in f for f in findings), findings)
        self.assertTrue(any("cites by line number (project-brief.md:40)" in f for f in findings), findings)
        self.assertFalse(any("RN-04" in f for f in findings))
        self.assertEqual(validate_project("IDS")["verdict"], "INVALID")


if __name__ == "__main__":
    unittest.main()
