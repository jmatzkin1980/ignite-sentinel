"""IMP-435 (H27 inc 9a) task 7: platform, /setup and refusal language (C-05, C-07, C-10, C-22, C-24, C-26, A-35, B-31).

No test downloads anything: the missing extra is simulated with a patched `find_spec`.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402

from sentinel.cli import main  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FX = ROOT / "fixtures"


def run_all(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def _env(**extra: str) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in {"PYTHONIOENCODING", "PYTHONUTF8"}}
    env.update(extra)
    env["PYTHONPATH"] = str(REPO)
    return env


class ChangeOnlyCase(SnapshotWorkspaceCase):
    """A workspace that only holds one change (Compras / alta de proveedores)."""

    @classmethod
    def build_workspace(cls):
        shutil.copy(FX / "change_borrador.md", Path.cwd() / "pedido.md")
        run_ok(["init", "ALTAS"])
        run_ok(["ingest", "ALTAS", "--source", "pedido.md", "--change"])

    def set_change_language(self, language: str) -> None:
        state_file = workspace_path("ALTAS") / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        for change in state["changes"].values():
            change["language"] = language
        state_file.write_text(json.dumps(state), encoding="utf-8")

    def test_stderr_utf8(self):
        """C-05: stderr is UTF-8 whatever the console code page and without PYTHONIOENCODING."""
        self.set_change_language("es")
        err_file = Path.cwd() / "err.txt"
        with err_file.open("wb") as handle:
            proc = subprocess.run([sys.executable, "-m", "sentinel", "maturity", "ALTAS"], stderr=handle,
                                  stdout=subprocess.DEVNULL, cwd=str(Path.cwd()), env=_env())
        self.assertNotEqual(proc.returncode, 0)
        text = err_file.read_bytes().decode("utf-8")
        self.assertIn("sólo", text)

    def test_refusal_language_follows_workspace(self):
        """A-35, C-26, B-31: the refusals of a change in English are in English."""
        self.set_change_language("en")
        code, _out, err = run_all(["gaps", "ALTAS", "--change", "CHG-001", "--top", "3"])
        self.assertEqual(code, 3, err)
        self.assertIn("does not combine with", err)
        self.assertNotIn("no se combina", err)
        self.assertNotIn("Corré", err)
        code, _out, err = run_all(["maturity", "ALTAS"])
        self.assertNotEqual(code, 0)
        self.assertIn("only has changes", err)
        self.assertNotIn("sólo tiene", err)
        code, _out, err = run_all(["validate", "ALTAS"])
        self.assertNotEqual(code, 0)
        self.assertNotIn("sólo tiene", err)
        code, _out, err = run_all(["brief", "ALTAS", "--change", "CHG-001", "--profile", "x"])
        self.assertNotIn("no se combina", err)
        code, _out, err = run_all(["self-review", "ALTAS", "--change", "CHG-001"])
        self.assertNotIn("va con", err)
        self.assertIn("goes with --crosses", err)


class SetupExitClasses(unittest.TestCase):
    def test_setup_exit_classes(self):
        """C-07: a missing extra is a prerequisite (4) with a next step; an empty --offline-from is input (3)."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            empty = Path(tmp) / "empty"
            empty.mkdir()
            with mock.patch.dict(os.environ, {"SENTINEL_HOME": str(home)}), \
                    mock.patch("importlib.util.find_spec", return_value=None):
                code, _out, err = run_all(["setup", "--semantic-memory"])
            self.assertEqual(code, 4, err)
            self.assertIn("next step:", err)
            self.assertIn("memory-semantic.txt", err)
            self.assertNotIn("Traceback", err)
            with mock.patch.dict(os.environ, {"SENTINEL_HOME": str(home)}), \
                    mock.patch("importlib.util.find_spec", return_value=object()):
                code, _out, err = run_all(["setup", "--semantic-memory", "--offline-from", str(empty)])
            self.assertEqual(code, 3, err)
            self.assertNotIn("Traceback", err)


class KiloAndAdapters(unittest.TestCase):
    def test_kilo_asks_for_setup(self):
        """C-10: Kilo asks before /setup, after the wildcard (Kilo takes the last matching rule)."""
        text = (REPO / "kilo.jsonc").read_text(encoding="utf-8")
        keys = re.findall(r'^\s*"(python -m sentinel[^"]*)":\s*"(\w+)"', text, re.M)
        order = [key for key, _ in keys]
        rules = dict(keys)
        wildcard = order.index("python -m sentinel *")
        for pattern in ("python -m sentinel setup *", "python -m sentinel /setup *"):
            self.assertEqual(rules.get(pattern), "ask", pattern)
            self.assertGreater(order.index(pattern), wildcard, pattern)

    def test_adapters_help_does_not_regenerate(self):
        """C-22: --help prints usage and exits 0 without running the generator."""
        proc = subprocess.run([sys.executable, "-m", "sentinel.adapters", "--help"], capture_output=True,
                              cwd=str(REPO), env=_env(), timeout=60)
        out = proc.stdout.decode("utf-8", "replace")
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertIn("usage:", out)
        self.assertNotIn("regenerated_commands", out)

    def test_doctor_network_detail(self):
        """C-24: the detail names the one declared exception."""
        from sentinel.doctor import network_isolation_check

        result = network_isolation_check()
        self.assertEqual(result["status"], "PASS", result)
        self.assertIn("setup_download.py", result["detail"])


if __name__ == "__main__":
    unittest.main()
