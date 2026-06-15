from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.memory import ContextBroker


class KnowledgeLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp)

    def test_ingest_materializes_cited_lens_knowledge_ledger(self) -> None:
        source = self.temp / "input" / "ledger-demo.md"
        source.parent.mkdir(parents=True)
        source.write_text(
            "\n".join(
                [
                    "# Ledger Demo",
                    "",
                    "Goal: reduce manual review time for support leads.",
                    "Users include support leads and operations managers.",
                    "Scope includes a dashboard for queue triage.",
                    "Quality expects auditable tests for stale queue data.",
                ]
            ),
            encoding="utf-8",
        )

        self.assertEqual(main(["init", "LEDGER"]), 0)
        self.assertEqual(main(["ingest", "LEDGER", "--source", str(source)]), 0)

        base = self.temp / "workspaces" / "LEDGER"
        ledger_md = base / "01_discovery" / "knowledge_state.md"
        ledger_json = base / "01_discovery" / "knowledge_state.json"
        self.assertTrue(ledger_md.exists())
        self.assertTrue(ledger_json.exists())

        payload = json.loads(ledger_json.read_text(encoding="utf-8"))
        self.assertEqual(payload["artifact"], "knowledge_state")
        self.assertGreater(payload["summary"]["total"], 0)
        self.assertIn("CONFIRMED", payload["summary"]["by_status"])
        self.assertIn("OPEN", payload["summary"]["by_status"])

        units = payload["units"]
        self.assertTrue(any(unit["lens"] == "business" and unit["status"] == "CONFIRMED" for unit in units))
        self.assertTrue(any(unit["status"] == "OPEN" for unit in units))
        for unit in units:
            self.assertIn(unit["status"], {"CONFIRMED", "ASSUMED", "OPEN", "INFERRED"})
            evidence = unit["evidence"]
            if unit["status"] == "OPEN":
                self.assertTrue(
                    evidence.get("note") == "[PENDING INPUT]" or (evidence.get("trace_id") and evidence.get("quote"))
                )
            else:
                self.assertTrue(evidence.get("trace_id"))
                self.assertTrue(evidence.get("quote"))

        ledger_text = ledger_md.read_text(encoding="utf-8")
        self.assertIn("Knowledge State - LEDGER", ledger_text)
        self.assertIn("[PENDING INPUT]", ledger_text)
        self.assertIn("reduce manual review time", ledger_text)

        graph = json.loads((base / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8"))
        ledger_nodes = [node for node in graph["nodes"] if node["type"] == "knowledge_ledger"]
        self.assertEqual(len(ledger_nodes), 1)
        ledger_id = ledger_nodes[0]["id"]
        self.assertTrue(
            any(edge["to"] == ledger_id and edge["relation"] == "consolidated_by" for edge in graph["edges"])
        )

        state = json.loads((base / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["artifacts"]["knowledge_state"], ledger_md.as_posix())
        self.assertEqual(state["metrics"]["knowledge_units"], payload["summary"]["total"])

        status_code = main(["status", "LEDGER"])
        self.assertEqual(status_code, 0)
        status_summary = __import__("sentinel.status", fromlist=["project_status"]).project_status("LEDGER")
        self.assertEqual(status_summary["knowledge_ledger"]["total"], payload["summary"]["total"])

        results = ContextBroker("LEDGER").retrieve(
            "manual review time",
            "discovery",
            artifact_type="knowledge_ledger",
        )
        self.assertTrue(results)
        self.assertEqual(results[0]["artifact_type"], "knowledge_ledger")

    def test_schema_documents_status_and_evidence_contract(self) -> None:
        schema = json.loads(Path(self.old_cwd / "sentinel" / "schemas" / "knowledge_unit.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["status"]["enum"], ["CONFIRMED", "ASSUMED", "OPEN", "INFERRED"])
        self.assertIn("note", schema["properties"]["evidence"]["properties"])
        self.assertIn("trace_id", schema["properties"]["evidence"]["properties"])
        self.assertIn("quote", schema["properties"]["evidence"]["properties"])
