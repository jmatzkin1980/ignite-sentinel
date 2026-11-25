"""IMP-420 (H27 inc 6b) task 3: confirming on the project writes 4-column EARS rows (EXT, global numbering)."""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import _HOME_SECTION, ProjectExtractionCase  # noqa: E402

from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.extraction.confirm import confirm_proposals, reject_item  # noqa: E402
from sentinel.extraction.coverage import extraction_coverage  # noqa: E402
from sentinel.extraction.inventory import build_inventory, element_lines, element_text, load_inventory  # noqa: E402
from sentinel.extraction.proposals import record_proposals  # noqa: E402
from sentinel.extraction.verify import start_verification  # noqa: E402
from sentinel.gap_resolution import materialize_ears_requirements  # noqa: E402
from sentinel.generation import parse_ears_requirements  # noqa: E402
from sentinel.health import collect_health  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = ProjectExtractionCase.PID
PROJECT = Path(__file__).resolve().parent / "fixtures" / "project_extraction"
RN02 = "Cuando el analista envía un alta con un CUIT inválido, el sistema debe rechazarla con el mensaje de padrón."
RN02_BIS = "Cuando el analista envía un alta con un CUIT que no figura en el padrón, el sistema debe impedir el envío."
GAP_ANSWER = "When the supplier is disabled, the system shall hide it from the picker."


def block_for(element: dict, base: Path, requisito: str | None = None) -> str:
    flat = " ".join((element_text(base, element) or "").split())
    quote = flat[:60].strip()
    first, last = element_lines(element)
    head = [f"### {element['id']}"]
    if requisito:
        head += ["- Tratamiento: requisito", f"- Líneas: {first}-{last}", f'- Cita: "{quote}"', f"- Enunciado: {requisito}"]
    else:
        section = _HOME_SECTION.get(element.get("home"), "reglas")
        head += ["- Tratamiento: seccion", f"- Líneas: {first}-{last}", f"- Seccion: {section}", f'- Cita: "{quote}"']
    return "\n".join(head) + "\n"


def propose_everything(requisito_rn02: str = RN02) -> None:
    """The fixture proposals plus RN-02 as a requirement and every other element as a section."""
    base = workspace_path(PID)
    build_inventory(PID, None)
    forget_read_snapshots()
    inventory = load_inventory(base, None) or {}
    given = (PROJECT / "propuestas.md").read_text(encoding="utf-8")
    have = set(re.findall(r"^### (\S+)", given, re.M))
    blocks = [given]
    for element in inventory["elements"]:
        if element["id"] in have:
            continue
        blocks.append(block_for(element, base, requisito_rn02 if element["id"] == "RN-02" else None))
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "proposals.md"
        path.write_text("\n".join(blocks), encoding="utf-8")
        result = record_proposals(PID, None, path)
    if result.get("rejected"):
        raise AssertionError(result["rejected"])


def requirements_text() -> str:
    return (workspace_path(PID) / "02_requirements" / "requirements.md").read_text(encoding="utf-8")


def ext_rows() -> list[dict]:
    return [r for r in parse_ears_requirements(requirements_text()) if "EXT:" in r["source"]]


def number(row: dict) -> int:
    return int(row["id"].split("-")[-1])


