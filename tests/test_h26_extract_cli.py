"""IMP-402 (H26 inc 3) task 8: /extract in the CLI and the MCP tool."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_cli, run_ok  # noqa: E402
from test_h26_extract_proposals import CID, EXAMPLE, PID, ProposalsCase  # noqa: E402

from sentinel import mcp as sentinel_mcp  # noqa: E402
from tests.test_mcp_parity import _tools  # noqa: E402


class ExtractCli(ProposalsCase):
    def test_cli_phases(self):
        inventory = json.loads(run_ok(["extract", PID, "--change", CID]))
        proposals = json.loads(run_ok(["extract", PID, "--change", CID, "--proposals", str(EXAMPLE)]))
        confirmed = json.loads(run_ok(["extract", PID, "--change", CID, "--confirm", "all"]))
        rejected = json.loads(run_ok(["extract", PID, "--change", CID, "--reject-item", "HU-01", "--reason", "x"]))
        for result, action in (
            (inventory, "inventory"), (proposals, "proposals"), (confirmed, "confirm"), (rejected, "reject"),
        ):
            self.assertEqual(result["action"], action)
            for key in ("coverage", "next_step", "message"):
                self.assertTrue(result[key], (action, key))
            self.assertNotIn("\n", result["message"])
        self.assertIn("elementos inventariados", inventory["message"])
        self.assertIn("propuesta(s) registrada(s)", proposals["message"])
        self.assertIn("0 sin cambios (siguen confirmadas), 0 sin tratamiento", proposals["message"])
        self.assertIn("retenida(s) por marca", confirmed["message"])
        self.assertEqual(rejected["message"], f"{CID}: HU-01 volvió a pendiente")

    def test_cli_confirm_item_on_a_held_item(self):
        run_ok(["extract", PID, "--change", CID, "--proposals", str(EXAMPLE)])
        bulk = json.loads(run_ok(["extract", PID, "--change", CID, "--confirm", "all"]))
        self.assertEqual(bulk["held"], ["RN-04"])
        self.assertIn("0 ya no válida(s)", bulk["message"])
        single = json.loads(run_ok(["extract", PID, "--change", CID, "--confirm-item", "RN-04"]))
        self.assertEqual(single["action"], "confirm")
        self.assertEqual((single["confirmed"], single["held"]), (["RN-04"], []))
        self.assertTrue(single["rows_added"])
        self.assertIn(f"{CID}: 1 confirmada(s), 0 retenida(s) por marca", single["message"])
        self.assertEqual(single["coverage"]["proposed"], 0)

    def test_cli_rejects_combinations(self):
        for argv in (
            ["--confirm", "all", "--confirm-item", "RN-01"],
            ["--proposals", str(EXAMPLE), "--confirm", "all"],
            ["--reason", "x"],
            ["--reject-item", "RN-01"],
        ):
            code, _ = run_cli(["extract", PID, "--change", CID, *argv])
            self.assertNotEqual(code, 0, argv)

    def test_unknown_change_is_refused(self):
        code, _ = run_cli(["extract", PID, "--change", "CHG-099"])
        self.assertNotEqual(code, 0)


class ExtractArguments(unittest.TestCase):
    def test_cli_change_is_optional(self):  # IMP-420: parsed without --change; the project path decides what it means
        self.assertNotEqual(run_cli(["extract", "P"])[0], 0)  # no workspace P: a refusal, not a parse error (SystemExit)

    def test_mcp_extract_passes_arguments(self):
        captured: list[list[str]] = []
        with patch.object(sentinel_mcp, "run_cli", lambda arguments: captured.append(arguments) or {"exit_code": 0}):
            _tools()["sentinel_extract"](project_id="P", change="CHG-001", confirm_item="Regla 1")
            _tools()["sentinel_extract"](project_id="P", change="CHG-001")
        self.assertEqual(captured[0], ["extract", "P", "--change", "CHG-001", "--confirm-item", "Regla 1"])
        self.assertEqual(captured[1], ["extract", "P", "--change", "CHG-001"])


if __name__ == "__main__":
    unittest.main()
