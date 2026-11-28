"""IMP-435 (H27 inc 9a) task 5: the series of an extracted change validates and each new unit has a route (B-03, B-04, B-07)."""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import class_deferred, complete_extraction, run_cli, run_ok  # noqa: E402
from test_h26_cross_record import CID, PID  # noqa: E402
from test_h27_consolidated_export import FinalCase  # noqa: E402

from sentinel.cli import main  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

INC7 = Path(__file__).resolve().parent / "fixtures" / "change_inc7"
SAD = Path(__file__).resolve().parent / "fixtures" / "change_baseline" / "sad-compras.md"
BA = ["--ba", "Ana", "--tech", "Equipo"]


def run_all(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def _answer(gap: str, text: str, delta: str, surface: str) -> str:
    return (f"### {gap}\n- Respuesta: {text}\n- Owner / fuente: Jefa de Compras\n- Delta: {delta}\n"
            f"- Superficie: {surface}\n- Estado de decisión: confirmado\n")


class SeriesCase(FinalCase):
    def reach_final(self) -> None:
        """The consolidated change, extracted, with its final brief sealed (the path of B-03)."""
        self.apply()
        run_ok(["sources", PID, "--load", str(SAD), "--role", "linea_de_base", "--change", CID])
        self.answer_rows("base.md", "GAP-BACKEND-SURFACE", "MODIFIED", "Alta de proveedores",
                         "Cuando el analista completa el alta, el sistema debe guardar el proveedor.")
        complete_extraction(PID, CID, skip=("RN-02", "RN-06"))
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-item", "HU-03"])
        result = self.submit_text("\n".join([
            "### PD-01", f"- Decisión: {self.dis}", f"- Líneas: {self.lines_of('PD-01')}",
            "- Texto: El umbral de aprobación se configura por parámetro y arranca en 1.000.000.", ""]), "pd.md")
        self.assertEqual(result["recorded"], ["PD-01"], result)
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "PD-01"])
        forget_read_snapshots()
        run_ok(["brief", PID, "--change", CID])
        class_deferred(PID, CID)
        forget_read_snapshots()
        code, out = run_cli(["export", PID, "--artifact", "brief", "--change", CID, "--final"])
        self.assertEqual(code, 0, (out, run_cli(["next", PID, "--change", CID])[1]))
        forget_read_snapshots()

    def answer_rows(self, name: str, gap: str, delta: str, surface: str, text: str) -> None:
        path = Path.cwd() / name
        path.write_text(_answer(gap, text, delta, surface), encoding="utf-8")
        forget_read_snapshots()
        run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID])
        forget_read_snapshots()

    def unit_ids(self) -> set[str]:
        return {p.stem for p in (workspace_path(PID) / "03_specs" / CID / "units").glob("SPEC-U-*.md")}

    def confirmed(self) -> None:
        self.reach_final()
        run_ok(["split", PID, "--propose", "--source", str(INC7 / "propuesta_serie_cambio.json"), "--change", CID])
        run_ok(["split", PID, "--confirm", *BA, "--change", CID])
        forget_read_snapshots()

    def step(self) -> dict:
        forget_read_snapshots()
        return json.loads(run_ok(["next", PID, "--change", CID]))

    def validation(self) -> dict:
        forget_read_snapshots()
        _code, out, _err = run_all(["validate", PID, "--change", CID])
        return json.loads(out)

    def stories(self, rid: str) -> list[str]:
        index = workspace_path(PID) / "04_backlog" / CID / rid / "stories.md"
        return sorted(set(re.findall(r"\[(US-\d+)\]", index.read_text(encoding="utf-8"))))

    def build_and_close(self, rid: str) -> None:
        run_ok(["specs", PID, "--change", CID, "--release", rid])
        run_ok(["backlog", PID, "--change", CID, "--release", rid])
        evidence = Path.cwd() / "evidencia.md"
        evidence.write_text(f"Evidencia sintetica de {rid}.\n", encoding="utf-8")
        for sid in self.stories(rid):
            for status in ("Ready", "In Progress", "In Review"):
                run_ok(["story-status", PID, "--story", sid, "--set", status])
            run_ok(["story-status", PID, "--story", sid, "--set", "Done", "--evidence", str(evidence)])
        forget_read_snapshots()
        run_ok(["split", PID, "--close", rid, "--evidence", str(evidence), *BA, "--change", CID])
        forget_read_snapshots()

    def add_unit_on_r1(self) -> str:
        """A new ADDED row on a surface that r1 owns (B-04); the id of the unit it becomes."""
        before = self.unit_ids()
        self.answer_rows("nueva.md", "GAP-QUALITY", "ADDED", "Tabla de proveedores",
                         "Cuando el analista guarda el alta, el sistema debe registrar el usuario que la cargó.")
        run_ok(["brief", PID, "--change", CID])
        class_deferred(PID, CID)
        forget_read_snapshots()
        run_ok(["export", PID, "--artifact", "brief", "--change", CID, "--final"])
        forget_read_snapshots()
        run_ok(["specs", PID, "--change", CID])
        forget_read_snapshots()
        added = sorted(self.unit_ids() - before)
        self.assertEqual(len(added), 1, added)
        return added[0]


