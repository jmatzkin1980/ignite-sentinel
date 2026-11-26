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
from unittest.mock import patch

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


def _release_ids(folder: Path) -> list[str]:
    """The stories a release lists in `04_backlog/CHG/rN/stories.md` (I3 of the 7d review: an index, never copies)."""
    index = folder / "stories.md"
    return sorted(set(re.findall(r"\[(US-\d+)\]\(\.\./\.\./US-\d+\.md\)", index.read_text(encoding="utf-8")))) if index.is_file() else []


def _story_files(folder: Path) -> dict[str, str]:
    """Story id -> text: the canonical stories a release folder lists, or the `US-*.md` files of a plain folder."""
    if folder.parent.name.startswith("CHG-"):
        backlog = folder.parent.parent
        return {sid: (backlog / f"{sid}.md").read_text(encoding="utf-8") for sid in _release_ids(folder)}
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

    def test_epic_lists_every_derived_release(self) -> None:
        """Controller ruling: EPIC-CHG-nnn lists the stories of every derived release, refreshed on each derivation."""
        self._derive_specs()
        run_ok(["backlog", PID, "--change", CID, "--release", "r1"])
        epic = self.base() / "04_backlog" / "EPIC-CHG-001.md"
        first = epic.read_text(encoding="utf-8")
        mine1 = sorted(_story_files(self.base() / "04_backlog" / CID / "r1"))
        self.assertTrue(all(f"`{sid}`" in first for sid in mine1))
        run_ok(["backlog", PID, "--change", CID, "--release", "r2"])
        second = epic.read_text(encoding="utf-8")
        mine2 = sorted(_story_files(self.base() / "04_backlog" / CID / "r2"))
        self.assertTrue(mine2)
        for sid in (*mine1, *mine2):
            self.assertIn(f"`{sid}`", second, sid)
        self.assertLess(second.index(f"`{mine1[0]}`"), second.index(f"`{mine2[0]}`"))  # release order
        run_ok(["backlog", PID, "--change", CID, "--release", "r1"])  # a rerun of r1 keeps r2's rows
        again = epic.read_text(encoding="utf-8")
        for sid in (*mine1, *mine2):
            self.assertIn(f"`{sid}`", again, sid)

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

    def without_series(self, *argvs: list[str]) -> None:
        """Run commands as a change of 0.37 did before its series was confirmed (the partition set aside, then put back)."""
        partition = self.base() / "02_requirements" / CID / "series" / "partition.json"
        kept = partition.read_bytes()
        partition.unlink()
        forget_read_snapshots()
        try:
            for argv in argvs:
                run_ok(argv)
        finally:
            partition.write_bytes(kept)
            forget_read_snapshots()

    def change_stories(self) -> dict[str, str]:
        return {sid: t for sid, t in _story_files(self.base() / "04_backlog").items() if f"change: {CID}" in t}

    def test_change_backlog_without_release_unchanged(self) -> None:
        """A change with no confirmed series keeps the plain /backlog --change (same stories on a rerun)."""
        self.without_series(["specs", PID, "--change", CID], ["backlog", PID, "--change", CID])
        base = self.base()
        first = self.change_stories()
        self.assertTrue(first)
        self.assertTrue((base / "04_backlog" / CID / "SLICE-PLAN.md").is_file())
        self.assertFalse((base / "04_backlog" / CID / "r1").exists())
        self.without_series(["backlog", PID, "--change", CID])
        self.assertEqual(self.change_stories(), first)

    def test_plain_backlog_refused_once_series_confirmed(self) -> None:
        """I2: with a confirmed series a plain /backlog --change would delete or duplicate the release stories."""
        self._derive_specs()
        run_ok(["backlog", PID, "--change", CID, "--release", "r1"])
        run_ok(["backlog", PID, "--change", CID, "--release", "r2"])
        before = self.change_stories()
        code, out = cli(["backlog", PID, "--change", CID])
        self.assertNotEqual(code, 0, out)
        self.assertIn(f"/backlog {PID} --change {CID} --release r1", out)
        self.assertEqual(self.change_stories(), before)

    def test_release_backlog_adopts_plain_stories(self) -> None:
        """I2: a 0.37 change with a plain backlog and a confirmed series: the release derivation reuses its stories."""
        from sentinel.change_release import release_units

        self.without_series(["specs", PID, "--change", CID], ["backlog", PID, "--change", CID])
        plain = self.change_stories()
        busy = sorted(plain)[0]
        for status in ("Ready", "In Progress"):
            run_ok(["story-status", PID, "--story", busy, "--set", status])
        self._derive_specs()
        run_ok(["backlog", PID, "--change", CID, "--release", "r1"])
        run_ok(["backlog", PID, "--change", CID, "--release", "r2"])
        stories = self.change_stories()
        self.assertIn(busy, stories)  # a story in progress keeps its id
        covered: dict[str, list[str]] = {}
        for sid, text in stories.items():
            for uid in set(re.findall(r"SPEC-U-\d+", text.split("---", 2)[1])):
                covered.setdefault(uid, []).append(sid)
        owned = release_units(PID, CID)
        for uid in (u for ids in owned.values() for u in ids):
            self.assertEqual(len(covered.get(uid, [])), 1, (uid, covered))
        listed = [sid for rid in ("r1", "r2") for sid in _release_ids(self.base() / "04_backlog" / CID / rid)]
        self.assertEqual(sorted(listed), sorted(stories))
        self.assertEqual(len(listed), len(set(listed)))

    def test_release_folder_holds_an_index_not_copies(self) -> None:
        """I3: `04_backlog/CHG/rN/` lists its stories with links to the canonical files; a status change never drifts."""
        self._derive_specs()
        result = json.loads(run_ok(["backlog", PID, "--change", CID, "--release", "r1"]))
        folder = self.base() / "04_backlog" / CID / "r1"
        self.assertFalse(list(folder.glob("US-*.md")))
        self.assertTrue((folder / "SLICE-PLAN.md").is_file())
        self.assertEqual(_release_ids(folder), sorted(result["stories"]))
        sid = sorted(result["stories"])[0]
        run_ok(["story-status", PID, "--story", sid, "--set", "Ready"])
        from sentinel.release_guide import release_stories

        self.assertEqual(release_stories(self.base(), PID, "r1", CID)[sid], "Ready")


