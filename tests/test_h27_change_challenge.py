"""IMP-418 (H27 inc 6a) task 6: /challenge --change reviews the change's request, brief and gaps; its questions stay in the change."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, run_ok  # noqa: E402

from sentinel.changes import change_gaps_path, list_changes  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.discovery import AnnotationError, apply_challenge  # noqa: E402
from sentinel.discovery.change_scope import change_channel_gate, change_channel_paths, change_grounding_text  # noqa: E402
from sentinel.errors import GateRefusal  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.prior_decisions import PriorDecision  # noqa: E402
from sentinel.readiness_verdict import change_next_step  # noqa: E402
from sentinel.workspace import read_state, workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CROSSES = FIXTURES / "change_crosses"
SAD = FIXTURES / "change_baseline" / "sad-compras.md"
PID = "CHCH"
CID = "CHG-001"
RAW = "# Alta de proveedores\n\nEl equipo de Compras quiere ordenar el alta de proveedores en el sistema.\n"
EVIDENCE = "Si el monto supera el umbral, el alta pasa a la bandeja de la jefa de Compras."


def finding(**over) -> dict:
    base = {"id": "GAP-APROBACION-AUSENCIA", "lens": "business", "severity": "high", "technique": "pre-mortem",
            "question": "¿Quién aprueba un alta de monto alto cuando la jefa de Compras está ausente?",
            "evidence": EVIDENCE}
    base.update(over)
    return base


class ChallengeCase(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(CROSSES / "pedido_contradiccion.md", root / "pedido.md")
        shutil.copy(CROSSES / "harvest_compras.md", root / "harvest_compras.md")
        (root / "raw.md").write_text(RAW, encoding="utf-8")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "raw.md"])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        run_ok(["sources", PID, "--load", str(SAD), "--role", "linea_de_base", "--change", CID])
        run_ok(["harvest", PID, "--source", "harvest_compras.md", "--change", CID])

    def setUp(self):
        super().setUp()
        forget_read_snapshots()
        self.base = workspace_path(PID)

    def payload(self, *findings: dict, name: str = "c.json", **extra) -> Path:
        path = Path.cwd() / name
        path.write_text(json.dumps({"gaps": list(findings or [finding()]), "absent": [], "untouched": [], **extra}),
                        encoding="utf-8")
        return path

    def challenge(self, *findings: dict, name: str = "c.json") -> dict:
        forget_read_snapshots()
        return apply_challenge(PID, self.payload(*findings, name=name), change_id=CID)

    def rows(self, path: Path) -> dict[str, dict]:
        return {g["id"]: g for g in parse_gap_rows(path.read_text(encoding="utf-8"))}


class Sink(ChallengeCase):
    def test_change_findings_stay_in_change_gaps(self):
        project_gaps = self.base / "01_discovery" / "gaps.md"
        before = project_gaps.read_bytes()
        result = self.challenge()
        self.assertEqual(result["change_id"], CID)
        rows = self.rows(change_gaps_path(self.base, CID))
        self.assertEqual(rows["GAP-APROBACION-AUSENCIA"]["origin"], "challenge")
        self.assertEqual(project_gaps.read_bytes(), before)

    def test_report_and_archive_under_change(self):
        result = self.challenge()
        folder = self.base / "01_discovery" / CID
        self.assertTrue((folder / "challenge_report.md").is_file())
        self.assertTrue((folder / "challenges" / "c.json").is_file())
        self.assertFalse((self.base / "01_discovery" / "challenge_report.md").exists())
        self.assertEqual(Path(result["challenge_report"]), (folder / "challenge_report.md"))
        self.assertEqual(Path(result["path"]), change_gaps_path(self.base, CID))
        report = (folder / "challenge_report.md").read_text(encoding="utf-8")
        self.assertIn("Informe de Challenge", report)

    def test_blocking_finding_sends_next_to_lenses(self):
        state_before = read_state(PID)
        before = list_changes(PID)[CID]["gap_counts"]["blocking_open"]
        self.challenge(finding(blocks=True))
        self.assertEqual(list_changes(PID)[CID]["gap_counts"]["blocking_open"], before + 1)
        self.assertEqual(change_next_step(PID, CID)["key"], "lenses")
        after = read_state(PID)
        for key in ("readiness_stage", "health", "gap_counts"):
            self.assertEqual(after.get(key), state_before.get(key))

    def test_sweep_log_per_change(self):
        self.challenge()
        log = self.base / "01_discovery" / CID / "agent_sweep_log.md"
        self.assertIn("## challenge -", log.read_text(encoding="utf-8"))
        self.assertFalse((self.base / "01_discovery" / "agent_sweep_log.md").exists())

    def test_graph_edge_from_change_node(self):
        from sentinel.core.graph import load_graph

        result = self.challenge()
        edges = load_graph(PID).get("edges", [])
        self.assertTrue(any(e.get("from") == CID and e.get("to") == result["challenge_id"]
                            and e.get("relation") == "challenged_by" for e in edges), edges[-3:])

    def test_prior_decision_not_asked_again(self):
        found = PriorDecision(gap_id="GAP-DIS-0A1B2C3D", match="linked", basis="quote", answer="Rige el pedido.")
        with mock.patch("sentinel.prior_decisions.find_prior_decision", return_value=found), \
                mock.patch("sentinel.prior_decisions.live_prior_answer",
                           side_effect=lambda _p, _c, entry, live=None: entry.get("answer")):
            before = list_changes(PID)[CID]["gap_counts"]["blocking_open"]
            self.challenge()
        row = self.rows(change_gaps_path(self.base, CID))["GAP-APROBACION-AUSENCIA"]
        self.assertEqual(row["status"], "PRE_DECIDED")
        self.assertEqual(list_changes(PID)[CID]["gap_counts"]["blocking_open"], before)


class Grounding(ChallengeCase):
    def test_quote_from_brief_and_baseline_accepted(self):
        quote = "No hay una bandeja de aprobaciones de altas para la jefatura."
        self.challenge(finding(evidence=quote))
        brief = self.base / "02_requirements" / CID / "project-brief.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text("# Brief\n\nLa jefa de Compras revisa las altas observadas por auditoría interna.\n",
                         encoding="utf-8")
        self.challenge(finding(id="GAP-AUDITORIA-OBSERVADAS", evidence="revisa las altas observadas por auditoría interna"),
                       name="c2.json")
        with self.assertRaises(AnnotationError):
            self.challenge(finding(id="GAP-INVENTADO", evidence="una frase que nadie dijo jamás"), name="c3.json")

    def test_request_in_09_request_is_citable(self):
        self.assertFalse(list((self.base / "00_raw").glob("pedido*")))
        self.assertTrue(list((self.base / "00_raw" / "09_request").glob("pedido*")))
        self.assertIn(EVIDENCE, change_grounding_text(PID, CID))
        self.assertEqual(self.challenge()["merged"], ["GAP-APROBACION-AUSENCIA"])


class Gate(ChallengeCase):
    def test_no_change_gaps_file_refused(self):
        change_gaps_path(self.base, CID).unlink()
        forget_read_snapshots()
        with self.assertRaises(GateRefusal) as caught:
            apply_challenge(PID, self.payload(), change_id=CID)
        self.assertIn("todavía no tiene archivo de gaps", str(caught.exception))
        self.assertEqual(caught.exception.next_step, f"/gaps {PID} --change {CID}")

    def test_gate_returns_change_path_and_language(self):
        change, gaps_path, language = change_channel_gate(PID, CID, "challenge")
        self.assertEqual(gaps_path, change_gaps_path(self.base, CID))
        self.assertEqual(language, "es")
        self.assertEqual(change["source"], list_changes(PID)[CID]["source"])

    def test_paths(self):
        paths = change_channel_paths(self.base, CID)
        folder = self.base / "01_discovery" / CID
        self.assertEqual(set(paths), {"gaps", "challenge_report", "scrutiny_report", "annotation_log", "annotations",
                                      "challenges", "scrutiny", "sweep_log"})
        self.assertEqual(paths["sweep_log"], folder / "agent_sweep_log.md")
        self.assertEqual(paths["gaps"], folder / "gaps.md")

    def test_project_form_unchanged_in_mixed_workspace(self):
        forget_read_snapshots()
        result = apply_challenge(PID, self.payload(finding(evidence="ordenar el alta de proveedores")))
        self.assertNotIn("change_id", result)
        self.assertTrue((self.base / "01_discovery" / "challenge_report.md").is_file())


if __name__ == "__main__":
    unittest.main()