class Series(SeriesCase):
    def test_extracted_change_splits_valid(self):
        """B-03: the literal-text blocks of a consolidated final are anchored by the request they quote."""
        self.confirmed()
        validation = self.validation()
        checks = {c["id"]: c["status"] for c in validation["checks"]}
        self.assertEqual(checks.get("release_series"), "PASS", validation["findings"][:3])
        self.assertEqual(validation["verdict"], "VALID", validation["findings"][:3])
        series = json.loads((workspace_path(PID) / "02_requirements" / CID / "series" / "series_report.json").read_text(encoding="utf-8"))             if (workspace_path(PID) / "02_requirements" / CID / "series" / "series_report.json").is_file() else {}
        self.assertEqual(series.get("integrity", {}), {}, series)
        self.assertEqual(series.get("unresolved", []) + series.get("unrouted", []), [])

    def test_split_confirm_routes_to_r1(self):
        """B-07: the client's confirmation is an operational item; r1 is next and the first move is not refused."""
        self.confirmed()
        step = self.step()
        self.assertTrue(step["command"].startswith(f"/specs {PID} --change {CID} --release r1"), step)
        forget_read_snapshots()
        code, out, err = run_all(["split", PID, "--move", "--unit", "C-04", "--from", "r1", "--to", "r2",
                                  "--reason", "prueba de ruta", *BA, "--change", CID])
        self.assertNotIn("el brief cambió", err)
        self.assertEqual(code, 0, (out, err))

    def test_unit_on_closed_release_routed(self):
        """B-04: a new unit whose owner closed is named and moved to the open release."""
        self.confirmed()
        self.build_and_close("r1")
        unit = self.add_unit_on_r1()
        step = self.step()
        self.assertEqual(step["key"], "series_closed_units", step)
        self.assertIn(unit, step["text"])
        self.assertIn(f"--move --unit {unit} --from r1 --to r2", step["command"])
        forget_read_snapshots()
        code, out, err = run_all(["split", PID, "--move", "--unit", unit, "--from", "r1", "--to", "r2",
                                  "--reason", "llegó con el último pedido", *BA, "--change", CID])
        self.assertEqual(code, 0, (out, err))
        forget_read_snapshots()
        run_ok(["specs", PID, "--change", CID, "--release", "r2"])
        folder = workspace_path(PID) / "03_specs" / CID
        self.assertTrue((folder / "r2" / "units" / f"{unit}.md").is_file())
        self.assertFalse((folder / "r1" / "units" / f"{unit}.md").exists())
        self.assertNotEqual(self.step()["key"], "series_closed_units")

    def test_unit_on_closed_release_no_open(self):
        """B-04 (Q4): every release closed: /validate says a new release is needed and names the unit."""
        self.confirmed()
        self.build_and_close("r1")
        self.build_and_close("r2")
        unit = self.add_unit_on_r1()
        validation = self.validation()
        self.assertEqual(validation["verdict"], "INVALID")
        text = " ".join(validation["findings"])
        self.assertIn(f"{unit} llega a r1, cerrada: proponé una release nueva con /split {PID} --change {CID} --propose", text)
        forget_read_snapshots()
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertIn(unit, json.dumps(status))

    def test_series_refusals_language(self):
        """A-35/B-31: in a Spanish change the refusals of the series are Spanish."""
        self.confirmed()
        run_ok(["specs", PID, "--change", CID, "--release", "r1"])
        run_ok(["backlog", PID, "--change", CID, "--release", "r1"])
        evidence = Path.cwd() / "ev.md"
        evidence.write_text("Evidencia.\n", encoding="utf-8")
        forget_read_snapshots()
        code, _out, err = run_all(["split", PID, "--close", "r1", "--evidence", str(evidence), *BA, "--change", CID])
        self.assertNotEqual(code, 0)
        self.assertIn("r1 no puede cerrar", err)
        self.assertNotIn("cannot close", err)
        self.add_unit_on_r1()
        forget_read_snapshots()
        code, _out, err = run_all(["split", PID, "--move", "--unit", "C-04", "--from", "r1", "--to", "r2",
                                   "--reason", "prueba", *BA, "--change", CID])
        self.assertNotEqual(code, 0)
        self.assertIn("el brief cambió desde que se confirmó la serie", err)
        self.assertNotIn("the brief changed", err)


if __name__ == "__main__":
    unittest.main()
