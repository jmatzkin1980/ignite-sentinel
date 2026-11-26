"""IMP-433: `/compose --change` writes narrative blocks onto the PRD of a change, and `/specs --change` keeps them."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, complete_extraction, export_final_brief, run_cli, run_ok, waive_coherence, waive_crosses  # noqa: E402
from change_inc8b_flow import BASELINE, build_project_outputs, project_output_hashes  # noqa: E402
from sentinel.compilers.change_prd import render_change_prd, write_change_prd  # noqa: E402
from sentinel.core.graph import load_graph  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.discovery.change_scope import change_grounding_text  # noqa: E402
from sentinel.workspace import read_json, update_state, workspace_path  # noqa: E402
import test_change_next as tcn  # noqa: E402
import test_h27_change_grouped_backlog as grouped  # noqa: E402

CID = "CHG-001"
QUOTE = "Guardar borrador"


def draft(name: str, quote: str, text: str = "The change lets the user keep a draft of the supplier registration.") -> str:
    path = Path(name)
    path.write_text(json.dumps({"blocks": [{"section": "1", "paragraphs": [{"text": text, "citations": [quote]}]}]}), encoding="utf-8")
    return str(path)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BorrWithPrd(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        tcn.ChangeNextSequence.build_workspace()
        tcn.ChangeNextSequence.test_each_row_of_the_table_in_order(unittest.TestCase())

    def setUp(self):
        super().setUp()
        forget_read_snapshots()
        self.base = workspace_path("BORR")
        self.prd = self.base / "03_specs" / CID / "prd.md"

    def test_change_compose_writes_change_prd(self):
        self.assertTrue(self.prd.is_file())
        out = json.loads(run_ok(["compose", "BORR", "--source", draft("b.json", QUOTE), "--change", CID]))
        self.assertEqual(len(out["accepted"]), 1)
        self.assertIn("### Agent Composition", self.prd.read_text(encoding="utf-8"))
        folder = self.base / "03_specs" / CID / "compositions"
        self.assertTrue((folder / "accepted_blocks.json").is_file())
        self.assertTrue((folder / "composition_report.md").read_text(encoding="utf-8").startswith("# PRD Composition Report - BORR / CHG-001"))
        self.assertFalse((self.base / "03_specs" / "compositions").exists())
        state = read_json(self.base / "state.json", {})
        self.assertEqual(state["changes"][CID]["composition"]["count"], 1)
        self.assertNotIn("prd_composition_count", state)
        edges = [e for e in load_graph("BORR")["edges"] if e["relation"] == "composed_by"]
        self.assertEqual([(e["from"], e["to"]) for e in edges], [(CID, out["composition_id"])])

    def test_specs_change_keeps_composition(self):
        """RF 1: regenerating the PRD of the change keeps the composed prose."""
        run_ok(["compose", "BORR", "--source", draft("b.json", QUOTE), "--change", CID])
        forget_read_snapshots()
        export_final_brief("BORR", CID)
        run_ok(["specs", "BORR", "--change", CID])
        text = self.prd.read_text(encoding="utf-8")
        self.assertIn("### Agent Composition", text)
        self.assertIn(QUOTE, text)
        self.assertTrue((self.base / "03_specs" / CID / "compositions" / "regeneration_report.md").is_file())

    def test_specs_change_without_compositions_unchanged(self):
        forget_read_snapshots()
        write_change_prd("BORR", CID)
        self.assertEqual(self.prd.read_text(encoding="utf-8"), render_change_prd("BORR", CID))
        self.assertFalse((self.base / "03_specs" / CID / "compositions").exists())

    def test_second_compose_merges_onto_the_first(self):
        run_ok(["compose", "BORR", "--source", draft("b.json", QUOTE), "--change", CID])
        forget_read_snapshots()
        run_ok(["compose", "BORR", "--source", draft("c.json", QUOTE, "Second narrative sentence for the same section."), "--change", CID])
        blocks = read_json(self.base / "03_specs" / CID / "compositions" / "accepted_blocks.json", [])
        self.assertEqual(len(blocks), 2)
        self.assertEqual(read_json(self.base / "state.json", {})["changes"][CID]["composition"]["count"], 2)


class BorrWithoutPrd(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        tcn.ChangeNextSequence.build_workspace()

    def test_change_compose_refusal(self):
        from sentinel.errors import GateRefusal
        from sentinel.prd import apply_prd_composition

        code, _out = run_cli(["compose", "BORR", "--source", draft("b.json", QUOTE), "--change", CID])
        self.assertNotEqual(code, 0)
        with self.assertRaises(GateRefusal) as caught:
            apply_prd_composition("BORR", Path("b.json"), CID)
        self.assertEqual(str(caught.exception), "CHG-001 todavía no tiene PRD para componer")
        self.assertEqual(caught.exception.next_step, "/specs BORR --change CHG-001")
        changes = read_json(workspace_path("BORR") / "state.json", {})["changes"]
        changes[CID]["language"] = "en"
        update_state("BORR", changes=changes)
        forget_read_snapshots()
        with self.assertRaises(GateRefusal) as caught:
            apply_prd_composition("BORR", Path("b.json"), CID)
        self.assertEqual(str(caught.exception), "CHG-001 has no PRD to compose yet")
        self.assertFalse((workspace_path("BORR") / "03_specs" / CID / "compositions").exists())


class MixWithChangePrd(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        grouped.GroupedRemovedBacklog.build_workspace.__func__(cls)
        waive_crosses("MIX", cls.cid)
        tcn.load_baseline("MIX", cls.cid)
        waive_coherence("MIX", cls.cid)
        complete_extraction("MIX", cls.cid)
        run_ok(["brief", "MIX", "--change", cls.cid])
        export_final_brief("MIX", cls.cid)
        run_ok(["specs", "MIX", "--change", cls.cid])

    def test_change_compose_rejects_project_only_quote(self):
        """RF 2: a quote that exists only in the project's raw cannot ground a block of the change."""
        cid = type(self).cid
        base = workspace_path("MIX")
        grounding = change_grounding_text("MIX", cid) + (base / "03_specs" / cid / "specs.md").read_text(encoding="utf-8")
        raw = "\n".join(p.read_text(encoding="utf-8") for p in sorted((base / "00_raw").rglob("*.md")))
        quote = next(ln.strip() for ln in raw.splitlines() if len(ln.strip()) > 25 and ln.strip() not in grounding)
        prd = base / "03_specs" / cid / "prd.md"
        before = sha(prd)
        code, out = run_cli(["compose", "MIX", "--source", draft("m.json", quote), "--change", cid])
        self.assertNotEqual(code, 0)
        self.assertEqual(sha(prd), before)
        report = base / "03_specs" / cid / "compositions" / "composition_report.md"
        self.assertIn("citation not found verbatim", report.read_text(encoding="utf-8"))
        self.assertFalse((base / "03_specs" / cid / "compositions" / "accepted_blocks.json").exists())


