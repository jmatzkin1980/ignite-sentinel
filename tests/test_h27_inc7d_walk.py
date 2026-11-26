"""H27 inc 7d walk: the confirmed series of a change is derived release by release, r1 is closed and r2 preserves it."""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SyncCase, run_ok  # noqa: E402

from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = "W7D"
CID = "CHG-001"
INC7 = SyncCase.FIXTURES / "change_inc7"


def _answer(gap: str, text: str, delta: str, surface: str) -> str:
    return (f"### {gap}\n- Respuesta: {text}\n- Owner / fuente: Jefa de Compras\n- Delta: {delta}\n"
            f"- Superficie: {surface}\n- Estado de decisión: confirmado\n")


ANSWERS = "\n".join([
    _answer("GAP-BACKEND-SURFACE", "Cuando el comprador completa el alta, el sistema debe guardar el proveedor.",
            "MODIFIED", "Alta de proveedores"),
    _answer("GAP-QUALITY", "Cuando el comprador guarda el alta, el sistema debe registrar el proveedor en la tabla.",
            "MODIFIED", "Tabla de proveedores"),
    _answer("GAP-DESIGN-FLOW", "Cuando la jefatura abre la bandeja, el sistema debe listar las altas pendientes.",
            "ADDED", "Bandeja de aprobaciones"),
    _answer("GAP-DESIGN-STATES", "Cuando el monto supera el umbral, el sistema debe pedir aprobación de jefatura.",
            "ADDED", "Aprobación por monto"),
])


class Inc7dWalk(SyncCase):
    PID = PID

    @classmethod
    def build_workspace(cls) -> None:
        super().build_workspace()
        Path("respuestas.md").write_text(ANSWERS, encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", "respuestas.md", "--change", CID])
        run_ok(["brief", PID, "--change", CID])

    def base(self) -> Path:
        return workspace_path(PID)

    def stories(self, rid: str) -> list[str]:
        return sorted(p.stem for p in (self.base() / "04_backlog" / CID / rid).glob("US-*.md"))

    def test_walk(self) -> None:
        run_ok(["split", PID, "--propose", "--source", str(INC7 / "propuesta_serie_cambio.json"), "--change", CID])
        run_ok(["split", PID, "--confirm", "--ba", "Ana", "--tech", "Equipo", "--change", CID])
        specs1 = json.loads(run_ok(["specs", PID, "--change", CID, "--release", "r1"]))
        self.assertEqual(specs1["release"], "r1")
        run_ok(["backlog", PID, "--change", CID, "--release", "r1"])
        mine = self.stories("r1")
        self.assertTrue(mine)
        evidence = Path("evidencia.md")
        evidence.write_text("Evidencia sintetica de r1.\n", encoding="utf-8")
        for sid in mine:
            for status in ("Ready", "In Progress", "In Review"):
                run_ok(["story-status", PID, "--story", sid, "--set", status])
            run_ok(["story-status", PID, "--story", sid, "--set", "Done", "--evidence", str(evidence)])
        run_ok(["split", PID, "--close", "r1", "--evidence", str(evidence), "--ba", "Ana", "--tech", "Equipo", "--change", CID])
        run_ok(["specs", PID, "--change", CID, "--release", "r2"])
        folder = self.base() / "03_specs" / CID
        text = (folder / "r2" / "specs.md").read_text(encoding="utf-8")
        block = text.split("## Comportamiento preservado", 1)[1]
        for uid in specs1["units"]:
            self.assertIn(uid, block)  # r1 stays preserved, never a unit of r2
            self.assertFalse((folder / "r2" / "units" / f"{uid}.md").exists())
        self.assertTrue((folder / "r1" / "specs.md").is_file())  # and r1's own derivation is kept
        run_ok(["view", PID, "--artifact", "release-guide", "--change", CID])
        guide = (self.base() / "02_requirements" / CID / "series" / "release-guide.md").read_text(encoding="utf-8")
        rows = {line.split("|")[1].split()[0]: line for line in guide.splitlines() if re.match(r"^\| r\d", line)}
        self.assertIn("cerrado", rows["r1"])
        self.assertIn("abierto", rows["r2"])
        self.assertTrue((self.base() / "08_context_packs" / "views" / f"{CID}-release-guide.html").is_file())
        forget_read_snapshots()


if __name__ == "__main__":
    unittest.main()
