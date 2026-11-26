"""IMP-420 (H27 inc 6b) task 8: a mature project request walked from /next to the brief and the specs, by the CLI."""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import _HOME_SECTION, ProjectExtractionCase, run_ok  # noqa: E402

from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.claims import cross_sources  # noqa: E402
from sentinel.extraction.inventory import element_lines, element_text, load_inventory  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = ProjectExtractionCase.PID
FIXTURES = ProjectExtractionCase.FIXTURES
BLOCKING = "\n".join([
    "### GAP-ACCEPTANCE", "- Answer: When the analyst submits a supplier, the system shall register it.",
    "- Owner / source: Jefa de Compras", "- Evidence or reference: Synthetic", "- Decision status: confirmed", "",
    "### GAP-OBJECTIVE", "- Answer: Reducir el tiempo del alta de proveedores.",
    "- Owner / source: Jefa de Compras", "- Evidence or reference: Synthetic", "- Decision status: confirmed", "",
    "### GAP-SCOPE", "- Answer: El alta de proveedores.",
    "- Owner / source: Jefa de Compras", "- Evidence or reference: Synthetic", "- Decision status: confirmed", "",
])


def next_step() -> dict:
    forget_read_snapshots()
    return json.loads(run_ok(["next", PID]))


def decided(gaps: list[str], answer: str) -> str:
    lines = []
    for gap in gaps:
        lines += [f"### {gap}", f"- Answer: {answer}", "- Owner / source: Jefa de Compras",
                  "- Evidence or reference: Synthetic", "- Decision status: confirmed", ""]
    return "\n".join(lines)


class ProjectExtractionWalk(ProjectExtractionCase):
    def claims(self, name: str, ids: dict) -> str:
        text = (FIXTURES / name).read_text(encoding="utf-8").replace("F-PED", sorted(ids["pedido"])[0])
        if ids.get("diseno"):
            text = text.replace("F-DIS", sorted(ids["diseno"])[0])
        Path(name).write_text(text, encoding="utf-8")
        return name

    def proposals(self) -> str:
        base = workspace_path(PID)
        inventory = load_inventory(base, None) or {}
        given = (FIXTURES / "propuestas.md").read_text(encoding="utf-8")
        have = set(re.findall(r"^### (\S+)", given, re.M))
        blocks = [given]
        for element in inventory["elements"]:
            if element["id"] in have:
                continue
            flat = " ".join((element_text(base, element) or "").split())
            first, last = element_lines(element)
            section = _HOME_SECTION.get(element.get("home"), "reglas")
            blocks.append("\n".join([
                f"### {element['id']}", "- Tratamiento: seccion", f"- Líneas: {first}-{last}",
                f"- Seccion: {section}", f'- Cita: "{flat[:60].strip()}"']) + "\n")
        Path("proposals.md").write_text("\n".join(blocks), encoding="utf-8")
        return "proposals.md"

    def test_mature_request_walk(self):
        self.assertEqual(next_step()["key"], "brief_settings")
        run_ok(["brief", PID, "--profile", "UI", "--genesis", "greenfield"])
        self.assertEqual(next_step()["key"], "resolve_blocking")
        Path("blocking.md").write_text(BLOCKING, encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", "blocking.md"])
        self.assertEqual(next_step()["key"], "crosses")

        run_ok(["sources", PID, "--load", str(FIXTURES / "prototipo-alta-proveedor.html"), "--role", "diseno_nuevo"])
        forget_read_snapshots()
        ids = cross_sources(PID, None)
        run_ok(["cross", PID, "--kind", "diseno", "--claims", self.claims("cruce_diseno.md", ids)])
        forget_read_snapshots()
        run_ok(["cross", PID, "--kind", "contradicciones", "--claims", self.claims("cruce_contradicciones.md", ids)])
        self.assertEqual(next_step()["key"], "resolve_blocking")  # the crosses open blocking questions
        base = workspace_path(PID)
        gaps_text = (base / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        cross_gaps = sorted(set(re.findall(r"GAP-(?:DIS|SRD|SED|CON)-[0-9A-Za-z]+", gaps_text)))
        contradiction = [g for g in cross_gaps if g.startswith("GAP-CON-")]
        self.assertTrue(contradiction, gaps_text)
        Path("cross-answers.md").write_text(decided(cross_gaps, "Se aplica el umbral de 5.000.000."), encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", "cross-answers.md"])
        self.assertEqual(next_step()["key"], "extract_inventory")

        seen = []
        for _ in range(12):
            found = next_step()
            key = found["key"]
            seen.append(key)
            if key == "extract_inventory":
                run_ok(["extract", PID])
            elif key == "extract_proposals":
                run_ok(["extract", PID, "--proposals", self.proposals()])
            elif key == "extract_confirm":
                flagged = re.search(r"--confirm-item (\S+)", found["command"])
                run_ok(["extract", PID] + (["--confirm-item", flagged.group(1)] if flagged else ["--confirm", "all"]))
            else:
                break
        self.assertEqual(seen[:3], ["extract_inventory", "extract_proposals", "extract_confirm"])
        self.assertEqual(seen[-1], "brief")  # compiled before the extraction: it asks to be recompiled

        run_ok(["brief", PID])
        brief = (base / "02_requirements" / "project-brief.md").read_text(encoding="utf-8")
        self.assertIn("el alta queda en estado Observada", brief)
        self.assertEqual(next_step()["key"], "specs")

        forget_read_snapshots()
        status = json.loads(run_ok(["status", PID]))
        blockers = json.dumps(status["verdict"]["blockers"], ensure_ascii=False)
        for gap in contradiction:
            self.assertNotIn(gap, blockers)


if __name__ == "__main__":
    unittest.main()