class ReleaseFlowCase(ChangeReleaseCase):
    def derive(self, *rids: str) -> None:
        for rid in rids:
            run_ok(["specs", PID, "--change", CID, "--release", rid])
            run_ok(["backlog", PID, "--change", CID, "--release", rid])

    def stories(self, rid: str) -> list[str]:
        return _release_ids(self.base() / "04_backlog" / CID / rid)

    def finish(self, rid: str) -> Path:
        evidence = Path("evidencia.md")
        evidence.write_text(f"Evidencia sintetica de {rid}.\n", encoding="utf-8")
        for sid in self.stories(rid):
            for status in ("Ready", "In Progress", "In Review"):
                run_ok(["story-status", PID, "--story", sid, "--set", status])
            run_ok(["story-status", PID, "--story", sid, "--set", "Done", "--evidence", str(evidence)])
        return evidence

    def close(self, rid: str, evidence: Path) -> tuple[int, str]:
        return cli(["split", PID, "--close", rid, "--evidence", str(evidence), "--ba", "Ana", "--tech", "Equipo",
                    "--change", CID])

    def partition(self) -> bytes:
        return (self.base() / "02_requirements" / CID / "series" / "partition.json").read_bytes()


class ReleaseCloseTest(ReleaseFlowCase):
    def test_close_requires_done_stories(self) -> None:
        self.derive("r1")
        evidence = Path("evidencia.md")
        evidence.write_text("Evidencia sintetica.\n", encoding="utf-8")
        before = self.partition()
        code, out = self.close("r1", evidence)
        self.assertNotEqual(code, 0, out)
        for sid in self.stories("r1"):
            self.assertIn(sid, out)
        self.assertIn("Done", out)
        self.assertEqual(self.partition(), before)
        code, out = self.close("r2", evidence)  # not derived: nothing to close
        self.assertNotEqual(code, 0, out)
        self.assertEqual(self.partition(), before)

    def test_closed_units_preserved_not_redelivered(self) -> None:
        from sentinel.change_release import ChangeReleaseError, release_units

        self.derive("r1")
        owned = release_units(PID, CID)
        evidence = self.finish("r1")
        code, out = self.close("r1", evidence)
        self.assertEqual(code, 0, out)
        run_ok(["specs", PID, "--change", CID, "--release", "r2"])
        folder = self.base() / "03_specs" / CID / "r2"
        specs = (folder / "specs.md").read_text(encoding="utf-8")
        self.assertIn("## Comportamiento preservado", specs)
        block = specs.split("## Comportamiento preservado")[1]
        for uid in owned["r1"]:
            self.assertIn(uid, block)
            self.assertFalse((folder / "units" / f"{uid}.md").exists(), uid)
        self.assertIn("entregado en r1", block)
        self.assertEqual(sorted(p.stem for p in (folder / "units").glob("SPEC-U-*.md")), sorted(owned["r2"]))
        forget_read_snapshots()
        with self.assertRaises(ChangeReleaseError) as caught:
            from sentinel.compilers.change_specs import compile_change_specs

            compile_change_specs(PID, CID, release="r1")
        self.assertIn("r1 está cerrada", str(caught.exception))
        code, out = cli(["specs", PID, "--change", CID, "--release", "r1"])
        self.assertNotEqual(code, 0, out)
        self.assertIn("r1 está cerrada", out)

    def test_change_guide_shows_progress(self) -> None:
        self.derive("r1")
        evidence = self.finish("r1")
        code, out = self.close("r1", evidence)
        self.assertEqual(code, 0, out)
        guide = (self.base() / "02_requirements" / CID / "series" / "release-guide.md").read_text(encoding="utf-8")
        rows = {line.split("|")[1].split()[0]: line for line in guide.splitlines() if line.startswith("| r")}
        self.assertIn("cerrado", rows["r1"])
        self.assertIn("abierto", rows["r2"])
        self.assertNotIn("todavía no se derivan", guide)
        self.assertIn(f"/specs {PID} --change {CID} --release r2", rows["r2"])