class ProjectComposeBytes(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        build_project_outputs(Path.cwd())

    def test_project_compose_bytes_unchanged(self):
        """RF 3."""
        self.assertEqual(project_output_hashes(self.temp), json.loads(BASELINE.read_text(encoding="utf-8")))


class ProjectFlowIsolation(unittest.TestCase):
    """The bytes baseline cannot depend on the installed LanceDB or on what ran before in the process (verify.ps1's .venv
    has lancedb 0.33, whose ranking wrote a different EPIC-001 than 0.41)."""

    def test_flow_runs_on_the_json_index_with_a_clean_environment(self):
        import os
        import tempfile
        from unittest.mock import patch
        from change_inc8b_flow import ISOLATED_ENV, isolated_flow
        from sentinel.memory import ContextBroker

        leaked = {name: "leaked" for name in ISOLATED_ENV}
        with patch.dict(os.environ, leaked), tempfile.TemporaryDirectory() as tmp:
            old = os.getcwd()
            with isolated_flow(Path(tmp)):
                self.assertEqual([name for name in ISOLATED_ENV if name in os.environ], [])
                self.assertEqual(Path.cwd().resolve(), Path(tmp).resolve())
                self.assertIsNone(ContextBroker._connect_lancedb(object()))  # the JSON index, whatever LanceDB is installed
            self.assertEqual(os.getcwd(), old)
            self.assertEqual({name: os.environ.get(name) for name in ISOLATED_ENV}, leaked)


if __name__ == "__main__":
    unittest.main()