class ProjectConfirm(ProjectExtractionCase):
    def confirm(self) -> dict:
        propose_everything()
        forget_read_snapshots()
        return confirm_proposals(PID, None, "all")

    def element(self, element_id: str) -> dict:
        inventory = load_inventory(workspace_path(PID), None) or {}
        return next(e for e in inventory["elements"] if e["id"] == element_id)

    def test_confirm_writes_project_ears_rows(self):
        result = self.confirm()
        self.assertEqual(result["held"], [])
        self.assertEqual(len(result["rows_added"]), 4)
        text = requirements_text()
        self.assertIn("## Normalized Requirements (EARS)", text)
        rows = [line for line in text.splitlines() if line.startswith("| REQ-EARS-")]
        self.assertEqual(len(rows), 4)
        for line in rows:
            self.assertEqual(len(line.strip().strip("|").split("|")), 4, line)
        self.assertTrue(any("`EXT:RN-02` / `F-01:" in line for line in rows), rows)
        self.assertEqual(list((workspace_path(PID) / "02_requirements").glob("CHG-*")), [])

    def test_project_ears_rows_parse_and_resolve_gaps_continues(self):
        self.confirm()
        rows = ext_rows()
        k = len(rows)
        self.assertEqual([r["id"] for r in rows], [f"REQ-EARS-{n:03d}" for n in range(1, k + 1)])
        closed = [{"id": "GAP-FUNC-001", "lens": "product", "answer": GAP_ANSWER}]
        forget_read_snapshots()
        materialize_ears_requirements(PID, closed, "CHG-NONE")
        every = parse_ears_requirements(requirements_text())
        ids = [r["id"] for r in every]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[-1], f"REQ-EARS-{k + 1:03d}")
        self.assertEqual(len(every), k + 1)

    def test_reconfirm_replaces_rows_and_never_reuses_ids(self):
        self.confirm()
        before = max(number(r) for r in ext_rows())
        old = next(r for r in ext_rows() if "EXT:RN-02" in r["source"])
        forget_read_snapshots()
        reject_item(PID, None, "RN-02", "el enunciado no refleja la regla")
        retired = workspace_path(PID) / "02_requirements" / "extraction" / "retired_ears.md"
        self.assertTrue(retired.is_file())
        self.assertIn(old["id"], retired.read_text(encoding="utf-8"))
        self.assertFalse(any("EXT:RN-02" in r["source"] for r in ext_rows()))
        forget_read_snapshots()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "p.md"
            path.write_text(block_for(self.element("RN-02"), workspace_path(PID), RN02_BIS), encoding="utf-8")
            self.assertEqual(record_proposals(PID, None, path)["rejected"], {})
        forget_read_snapshots()
        confirm_proposals(PID, None, "all")
        new = [r for r in ext_rows() if "EXT:RN-02" in r["source"]]
        self.assertEqual(len(new), 1)
        self.assertGreater(number(new[0]), before)

    def test_project_coverage_counts(self):
        self.confirm()
        forget_read_snapshots()
        coverage = extraction_coverage(PID, None)
        inventory = load_inventory(workspace_path(PID), None) or {}
        self.assertEqual(coverage["pending"], 0)
        self.assertEqual(coverage["proposed"], 0)
        self.assertEqual(coverage["total"], len(inventory["elements"]))
        self.assertEqual(coverage["orphans"], [])

    def test_project_sections_and_verify(self):
        self.confirm()
        forget_read_snapshots()
        path = workspace_path(PID) / "02_requirements" / "extraction" / "sections.json"
        sections = json.loads(path.read_text(encoding="utf-8"))
        entry = next(e for e in sections["entries"] if e["element"] == "SEC-objetivo")
        self.assertIn("Que el alta de proveedores de Compras se haga", entry["content"])
        start_verification(PID, None)
        verify = workspace_path(PID) / "02_requirements" / "extraction" / "verify" / "001-muestra.md"
        self.assertTrue(verify.is_file())

    def test_ext_rows_keep_health_clean(self):
        self.confirm()
        forget_read_snapshots()
        findings = collect_health(PID)["findings"]
        self.assertFalse([f for f in findings if "REQ-EARS" in json.dumps(f, ensure_ascii=False)], findings)


class Numbering(ProjectExtractionCase):
    def test_project_numbering_unchanged_without_ext(self):
        closed = [{"id": "GAP-FUNC-001", "lens": "product", "answer": GAP_ANSWER}]
        materialize_ears_requirements(PID, closed, "CHG-NONE")
        self.assertEqual([r["id"] for r in parse_ears_requirements(requirements_text())], ["REQ-EARS-001"])


if __name__ == "__main__":
    unittest.main()