class SeriesWalkTest(ReleaseFlowCase):
    def step(self) -> dict:
        """/next of the change as if its request were already extracted, crossed and exported (that part has its own walks)."""
        forget_read_snapshots()
        with patch("sentinel.readiness_verdict._change_prep_key", return_value=""):
            return json.loads(run_ok(["next", PID, "--change", CID]))

    def test_move_within_change_series(self) -> None:
        from sentinel.change_release import release_units

        self.derive("r1", "r2")
        before = release_units(PID, CID)
        by_surface = self.units_by_surface()
        unit = by_surface["Tabla de proveedores"]
        self.assertIn(unit, before["r1"])
        code, out = cli(["split", PID, "--move", "--unit", "Tabla de proveedores", "--from", "r1", "--to", "r2",
                         "--reason", "La tabla depende de la bandeja", "--ba", "Ana", "--tech", "Equipo", "--change", CID])
        self.assertEqual(code, 0, out)
        series = self.base() / "02_requirements" / CID / "series"
        changes = json.loads((series / "scope_changes.json").read_text(encoding="utf-8"))["changes"]
        self.assertEqual([(c["from"], c["to"]) for c in changes], [("r1", "r2")])
        forget_read_snapshots()
        after = release_units(PID, CID)
        self.assertNotIn(unit, after["r1"])
        self.assertIn(unit, after["r2"])
        self.assertFalse((self.base() / "02_requirements" / "series").exists())
        found = json.loads(out[out.index("{"):])
        self.assertEqual(sorted(found["stale_derivations"]), ["r1", "r2"])
        step = self.step()
        self.assertEqual(step["key"], "specs")
        self.assertEqual(step["command"], f"/specs {PID} --change {CID} --release r1")
        run_ok(["specs", PID, "--change", CID, "--release", "r1"])
        self.assertEqual(self.step()["command"], f"/backlog {PID} --change {CID} --release r1")  # its stories are the old ones
        run_ok(["backlog", PID, "--change", CID, "--release", "r1"])
        step = self.step()  # r1 is whole again
        self.assertEqual(step["key"], "done")
        self.assertIn("--close r1", step["text"])

    def test_move_refuses_a_closed_release(self) -> None:
        self.derive("r1")
        evidence = self.finish("r1")
        self.assertEqual(self.close("r1", evidence)[0], 0)
        before = self.partition()
        code, out = cli(["split", PID, "--move", "--unit", "Aprobación por monto", "--from", "r2", "--to", "r1",
                         "--reason", "x", "--ba", "Ana", "--tech", "Equipo", "--change", CID])
        self.assertNotEqual(code, 0, out)
        self.assertIn("r1", out)
        self.assertIn("cerrada", out)
        self.assertEqual(self.partition(), before)

    def test_next_walks_series_once(self) -> None:
        """RF 5: specs r1, backlog r1, close r1, specs r2, backlog r2, close r2, then today's done; never a repeat."""
        seen = []
        evidence = Path("evidencia.md")
        evidence.write_text("Evidencia sintetica.\n", encoding="utf-8")
        for rid in ("r1", "r2"):
            step = self.step()
            self.assertEqual((step["key"], step["command"]), ("specs", f"/specs {PID} --change {CID} --release {rid}"), seen)
            seen.append(step["command"])
            run_ok(["specs", PID, "--change", CID, "--release", rid])
            step = self.step()
            self.assertEqual((step["key"], step["command"]), ("backlog", f"/backlog {PID} --change {CID} --release {rid}"))
            seen.append(step["command"])
            run_ok(["backlog", PID, "--change", CID, "--release", rid])
            step = self.step()
            self.assertEqual(step["key"], "done")
            self.assertEqual(step["command"], "")  # M5: the close is not a command while stories are not Done
            self.assertIn(f"--close {rid}", step["text"])
            self.finish(rid)
            step = self.step()
            self.assertEqual(step["command"], f"/split {PID} --change {CID} --close {rid}")
            seen.append(step["command"])
            code, out = self.close(rid, evidence)
            self.assertEqual(code, 0, out)
        step = self.step()
        self.assertEqual(self.step(), step)  # asked again, the same answer, not a new instruction
        self.assertEqual(step["key"], "done", step)
        self.assertEqual(step["command"], "")
        self.assertNotIn("--close", step["text"])
        self.assertEqual(len(seen), len(set(seen)))

    def test_close_makes_a_later_derivation_stale(self) -> None:
        """I1: r2 derived before r1 closes lacks r1's preserved rows: /next and /validate ask to derive r2 again."""
        self.derive("r1", "r2")
        evidence = self.finish("r1")
        code, out = self.close("r1", evidence)
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out[out.index("{"):])["stale_derivations"], ["r2"])
        step = self.step()
        self.assertEqual((step["key"], step["command"]), ("specs", f"/specs {PID} --change {CID} --release r2"))
        self.assertIn("r1", step["text"])
        forget_read_snapshots()
        code, out = cli(["validate", PID, "--change", CID])
        found = json.loads(out[out.index("{"):])
        series = [c for c in found["checks"] if c["id"] == "release_series"][0]
        self.assertEqual(series["status"], "FAIL", found)
        self.assertIn(f"/specs {PID} --change {CID} --release r2", series["detail"])
        run_ok(["specs", PID, "--change", CID, "--release", "r2"])
        self.assertIn("entregado en r1", (self.base() / "03_specs" / CID / "r2" / "specs.md").read_text(encoding="utf-8"))
        step = self.step()
        self.assertEqual((step["key"], step["command"]), ("backlog", f"/backlog {PID} --change {CID} --release r2"))
        run_ok(["backlog", PID, "--change", CID, "--release", "r2"])
        self.assertEqual(self.step()["key"], "done")

    def test_close_refuses_a_release_whose_derivation_is_old(self) -> None:
        """I4: a unit moved into r1 after its backlog has no story: r1 does not close until it is derived again."""
        self.derive("r1")
        evidence = self.finish("r1")
        code, out = cli(["split", PID, "--move", "--unit", "Bandeja de aprobaciones", "--from", "r2", "--to", "r1",
                         "--reason", "la bandeja va con el alta", "--ba", "Ana", "--tech", "Equipo", "--change", CID])
        self.assertEqual(code, 0, out)
        forget_read_snapshots()
        before = self.partition()
        code, out = self.close("r1", evidence)
        self.assertNotEqual(code, 0, out)
        self.assertIn(f"/specs {PID} --change {CID} --release r1", out)
        self.assertEqual(self.partition(), before)

    def test_backlog_of_a_closed_release_refused(self) -> None:
        """M1: /backlog --release of a closed release refuses like /specs does."""
        self.derive("r1")
        evidence = self.finish("r1")
        self.assertEqual(self.close("r1", evidence)[0], 0)
        plan = (self.base() / "04_backlog" / CID / "r1" / "SLICE-PLAN.md").read_bytes()
        code, out = cli(["backlog", PID, "--change", CID, "--release", "r1"])
        self.assertNotEqual(code, 0, out)
        self.assertIn("r1 está cerrada", out)
        self.assertEqual((self.base() / "04_backlog" / CID / "r1" / "SLICE-PLAN.md").read_bytes(), plan)

    def test_release_closed_out_of_order_is_preserved(self) -> None:
        """M3: a release closed before an earlier one reads as preserved in that earlier release."""
        from sentinel.change_release import release_units

        self.derive("r2")
        evidence = self.finish("r2")
        self.assertEqual(self.close("r2", evidence)[0], 0)
        run_ok(["specs", PID, "--change", CID, "--release", "r1"])
        specs = (self.base() / "03_specs" / CID / "r1" / "specs.md").read_text(encoding="utf-8")
        self.assertIn("entregado en r2", specs)
        for uid in release_units(PID, CID)["r2"]:
            self.assertIn(uid, specs.split("## Comportamiento preservado")[1])

    def test_specs_refuses_a_bad_release_before_compiling(self) -> None:
        """M2: a release the series does not have refuses before the change-level units are rewritten."""
        from sentinel.change_release import ChangeReleaseError
        from sentinel.compilers.change_specs import compile_change_specs

        with patch("sentinel.compilers.change_specs._compile_change_specs", side_effect=AssertionError("compiled")):
            with self.assertRaises(ChangeReleaseError):
                compile_change_specs(PID, CID, release="r9")

    def test_containment_match_is_reported(self) -> None:
        """M4: a unit owned only because its surface is contained in a quote says so in the result."""
        run_ok(["specs", PID, "--change", CID])
        self.edit_surface("REQ-EARS-003", "Bandeja")
        result = json.loads(run_ok(["specs", PID, "--change", CID, "--release", "r2"]))
        self.assertTrue(result["containment"], result)
        self.assertEqual(result["containment"][0]["release"], "r2")
        self.assertEqual(result["containment"][0]["surface"], "Bandeja")

    def test_next_names_the_release_when_stories_are_not_done(self) -> None:
        self.derive("r1")
        step = self.step()
        self.assertEqual(step["key"], "done")
        self.assertIn("r1", step["text"])
        self.assertIn("Done", step["text"])


