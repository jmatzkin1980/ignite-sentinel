"""H27 inc 7a tasks 1-2: /sources --load --derived-from records where a derived prototype comes from."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SyncCase, run_ok  # noqa: E402

from sentinel.changes import list_changes  # noqa: E402
from sentinel.cli import main  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.source_versions import check_change_versions  # noqa: E402
from sentinel.sources import load_source_manifest, source_log_path  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = "DERV"
CID = "CHG-001"
INC7 = SyncCase.FIXTURES / "change_inc7"
HTML = INC7 / "prototipo-alta-proveedor.html"
TRANSCRIPT = INC7 / "prototipo-alta-proveedor.md"
ORIGIN_ERROR = "no es un prototipo vigente de"
ROLE_ERROR = "--derived-from va con --role diseno_nuevo"


def run_err(argv: list[str]) -> tuple[int, str]:
    """Run one command; return its exit code and what it wrote to stderr."""
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, err.getvalue()


class DerivedCase(SyncCase):
    """A change with its design loaded (F-DIS) and a prototype that has no visible text (F-ORI)."""

    PID = PID
    ORI = ""

    @classmethod
    def build_workspace(cls) -> None:
        super().build_workspace()
        out = run_ok(["sources", PID, "--load", str(HTML), "--role", "diseno_nuevo", "--change", CID])
        cls.ORI = json.loads(out)["source_id"]

    def rows(self) -> list[dict]:
        forget_read_snapshots()
        return load_source_manifest(PID)["registry"]

    def row(self, source_id: str) -> dict:
        return next(r for r in self.rows() if r["id"] == source_id)

    def load_derived(self, origin: str | None = None, *extra: str) -> dict:
        out = run_ok(["sources", PID, "--load", str(TRANSCRIPT), "--role", "diseno_nuevo", "--change", CID,
                      "--derived-from", origin or self.ORI, *extra])
        forget_read_snapshots()
        return json.loads(out)

    def source_log(self) -> str:
        return source_log_path(PID).read_text(encoding="utf-8")


class DerivedSourceTests(DerivedCase):
    def test_derived_row_records_origin(self):
        result = self.load_derived()
        self.assertEqual(result["derived_from"], self.ORI)
        self.assertEqual(self.row(result["source_id"])["derived_from"], self.ORI)
        log = self.source_log()
        self.assertTrue(f"derivado de {self.ORI}" in log or f"derived from {self.ORI}" in log)

    def test_derived_refusals(self):
        before = json.dumps(self.rows(), sort_keys=True)
        for role in ("pedido", "linea_de_base"):
            code, err = run_err(["sources", PID, "--load", str(TRANSCRIPT), "--role", role, "--change", CID,
                                 "--derived-from", self.ORI])
            self.assertNotEqual(code, 0)
            self.assertIn(ROLE_ERROR, err)
            self.assertEqual(json.dumps(self.rows(), sort_keys=True), before)
        code, err = run_err(["sources", PID, "--load", str(TRANSCRIPT), "--role", "diseno_nuevo", "--change", CID,
                             "--derived-from", "F-99"])
        self.assertNotEqual(code, 0)
        self.assertIn(ORIGIN_ERROR, err)
        self.assertEqual(json.dumps(self.rows(), sort_keys=True), before)
        # a design of another change is not in this change's view
        run_ok(["ingest", PID, "--source", str(SyncCase.FIXTURES / "change_request.md"), "--change"])
        second_change = next(c for c in list_changes(PID) if c != CID)
        second = Path.cwd() / "prototipo-otro.html"
        second.write_text("<html><body><h1>Otra pantalla</h1></body></html>", encoding="utf-8")
        other = run_ok(["sources", PID, "--load", str(second), "--role", "diseno_nuevo", "--change", second_change])
        other_id = json.loads(other)["source_id"]
        before = json.dumps(self.rows(), sort_keys=True)
        code, err = run_err(["sources", PID, "--load", str(TRANSCRIPT), "--role", "diseno_nuevo", "--change", CID,
                             "--derived-from", other_id])
        self.assertNotEqual(code, 0)
        self.assertIn(ORIGIN_ERROR, err)
        self.assertEqual(json.dumps(self.rows(), sort_keys=True), before)
        self.assertNotIn("derivado de", self.source_log())
        self.assertNotIn("derived from", self.source_log())

    def test_derived_not_a_version(self):
        result = self.load_derived()
        row = self.row(result["source_id"])
        self.assertFalse(row.get("pending_version_of"))
        report = check_change_versions(PID, CID, write=False)
        seen = [item.get("source_id") for key in ("matched", "mismatched") for item in report[key]]
        self.assertNotIn(row["id"], seen)

    def test_rows_without_derivation_unchanged(self):
        log = self.source_log()
        self.assertNotIn("derivado de", log)
        self.assertNotIn("derived from", log)
        for row in self.rows():
            self.assertNotIn("derived_from", row)
        listed = json.loads(run_ok(["sources", PID]))
        self.assertTrue(all("derived_from" not in row for row in listed["registry"]))


class DerivedCitationTests(DerivedCase):
    def claims_for(self, name: str, derived: str = "F-DER") -> Path:
        ids = self.ids()
        text = (INC7 / name).read_text(encoding="utf-8")
        text = text.replace("F-PED", ids["pedido"]).replace("F-DER", derived).replace("F-ORI", self.ORI)
        path = Path.cwd() / f"sub-{name}"
        path.write_text(text, encoding="utf-8")
        return path

    def crosses_text(self) -> str:
        from sentinel.crosses import crosses_dir

        return (crosses_dir(workspace_path(PID), CID) / "crosses.md").read_text(encoding="utf-8")

    def test_crosses_md_shows_origin(self):
        from sentinel.crosses.record import record_cross

        derived = self.load_derived()["source_id"]
        record_cross(PID, CID, "diseno", self.claims_for("cruce_diseno_derivado.md", derived))
        text = self.crosses_text()
        self.assertTrue(f"(derivado de {self.ORI})" in text or f"(derived from {self.ORI})" in text)
        self.assertIn(f"{derived} (", text)

    def test_gap_text_names_origin(self):
        from sentinel.changes import change_gaps_path
        from sentinel.crosses.record import record_cross

        derived = self.load_derived()["source_id"]
        path = Path.cwd() / "sub-solo-derivado.md"
        path.write_text(
            "# Cruce pedido ↔ diseño nuevo — CHG-001\n\n"
            "- [SOLO EN DISEÑO] El prototipo trae un botón de envío que el pedido no menciona.\n"
            f"  - Diseño: {derived} \"Botón: Enviar a aprobación\"\n", encoding="utf-8")
        result = record_cross(PID, CID, "diseno", path)
        forget_read_snapshots()
        gaps = change_gaps_path(workspace_path(PID), CID).read_text(encoding="utf-8")
        gap_id = next(g for g in result["gaps"] if g.startswith("GAP-SED-"))
        text = "\n".join(item for item in gaps.splitlines() if gap_id in item)
        self.assertTrue(f"({derived}, derivado de {self.ORI})" in text or f"({derived}, derived from {self.ORI})" in text, text)

    def test_quote_absent_from_derived_refused(self):
        from sentinel.crosses.record import record_cross
        from sentinel.errors import InputError

        self.load_derived()
        before = self.crosses_text()
        with self.assertRaises(InputError):
            record_cross(PID, CID, "diseno", self.claims_for("cruce_diseno_origen.md"))
        self.assertEqual(self.crosses_text(), before)

    def test_change_brief_lists_origin(self):
        from sentinel.compilers.change_deliverable import render_change_deliverable

        derived = self.load_derived()["source_id"]
        text = render_change_deliverable(PID, CID, False)
        line = next(item for item in text.splitlines() if item.startswith(f"- `{derived}`"))
        self.assertTrue(line.endswith(f"— derivado de {self.ORI}") or line.endswith(f"— derived from {self.ORI}"), line)
        other = next(item for item in text.splitlines() if item.startswith(f"- `{self.ORI}`"))
        self.assertNotIn("derivado de", other)
        self.assertNotIn("derived from", other)


class DerivedOverwriteTests(DerivedCase):
    def test_other_origin_refused(self):
        self.load_derived()
        extra = Path.cwd() / "otro-prototipo.md"
        extra.write_text("# Otro prototipo\n\nPantalla de consulta de proveedores.\n", encoding="utf-8")
        other = json.loads(run_ok(["sources", PID, "--load", str(extra), "--role", "diseno_nuevo", "--change", CID]))["source_id"]
        code, err = run_err(["sources", PID, "--load", str(TRANSCRIPT), "--role", "diseno_nuevo", "--change", CID,
                             "--derived-from", other])
        self.assertNotEqual(code, 0)
        self.assertIn(self.ORI, err)
        derived = [r for r in self.rows() if r.get("derived_from")]
        self.assertEqual([r["derived_from"] for r in derived], [self.ORI])


if __name__ == "__main__":
    unittest.main()
