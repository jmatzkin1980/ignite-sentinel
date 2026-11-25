"""IMP-420 (H27 inc 6b) task 5: /next P offers crosses and extraction only with evidence."""
from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import _HOME_SECTION, ProjectExtractionCase, run_ok  # noqa: E402
from test_golden_artifacts import RAW_ES  # noqa: E402

from sentinel.core.io import forget_read_snapshots, write_json  # noqa: E402
from sentinel.crosses.claims import cross_sources  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402
from sentinel.extraction.confirm import confirm_proposals, reject_item  # noqa: E402
from sentinel.extraction.coverage import extraction_fingerprint  # noqa: E402
from sentinel.extraction.inventory import build_inventory, element_lines, element_text, load_inventory  # noqa: E402
from sentinel.extraction.proposals import record_proposals  # noqa: E402
from sentinel.readiness_verdict import NEXT_STEPS, build_readiness_verdict  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = ProjectExtractionCase.PID
PROJECT = ProjectExtractionCase.FIXTURES
NEW_KEYS = {"crosses", "extract_inventory", "extract_proposals", "extract_confirm", "extract_orphans", "extract_verify"}
BLOCKING = "\n".join([
    "### GAP-ACCEPTANCE", "- Answer: When the analyst submits a supplier, the system shall register it.",
    "- Owner / source: Jefa de Compras", "- Evidence or reference: Synthetic", "- Decision status: confirmed", "",
    "### GAP-OBJECTIVE", "- Answer: Reducir el tiempo del alta de proveedores.",
    "- Owner / source: Jefa de Compras", "- Evidence or reference: Synthetic", "- Decision status: confirmed", "",
    "### GAP-SCOPE", "- Answer: El alta de proveedores.",
    "- Owner / source: Jefa de Compras", "- Evidence or reference: Synthetic", "- Decision status: confirmed", "",
])


def step(pid: str = PID) -> dict:
    forget_read_snapshots()
    return build_readiness_verdict(pid)["next_step"]


def block_for(element: dict, base: Path) -> str:
    flat = " ".join((element_text(base, element) or "").split())
    first, last = element_lines(element)
    section = _HOME_SECTION.get(element.get("home"), "reglas")
    return "\n".join([f"### {element['id']}", "- Tratamiento: seccion", f"- Líneas: {first}-{last}",
                      f"- Seccion: {section}", f'- Cita: "{flat[:60].strip()}"']) + "\n"


