"""IMP-404 (H26 inc 4) task 7: /cross in the CLI and the MCP tool."""
from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_h26_cross_next import CID, CROSSES, PID, NextCase  # noqa: E402
from helpers import run_cli, run_ok  # noqa: E402

from sentinel import mcp as sentinel_mcp  # noqa: E402
from sentinel.cli import main  # noqa: E402
from sentinel.crosses.surfaces import new_surface_candidates  # noqa: E402
from tests.test_mcp_parity import _tools  # noqa: E402


def cross(*argv: str) -> dict:
    return json.loads(run_ok(["cross", PID, "--change", CID, *argv]))


class CrossCli(NextCase):
    def prepare(self) -> dict[str, str]:
        run_ok(["harvest", PID, "--source", "harvest_compras.md", "--change", CID])
        self.load_design()
        return self.ids()

    def test_cli_forms(self):
        ids = self.prepare()
        status = cross()
        claims = cross("--kind", "diseno", "--claims", str(self.claims("cruce_diseno.md", ids)))
        skipped = cross("--kind", "contradicciones", "--skip", "--reason", "x")
        found = new_surface_candidates(PID, CID)
        self.assertEqual(len(found), 2)
        accepted = cross("--accept-new", found[0]["id"], "--type", "pantalla", "--name", "Historial de aprobaciones")
        declined = cross("--decline-new", found[1]["id"], "--reason", "x")
        for result, action in (
            (status, "status"), (claims, "claims"), (skipped, "skip"), (accepted, "accept_new"), (declined, "decline_new"),
        ):
            self.assertEqual(result["action"], action)
            for key in ("crosses", "next_step", "message"):
                self.assertTrue(result[key], (action, key))
            self.assertNotIn("\n", result["message"])
        self.assertTrue(status["message"].startswith(f"{CID}: cruces: "))
        self.assertIn(f"{CID}: cruce diseño nuevo registrado (", claims["message"])
        self.assertIn("pregunta(s) nueva(s)", claims["message"])
        self.assertEqual(skipped["message"], f"{CID}: cruce contradicciones internas descartado: x")
        self.assertEqual(
            accepted["message"], f"{CID}: «Historial de aprobaciones» entra al borde como superficie nuevo (pantalla)")
        self.assertEqual(declined["message"], f"{CID}: {found[1]['id']} descartada: x")

    def test_cli_rejects_combinations(self):
        for argv in (
            ["--claims", "a", "--skip"],
            ["--claims", "a"],
            ["--skip", "--kind", "diseno"],
            ["--accept-new", "X", "--name", "y"],
            ["--type", "pantalla"],
            ["--kind", "diseno", "--decline-new", "X", "--reason", "y"],
        ):
            code, _ = run_cli(["cross", PID, "--change", CID, *argv])
            self.assertNotEqual(code, 0, argv)

    def test_unknown_change_is_refused(self):
        code, _ = run_cli(["cross", PID, "--change", "CHG-099"])
        self.assertNotEqual(code, 0)

    def test_baseline_claims_point_to_harvest(self):
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = main(["cross", PID, "--change", CID, "--kind", "linea_de_base", "--claims", "a.md"])
        self.assertNotEqual(code, 0)
        self.assertRegex(err.getvalue(), r"next step:.*/harvest")


class CrossArguments(unittest.TestCase):
    def test_cli_requires_change(self):
        with self.assertRaises(SystemExit):
            run_cli(["cross", "P"])

    def test_mcp_cross_passes_arguments(self):
        captured: list[list[str]] = []
        with patch.object(sentinel_mcp, "run_cli", lambda arguments: captured.append(arguments) or {"exit_code": 0}):
            _tools()["sentinel_cross"](
                project_id="P", change="CHG-001", accept_new="NEW-ABC123", surface_type="pantalla",
                name="Historial de aprobaciones")
            _tools()["sentinel_cross"](project_id="P", change="CHG-001", kind="diseno", skip=True, reason="x")
        self.assertEqual(captured[0], [
            "cross", "P", "--change", "CHG-001", "--accept-new", "NEW-ABC123", "--type", "pantalla",
            "--name", "Historial de aprobaciones"])
        self.assertEqual(captured[1], ["cross", "P", "--change", "CHG-001", "--kind", "diseno", "--skip", "--reason", "x"])


if __name__ == "__main__":
    unittest.main()
