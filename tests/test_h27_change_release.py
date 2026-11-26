"""IMP-429 (H27 inc 7d) task 1: the units of a change split by release, and `/specs --change --release rN`.

The series of a change (7c) is confirmed; `change_release.release_units` gives each `SPEC-U` unit of the change to
exactly one release, and `/specs P --change CHG --release rN` writes that release's units under `03_specs/CHG/rN/`.
The project's own `--release` output does not move a byte (RF 4).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from helpers import SyncCase, run_ok  # noqa: E402
from release_project_flow import release_output_hashes, run_release_flow  # noqa: E402

from sentinel.cli import main  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = "CREL"
CID = "CHG-001"
INC7 = ROOT / "fixtures" / "change_inc7"
BASELINE = json.loads((INC7 / "release_project_sha256.json").read_text(encoding="utf-8"))


def _answer(gap: str, text: str, delta: str, surface: str) -> str:
    return (f"### {gap}\n- Respuesta: {text}\n- Owner / fuente: Jefa de Compras\n- Delta: {delta}\n"
            f"- Superficie: {surface}\n- Estado de decisión: confirmado\n")


# four answers, four units: each one names one surface of the proposal's two releases
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


def cli(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(argv)
    return code, out.getvalue()


class ChangeReleaseCase(SyncCase):
    PID = PID

    @classmethod
    def build_workspace(cls) -> None:
        super().build_workspace()
        Path("respuestas.md").write_text(ANSWERS, encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", "respuestas.md", "--change", CID])
        run_ok(["brief", PID, "--change", CID])
        run_ok(["split", PID, "--propose", "--source", str(INC7 / "propuesta_serie_cambio.json"), "--change", CID])
        run_ok(["split", PID, "--confirm", "--ba", "Ana", "--tech", "Equipo", "--change", CID])

    def base(self) -> Path:
        return workspace_path(PID)

    def units_by_surface(self) -> dict[str, str]:
        """surface -> SPEC-U id, from the change's own units (compiled by `/specs --change`)."""
        found = {}
        for path in sorted((self.base() / "03_specs" / CID / "units").glob("SPEC-U-*.md")):
            match = re.search(r"surfaces:\n((?:  - .*\n)+)", path.read_text(encoding="utf-8"))
            for line in match.group(1).splitlines():
                found[line[4:].strip()] = path.stem
        return found

    def edit_surface(self, ears: str, surfaces: str) -> None:
        """Rewrite the surfaces cell of a REQ-EARS row (the units are compiled from this file)."""
        path = self.base() / "02_requirements" / CID / "requirements.md"
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if line.startswith(f"| {ears} |"):
                cells = line.strip(" |").split(" | ")
                cells[6] = surfaces
                lines[index] = "| " + " | ".join(cells) + " |"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        forget_read_snapshots()


class ReleaseUnitsTest(ChangeReleaseCase):
    def test_release_units_partition(self) -> None:
        from sentinel.change_release import release_units

        run_ok(["specs", PID, "--change", CID])
        by_surface = self.units_by_surface()
        found = release_units(PID, CID)
        self.assertEqual(list(found), ["r1", "r2"])
        every = [uid for ids in found.values() for uid in ids]
        self.assertEqual(sorted(every), sorted(set(by_surface.values())))  # each unit in exactly one list
        self.assertEqual(sorted(found["r1"]), sorted([by_surface["Alta de proveedores"], by_surface["Tabla de proveedores"]]))
        self.assertEqual(sorted(found["r2"]), sorted([by_surface["Bandeja de aprobaciones"], by_surface["Aprobación por monto"]]))

    def test_unit_owned_twice_or_never_refused(self) -> None:
        from sentinel.change_release import ChangeReleaseError, release_units

        run_ok(["specs", PID, "--change", CID])
        self.edit_surface("REQ-EARS-002", "Alta de proveedores; Bandeja de aprobaciones")
        code, out = cli(["specs", PID, "--change", CID, "--release", "r1"])
        self.assertEqual(code, 3, out)
        for needle in ("SPEC-U-002", "r1", "r2", f"/split {PID} --change {CID} --move"):
            self.assertIn(needle, out)
        self.assertFalse((self.base() / "03_specs" / CID / "r1").exists())
        with self.assertRaises(ChangeReleaseError):
            release_units(PID, CID)
        self.edit_surface("REQ-EARS-002", "Superficie ajena")
        code, out = cli(["specs", PID, "--change", CID, "--release", "r1"])
        self.assertEqual(code, 3, out)
        self.assertIn("SPEC-U-002", out)
        self.assertIn("ninguna release", out)
        self.assertFalse((self.base() / "03_specs" / CID / "r1").exists())

    def test_specs_release_change(self) -> None:
        from sentinel.change_release import release_units

        result = json.loads(run_ok(["specs", PID, "--change", CID, "--release", "r1"]))
        self.assertEqual(result["release"], "r1")
        expected = release_units(PID, CID)["r1"]
        self.assertEqual(result["units"], expected)
        folder = self.base() / "03_specs" / CID
        written = sorted(p.stem for p in (folder / "r1" / "units").glob("SPEC-U-*.md"))
        self.assertEqual(written, sorted(expected))
        for uid in expected:
            self.assertEqual((folder / "r1" / "units" / f"{uid}.md").read_bytes(), (folder / "units" / f"{uid}.md").read_bytes())
        self.assertTrue((folder / "r1" / "specs.md").is_file())
        self.assertFalse((folder / "r2").exists())

    def test_other_commands_still_refuse(self) -> None:
        for command in ("validate", "next", "status"):
            code, out = cli([command, PID, "--change", CID, "--release", "r1"])
            self.assertNotEqual(code, 0, command)
            self.assertIn(f"--release con --change existe para /specs y /backlog; para el resto corré /{command} {PID} --change {CID}", out)