class SeriesRefreshAndValidateTest(ReleaseFlowCase):
    """M5 of the 7c review: a change's series follows its text, and /validate --change reports the series."""

    def series(self) -> Path:
        return self.base() / "02_requirements" / CID / "series"

    def validate(self) -> tuple[int, dict]:
        forget_read_snapshots()
        code, out = cli(["validate", PID, "--change", CID])
        return code, json.loads(out[out.index("{"):])

    def test_series_refreshes_when_the_change_text_changes(self) -> None:
        run_ok(["specs", PID, "--change", CID])
        before = (self.series() / "series_map.json").read_bytes()
        Path("mas.md").write_text(_answer("GAP-BACKEND-SURFACE", "Cuando el comprador completa el alta, el sistema debe guardar y notificar al proveedor.",
                                          "MODIFIED", "Alta de proveedores"), encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", "mas.md", "--change", CID])
        run_ok(["brief", PID, "--change", CID])
        forget_read_snapshots()
        self.assertNotEqual((self.series() / "series_map.json").read_bytes(), before)
        code, found = self.validate()
        self.assertFalse([f for f in found["findings"] if "desactualizada" in f], found["findings"])

    def test_confirmed_series_validates_clean(self) -> None:
        """C1: an open gap with no owner reads `sin dato registrado` in the release briefs, never a bare `-`."""
        from sentinel.release_series import series_validation_findings

        run_ok(["specs", PID, "--change", CID])
        self.assertEqual(series_validation_findings(self.base(), CID), [])
        for rid in ("r1", "r2"):
            brief = (self.series().parent / rid / "project-brief.md").read_text(encoding="utf-8")
            self.assertNotRegex(brief, r"(?m)\|\s*-\s*\|\s*$")
            self.assertIn("sin dato registrado", brief)
        code, found = self.validate()
        series = [c for c in found["checks"] if c["id"] == "release_series"]
        self.assertEqual(series[0]["status"], "PASS", found)

    def test_validate_reports_a_stale_series(self) -> None:
        run_ok(["specs", PID, "--change", CID])
        code, found = self.validate()
        self.assertFalse([f for f in found["findings"] if "desactualizada" in f], found["findings"])  # a fresh series is not stale
        path = self.series() / "series_map.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["brief_sha256"] = "0" * 64
        path.write_text(json.dumps(data), encoding="utf-8")
        code, found = self.validate()
        self.assertEqual(found["verdict"], "INVALID")
        series = [c for c in found["checks"] if c["id"] == "release_series"]
        self.assertEqual(series[0]["status"], "FAIL", found)
        self.assertIn("desactualizada", series[0]["detail"])

    def test_validate_reports_a_unit_owned_twice_or_never(self) -> None:
        run_ok(["specs", PID, "--change", CID])
        self.edit_surface("REQ-EARS-002", "Alta de proveedores; Bandeja de aprobaciones")
        run_ok(["specs", PID, "--change", CID])
        code, found = self.validate()
        series = [c for c in found["checks"] if c["id"] == "release_series"]
        self.assertEqual(series[0]["status"], "FAIL", found)
        for needle in ("SPEC-U-002", "r1", "r2"):
            self.assertIn(needle, series[0]["detail"])
        self.edit_surface("REQ-EARS-002", "Superficie ajena")
        run_ok(["specs", PID, "--change", CID])
        code, found = self.validate()
        series = [c for c in found["checks"] if c["id"] == "release_series"]
        self.assertIn("ninguna release", series[0]["detail"])


class ProjectCloseTextTest(unittest.TestCase):
    def test_project_close_message_unchanged(self) -> None:
        """I5: the project's "no stories yet" refusal is the text of 36f3a19, byte for byte."""
        from sentinel.release_guide import close_release
        from sentinel.release_split import ReleaseSplitError

        with tempfile.TemporaryDirectory() as tmp:
            proof = Path(tmp) / "evidence.md"
            proof.write_text("x\n", encoding="utf-8")
            with patch("sentinel.release_guide._series", return_value=({"releases": ["r1"]}, {})), \
                    patch("sentinel.release_guide.release_stories", return_value={}), \
                    patch("sentinel.core.paths.workspace_path", return_value=Path(tmp)):
                with self.assertRaises(ReleaseSplitError) as caught:
                    close_release("P", "r1", str(proof), "Ana", "Equipo")
        self.assertEqual(str(caught.exception),
                         "r1 has no stories yet: derive it (/specs, /backlog --release r1) and build it before closing")


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
