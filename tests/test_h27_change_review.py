"""IMP-418 (H27 inc 6a) task 7: /annotate and /scrutinize with --change, and the command surface of the three channels."""
from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, run_ok  # noqa: E402

from sentinel.cli import main  # noqa: E402
from sentinel.changes import change_gaps_path  # noqa: E402
from sentinel.commands import skill_for_command  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

CROSSES = Path(__file__).resolve().parent / "fixtures" / "change_crosses"
PID = "CHRV"
ONLY = "CHRO"
CID = "CHG-001"
RAW = "# Alta de proveedores\n\nEl equipo de Compras quiere ordenar el alta de proveedores en el sistema.\n"
RAW_QUOTE = "El equipo de Compras quiere ordenar el alta de proveedores en el sistema."
EVIDENCE = "Si el monto supera el umbral, el alta pasa a la bandeja de la jefa de Compras."


def finding(**over) -> dict:
    base = {"id": "GAP-APROBACION-AUSENCIA", "lens": "business", "severity": "high", "technique": "pre-mortem",
            "finding_type": "domain-conflict",
            "question": "¿Quién aprueba un alta de monto alto cuando la jefa de Compras está ausente?",
            "evidence": EVIDENCE}
    base.update(over)
    return base


def fails(argv: list[str]) -> tuple[int, str]:
    """Run one command in-process; return (exit code, stderr)."""
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        code = main(list(argv))
    return code, err.getvalue()


class ReviewCase(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(CROSSES / "pedido_contradiccion.md", root / "pedido.md")
        (root / "raw.md").write_text(RAW, encoding="utf-8")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "raw.md"])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        run_ok(["init", ONLY])
        run_ok(["ingest", ONLY, "--source", "pedido.md", "--change"])

    def setUp(self):
        super().setUp()
        forget_read_snapshots()
        self.base = workspace_path(PID)

    def payload(self, name: str, *findings: dict) -> str:
        path = Path.cwd() / name
        path.write_text(json.dumps({"gaps": list(findings or [finding()]), "absent": [], "untouched": [],
                                    "ambiguities": [], "assumptions": []}), encoding="utf-8")
        return str(path)

    def rows(self, path: Path) -> dict[str, dict]:
        return {g["id"]: g for g in parse_gap_rows(path.read_text(encoding="utf-8"))}


class Annotate(ReviewCase):
    def test_annotate_change(self):
        project_gaps = self.base / "01_discovery" / "gaps.md"
        before = project_gaps.read_bytes()
        result = json.loads(run_ok(["annotate", PID, "--source", self.payload("a.json"), "--change", CID]))
        self.assertEqual(result["change_id"], CID)
        row = self.rows(change_gaps_path(self.base, CID))["GAP-APROBACION-AUSENCIA"]
        self.assertEqual(row["origin"], "agent")
        folder = self.base / "01_discovery" / CID
        self.assertTrue((folder / "agent_annotation_log.md").is_file())
        self.assertTrue((folder / "annotations" / "a.json").is_file())
        self.assertFalse((self.base / "01_discovery" / "agent_annotation_log.md").exists())
        self.assertEqual(project_gaps.read_bytes(), before)
        self.assertIn("Anotación", (folder / "agent_annotation_log.md").read_text(encoding="utf-8"))

    def test_project_annotate_unchanged(self):
        run_ok(["annotate", PID, "--source", self.payload("p.json", finding(evidence=RAW_QUOTE))])
        self.assertTrue((self.base / "01_discovery" / "agent_annotation_log.md").is_file())


class Scrutinize(ReviewCase):
    def test_scrutinize_change(self):
        ledger = self.base / "01_discovery" / "knowledge_ledger.json"
        existed = ledger.exists()
        before = ledger.stat().st_mtime_ns if existed else None
        result = json.loads(run_ok(["scrutinize", PID, "--source", self.payload("s.json"), "--change", CID,
                                    "--lens", "business"]))
        self.assertEqual(result["change_id"], CID)
        row = self.rows(change_gaps_path(self.base, CID))["GAP-APROBACION-AUSENCIA"]
        self.assertEqual(row["origin"], "scrutiny")
        folder = self.base / "01_discovery" / CID
        self.assertTrue((folder / "scrutiny_report.md").is_file())
        self.assertTrue((folder / "scrutiny" / "s.json").is_file())
        self.assertIn("Informe de Scrutiny", (folder / "scrutiny_report.md").read_text(encoding="utf-8"))
        self.assertEqual(ledger.exists(), existed)
        if existed:
            self.assertEqual(ledger.stat().st_mtime_ns, before)
        self.assertNotIn("knowledge_state", result)

    def test_probe_and_anchors_refused(self):
        for mode in ("implementability-probe", "anchors"):
            code, err = fails(["scrutinize", PID, "--source", self.payload("m.json"), "--change", CID, "--mode", mode])
            self.assertNotEqual(code, 0, mode)
            self.assertIn(f"--change {CID}", err, mode)


class ChangeOnly(ReviewCase):
    def test_change_only_project_form_names_change(self):
        for command in ("challenge", "annotate", "scrutinize"):
            code, err = fails([command, ONLY, "--source", self.payload("c.json")])
            self.assertNotEqual(code, 0, command)
            self.assertIn("sólo tiene cambios", err, command)
            self.assertIn(f"--change {CID}", err, command)
            self.assertNotIn("before /ingest", err, command)

    def test_project_form_leaves_change_gaps(self):
        path = change_gaps_path(self.base, CID)
        before = path.read_bytes()
        run_ok(["challenge", PID, "--source", self.payload("c.json", finding(evidence=RAW_QUOTE))])
        self.assertEqual(path.read_bytes(), before)


class Surface(unittest.TestCase):
    def test_mcp_and_registry(self):
        import inspect

        from sentinel import mcp

        source = inspect.getsource(mcp)
        for name in ("sentinel_annotate", "sentinel_challenge", "sentinel_scrutinize"):
            start = source.index(f"def {name}(")
            signature = source[start:source.index(":\n", start)]
            self.assertIn('change: str = ""', signature, name)
        self.assertEqual(skill_for_command(f"/challenge {PID} --source X --change {CID}"), "sentinel-challenge §Change")
        self.assertEqual(skill_for_command(f"/annotate {PID} --source X --change {CID}"), "sentinel-annotate §Change")
        self.assertEqual(skill_for_command(f"/scrutinize {PID} --source X --change {CID}"), "sentinel-scrutiny §Change")
        self.assertEqual(skill_for_command(f"/challenge {PID} --source X"), "sentinel-challenge")


if __name__ == "__main__":
    unittest.main()