class ProjectNext(ProjectExtractionCase):
    def close_blocking(self) -> None:
        """Confirm the brief settings and answer the three blocking gaps (/resolve-gaps then compiles the brief)."""
        run_ok(["brief", PID, "--profile", "UI", "--genesis", "greenfield"])
        Path("blocking.md").write_text(BLOCKING, encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", "blocking.md"])
        forget_read_snapshots()

    def record_crosses(self) -> None:
        ids = cross_sources(PID, None)
        text = (PROJECT / "cruce_contradicciones.md").read_text(encoding="utf-8").replace("F-PED", sorted(ids["pedido"])[0])
        Path("claims.md").write_text(text, encoding="utf-8")
        forget_read_snapshots()
        opened = record_cross(PID, None, "contradicciones", Path("claims.md"))["gaps_opened"]
        forget_read_snapshots()
        # the contradiction opens a blocking question: the BA answers it before the extraction goes on
        lines = []
        for gap in opened:
            lines += [f"### {gap}", "- Answer: Se aplica el umbral de 5.000.000.", "- Owner / source: Jefa de Compras",
                      "- Evidence or reference: Synthetic", "- Decision status: confirmed", ""]
        Path("cross-answers.md").write_text("\n".join(lines), encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", "cross-answers.md"])
        forget_read_snapshots()

    def propose(self, first: str) -> None:
        base = workspace_path(PID)
        build_inventory(PID, None)
        forget_read_snapshots()
        inventory = load_inventory(base, None) or {}
        given = (PROJECT / first).read_text(encoding="utf-8")
        have = set(re.findall(r"^### (\S+)", given, re.M))
        blocks = [given] + [block_for(e, base) for e in inventory["elements"] if e["id"] not in have]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "proposals.md"
            path.write_text("\n".join(blocks), encoding="utf-8")
            result = record_proposals(PID, None, path)
        self.assertEqual(result.get("rejected"), {})
        forget_read_snapshots()

    def extract_everything(self) -> None:
        self.close_blocking()
        self.record_crosses()
        self.propose("propuestas.md")
        confirm_proposals(PID, None, "all")
        forget_read_snapshots()

    def test_mature_request_goes_crosses_then_extraction(self):
        self.assertEqual(step()["key"], "brief_settings")
        run_ok(["brief", PID, "--profile", "UI", "--genesis", "greenfield"])
        self.assertEqual(step()["key"], "resolve_blocking")
        self.close_blocking()
        found = step()
        self.assertEqual(found["key"], "crosses")
        self.assertEqual(found["command"], f"/cross {PID} --kind contradicciones --claims PATH")
        self.assertEqual(found["skill"], "sentinel-discovery §Cross-reads of a change")
        self.assertIn("contradicciones", found["text"])
        self.record_crosses()
        found = step()
        self.assertEqual(found["key"], "extract_inventory")
        self.assertEqual(found["command"], f"/extract {PID}")
        build_inventory(PID, None)
        found = step()
        self.assertEqual((found["key"], found["command"]), ("extract_proposals", f"/extract {PID} --proposals PATH"))
        self.propose("propuestas.md")
        found = step()
        self.assertEqual((found["key"], found["command"]), ("extract_confirm", f"/extract {PID} --confirm all"))
        confirm_proposals(PID, None, "all")
        forget_read_snapshots()
        # nothing of the extraction is left to offer; the brief /resolve-gaps compiled before it reads as stale
        self.assertEqual(step()["key"], "brief")

    def test_flagged_confirm_names_item(self):
        self.close_blocking()
        self.record_crosses()
        self.propose("propuestas_marcadas.md")
        confirm_proposals(PID, None, "all")
        forget_read_snapshots()
        found = step()
        self.assertEqual(found["key"], "extract_confirm")
        self.assertEqual(found["command"], f"/extract {PID} --confirm-item RN-01")

    def test_baseline_without_harvest_asks_harvest(self):
        self.close_blocking()
        run_ok(["sources", PID, "--load", str(PROJECT.parent / "change_baseline" / "sad-compras.md"),
                "--role", "linea_de_base"])
        forget_read_snapshots()
        found = step()
        self.assertEqual(found["key"], "crosses")
        self.assertEqual(found["command"], f"/harvest {PID} --source PATH")

    def test_compiled_brief_still_offered(self):
        """/resolve-gaps compiles the brief when the blocking gaps close; the offer must not depend on it being absent."""
        self.close_blocking()
        base = workspace_path(PID)
        self.assertTrue((base / "02_requirements" / "project-brief.md").is_file())
        self.assertEqual(step()["key"], "crosses")
        self.record_crosses()
        self.assertTrue((base / "02_requirements" / "project-brief.md").is_file())
        self.assertEqual(step()["key"], "extract_inventory")

    def test_brief_stale_after_extraction(self):
        self.extract_everything()
        base = workspace_path(PID)
        (base / "02_requirements" / "project-brief.md").write_text("# brief\n", encoding="utf-8")
        write_json(base / "02_requirements" / "brief_compile_report.json",
                   {"extraction_fingerprint": extraction_fingerprint(base, None)})
        forget_read_snapshots()
        self.assertNotIn(step()["key"], NEW_KEYS | {"brief"})
        reject_item(PID, None, "RN-02", "el enunciado no refleja la regla")
        forget_read_snapshots()
        self.assertEqual(step()["key"], "extract_proposals")
        element = next(e for e in (load_inventory(base, None) or {})["elements"] if e["id"] == "RN-02")
        first, last = element_lines(element)
        quote = " ".join((element_text(base, element) or "").split())[:60].strip()
        Path("rn02.md").write_text("\n".join([
            "### RN-02", "- Tratamiento: requisito", f"- Líneas: {first}-{last}", f'- Cita: "{quote}"',
            "- Enunciado: Cuando el analista envía un alta con un CUIT inválido, el sistema debe rechazarla con el "
            "mensaje de padrón."]) + "\n", encoding="utf-8")
        self.assertEqual(record_proposals(PID, None, Path("rn02.md")).get("rejected"), {})
        confirm_proposals(PID, None, "all")
        forget_read_snapshots()
        self.assertEqual(step()["key"], "brief")

    def test_new_keys_follow_resolve_blocking(self):
        keys = list(NEXT_STEPS)
        at = keys.index("resolve_blocking")
        self.assertEqual(keys[at + 1:at + 7], ["crosses", "extract_inventory", "extract_proposals", "extract_confirm",
                                               "extract_orphans", "extract_verify"])


class RequestWithoutIds(unittest.TestCase):
    def test_request_without_ids_sees_no_new_step(self):
        old = Path.cwd()
        with tempfile.TemporaryDirectory() as folder:
            os.chdir(folder)
            try:
                Path("raw.md").write_text(RAW_ES, encoding="utf-8")
                run_ok(["init", "NOIDS"])
                run_ok(["ingest", "NOIDS", "--source", "raw.md"])
                self.assertNotIn(step("NOIDS")["key"], NEW_KEYS)
                base = workspace_path("NOIDS")
                self.assertFalse((base / "02_requirements" / "extraction").exists())
                self.assertFalse((base / "01_discovery" / "crosses").exists())
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()