def _story_files(folder: Path) -> dict[str, str]:
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(folder.glob("US-*.md"))}


def _sha_tree(base: Path, folder: str, pattern: str) -> dict[str, str]:
    import hashlib

    return {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((base / folder).glob(pattern)) if p.is_file()}


class ReleaseBacklogTest(ChangeReleaseCase):
    def _derive_specs(self) -> None:
        for rid in ("r1", "r2"):
            run_ok(["specs", PID, "--change", CID, "--release", rid])

    def test_backlog_release_change(self) -> None:
        from sentinel.change_release import release_units

        self._derive_specs()
        owned = release_units(PID, CID)
        first = json.loads(run_ok(["backlog", PID, "--change", CID, "--release", "r1"]))
        second = json.loads(run_ok(["backlog", PID, "--change", CID, "--release", "r2"]))
        self.assertEqual(first["release"], "r1")
        folder = self.base() / "04_backlog" / CID
        mine = {}
        for rid in ("r1", "r2"):
            mine[rid] = _story_files(folder / rid)
            self.assertTrue(mine[rid], rid)
            self.assertTrue((folder / rid / "SLICE-PLAN.md").is_file())
            other = [u for r, ids in owned.items() if r != rid for u in ids]
            for sid, text in mine[rid].items():
                for uid in other:
                    self.assertNotIn(uid, text, f"{sid} in {rid} cites {uid}")
            cited = {u for t in mine[rid].values() for u in re.findall(r"SPEC-U-\d+", t)}
            self.assertTrue(cited and cited <= set(owned[rid]), (rid, cited))
        self.assertEqual(sorted(first["stories"]), sorted(mine["r1"]))
        self.assertEqual(sorted(second["stories"]), sorted(mine["r2"]))
        self.assertFalse(set(mine["r1"]) & set(mine["r2"]))

    def test_backlog_release_needs_specs(self) -> None:
        run_ok(["specs", PID, "--change", CID, "--release", "r1"])
        code, out = cli(["backlog", PID, "--change", CID, "--release", "r2"])
        self.assertNotEqual(code, 0, out)
        self.assertIn(f"/specs {PID} --change {CID} --release r2", out)
        self.assertFalse((self.base() / "04_backlog" / CID / "r2").exists())

    def test_rerun_keeps_other_release(self) -> None:
        self._derive_specs()
        run_ok(["backlog", PID, "--change", CID, "--release", "r1"])
        run_ok(["backlog", PID, "--change", CID, "--release", "r2"])
        before = {rid: _story_files(self.base() / "04_backlog" / CID / rid) for rid in ("r1", "r2")}
        run_ok(["backlog", PID, "--change", CID, "--release", "r2"])
        after = {rid: _story_files(self.base() / "04_backlog" / CID / rid) for rid in ("r1", "r2")}
        self.assertEqual(sorted(before["r1"]), sorted(after["r1"]))
        self.assertEqual(sorted(before["r2"]), sorted(after["r2"]))
        for sid in before["r1"]:
            self.assertTrue((self.base() / "04_backlog" / f"{sid}.md").is_file())

    def test_release_derivation_isolated(self) -> None:
        """RF 3: deriving CHG-001's releases touches nothing of the project or of another change."""
        Path("otro.md").write_text("Pedido: sumar un reporte de compras mensual para la jefatura.\n", encoding="utf-8")
        run_ok(["ingest", PID, "--source", "otro.md", "--change"])
        base = self.base()
        before_project = _sha_tree(base, "04_backlog", "US-*.md")
        before_other = _sha_tree(base, "03_specs/CHG-002", "**/*")
        before_req = _sha_tree(base, "02_requirements/CHG-002", "**/*")
        self._derive_specs()
        for rid in ("r1", "r2"):
            run_ok(["backlog", PID, "--change", CID, "--release", rid])
        self.assertFalse((base / "03_specs" / "r1").exists())
        self.assertFalse((base / "04_backlog" / "r1").exists())
        self.assertFalse((base / ".series_work").exists())
        after = _sha_tree(base, "04_backlog", "US-*.md")
        own = {k for k in after if f"change: {CID}" not in (base / k).read_text(encoding="utf-8")}
        self.assertEqual({k: after[k] for k in own}, {k: before_project[k] for k in own})
        self.assertEqual(_sha_tree(base, "03_specs/CHG-002", "**/*"), before_other)
        self.assertEqual(_sha_tree(base, "02_requirements/CHG-002", "**/*"), before_req)

    def test_change_backlog_without_release_unchanged(self) -> None:
        run_ok(["specs", PID, "--change", CID])
        run_ok(["backlog", PID, "--change", CID])
        base = self.base()
        stories = _story_files(base / "04_backlog")
        mine = {sid for sid, t in stories.items() if f"change: {CID}" in t}
        self.assertTrue(mine)
        self.assertTrue((base / "04_backlog" / CID / "SLICE-PLAN.md").is_file())
        self.assertFalse((base / "04_backlog" / CID / "r1").exists())
        first = {sid: stories[sid] for sid in mine}
        run_ok(["backlog", PID, "--change", CID])
        again = _story_files(base / "04_backlog")
        self.assertEqual({sid: again[sid] for sid in mine}, first)


class ProjectReleaseBytesTest(unittest.TestCase):
    def test_project_release_bytes_unchanged(self) -> None:
        """RF 4: the project's specs/backlog/close/move write the bytes recorded before this increment."""
        old = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            try:
                run_release_flow(work)
                found = release_output_hashes(work)
            finally:
                os.chdir(old)
        self.assertEqual(found, BASELINE)


if __name__ == "__main__":
    unittest.main()
