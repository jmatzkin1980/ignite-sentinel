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


if __name__ == "__main__":
    unittest.main()
