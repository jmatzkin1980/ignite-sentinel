from __future__ import annotations

import os
import shutil
import tempfile
import unittest
import json
from pathlib import Path

from sentinel.cli import main
from sentinel.doctor import run_doctor
from sentinel.memory import ContextBroker


ROOT = Path(__file__).parent


class SentinelCoreFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp)

    def test_incomplete_requirement_blocks_maturity(self) -> None:
        fixture = ROOT / "fixtures" / "incomplete_requirement.md"
        self.assertEqual(main(["init", "ACME"]), 0)
        self.assertEqual(main(["ingest", "ACME", "--source", str(fixture)]), 0)
        self.assertEqual(main(["maturity", "ACME"]), 0)
        gaps = (self.temp / "workspaces" / "ACME" / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        self.assertIn("Document version: `1.0`", gaps)
        self.assertIn("How To Respond", gaps)
        self.assertIn("Example of a useful answer", gaps)
        self.assertIn("Client / domain response", gaps)
        self.assertIn("Framework Trace Table", gaps)
        report = (self.temp / "workspaces" / "ACME" / "01_discovery" / "requirement_maturity_report.md").read_text(encoding="utf-8")
        self.assertIn("`BLOCKED`", report)
        self.assertNotEqual(main(["specs", "ACME"]), 0)

    def test_spanish_client_input_generates_spanish_gap_document(self) -> None:
        source = self.temp / "input" / "client_requirement" / "nota-cliente.md"
        source.parent.mkdir(parents=True)
        source.write_text(
            "# Nota del cliente\n\nNecesitamos un dashboard para operaciones. El objetivo es reducir trabajo manual.",
            encoding="utf-8",
        )
        self.assertEqual(main(["init", "LANG_DEMO"]), 0)
        self.assertEqual(main(["ingest", "LANG_DEMO", "--source", str(source)]), 0)
        state = json.loads((self.temp / "workspaces" / "LANG_DEMO" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["project_language"], "es")
        gaps = (self.temp / "workspaces" / "LANG_DEMO" / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        self.assertIn("Versión del documento: `1.0`", gaps)
        self.assertIn("## Cómo responder", gaps)
        self.assertIn("Ejemplo de respuesta útil", gaps)
        self.assertIn("Respuesta del cliente / dominio", gaps)

    def test_complete_requirement_generates_traceable_backlog(self) -> None:
        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "NOVA"]), 0)
        self.assertEqual(main(["ingest", "NOVA", "--source", str(fixture)]), 0)
        lens_review = self.temp / "workspaces" / "NOVA" / "01_discovery" / "lens_review.md"
        self.assertTrue(lens_review.exists())
        lens_review_text = lens_review.read_text(encoding="utf-8")
        self.assertIn("Multi-Lens Critical Review", lens_review_text)
        self.assertIn("Technology deep-dive readiness", lens_review_text)
        self.assertIn("Design prototype readiness", lens_review_text)
        self.assertIn("Frontend implementation readiness", lens_review_text)
        self.assertIn("Backend implementation readiness", lens_review_text)
        self.assertEqual(main(["maturity", "NOVA"]), 0)
        project_brief = self.temp / "workspaces" / "NOVA" / "02_requirements" / "project-brief.md"
        self.assertTrue(project_brief.exists())
        brief_text = project_brief.read_text(encoding="utf-8")
        self.assertIn("Project Brief", brief_text)
        self.assertIn("Identidad y Valor", brief_text)
        self.assertIn("Radar de Incertidumbres", brief_text)
        self.assertIn("Domain Context Pack Requests", brief_text)
        self.assertIn("endpoint/event inventory", brief_text)
        self.assertEqual(main(["specs", "NOVA"]), 0)
        prd_text = (self.temp / "workspaces" / "NOVA" / "03_specs" / "prd.md").read_text(encoding="utf-8")
        spec_text = (self.temp / "workspaces" / "NOVA" / "03_specs" / "specs.md").read_text(encoding="utf-8")
        self.assertIn("Executive Summary", prd_text)
        self.assertIn("Users And Personas", prd_text)
        self.assertIn("Functional Requirements", prd_text)
        self.assertIn("FR-01 Acceptance Criteria", prd_text)
        self.assertIn("Business Success Criteria", prd_text)
        self.assertIn("Dependency Map", prd_text)
        self.assertIn("Mature source: `02_requirements/project-brief.md`", spec_text)
        self.assertIn("Backlog-Relevant Contract", spec_text)
        self.assertIn("Retrieval Plan For Backlog Agents", spec_text)
        self.assertTrue((self.temp / "workspaces" / "NOVA" / "08_context_packs" / "specs_generation.json").exists())
        self.assertEqual(main(["backlog", "NOVA"]), 0)
        backlog_pack = self.temp / "workspaces" / "NOVA" / "08_context_packs" / "backlog_generation.json"
        self.assertTrue(backlog_pack.exists())
        readiness_pack = self.temp / "workspaces" / "NOVA" / "08_context_packs" / "implementation_readiness.json"
        self.assertTrue(readiness_pack.exists())
        slice_plan_md = self.temp / "workspaces" / "NOVA" / "04_backlog" / "SLICE-PLAN.md"
        slice_plan_json = self.temp / "workspaces" / "NOVA" / "08_context_packs" / "slice_plan.json"
        self.assertTrue(slice_plan_md.exists())
        self.assertTrue(slice_plan_json.exists())
        readiness = json.loads(readiness_pack.read_text(encoding="utf-8"))
        self.assertEqual(readiness["workflow"], "implementation_readiness")
        self.assertTrue(readiness["stories"])
        self.assertIn("retrieval_plan", readiness["stories"][0])
        slice_plan = json.loads(slice_plan_json.read_text(encoding="utf-8"))
        self.assertEqual(slice_plan["workflow"], "slice_plan")
        self.assertIn("handoff_packs", slice_plan)
        self.assertIn("Implementation Waves", slice_plan_md.read_text(encoding="utf-8"))
        epic_text = (self.temp / "workspaces" / "NOVA" / "04_backlog" / "EPIC-001.md").read_text(encoding="utf-8")
        self.assertIn("## Story Map", epic_text)
        self.assertIn("## Slicing Strategy", epic_text)
        self.assertIn("## Domain Context Coverage", epic_text)
        self.assertIn("**Agent Execution Contract:**", epic_text)
        self.assertIn("**Retrieval Plan For Execution Agents:**", epic_text)
        self.assertIn("Small but valuable", epic_text)
        self.assertIn("Fail-to-Pass", epic_text)
        self.assertIn("Pass-to-Pass", epic_text)
        self.assertIn("[PENDING DOMAIN CONTEXT]", epic_text)
        self.assertFalse((self.temp / "workspaces" / "NOVA" / "04_backlog" / "EPIC-002-cross-cutting-enablers.md").exists())
        self.assertIn("SPEC-U", epic_text)
        self.assertIn("backlog_generation.json", epic_text)
        self.assertIn("implementation_readiness.json", epic_text)
        self.assertEqual(main(["quality", "NOVA"]), 0)
        self.assertEqual(main(["health", "NOVA"]), 0)
        self.assertEqual(main(["validate", "NOVA"]), 0)
        self.assertEqual(main(["trace", "NOVA"]), 0)
        graph = (self.temp / "workspaces" / "NOVA" / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "project_brief"', graph)
        self.assertIn('"type": "prd"', graph)
        self.assertIn('"type": "user_story"', graph)
        self.assertIn('"type": "acceptance_criteria"', graph)
        self.assertIn('"type": "test_case"', graph)
        self.assertIn('"id": "US-001"', graph)
        self.assertIn('"id": "TC-001"', graph)
        story = (self.temp / "workspaces" / "NOVA" / "04_backlog" / "US-001.md").read_text(encoding="utf-8")
        self.assertIn("Acceptance Criteria", story)
        self.assertIn("AC-001-01", story)
        self.assertIn("Agent Execution Contract", story)
        self.assertIn("Retrieval Plan For Execution Agents", story)
        self.assertIn("pass-to-pass", story)
        mermaid = self.temp / "workspaces" / "NOVA" / "06_traceability" / "traceability_graph.md"
        self.assertTrue(mermaid.exists())
        command_log = self.temp / "workspaces" / "NOVA" / "06_traceability" / "command_protocol_log.md"
        self.assertTrue(command_log.exists())
        self.assertIn("`quality`", command_log.read_text(encoding="utf-8"))

    def test_backlog_generates_cross_cutting_enabler_epic_only_with_specific_evidence(self) -> None:
        source = self.temp / "input" / "client_requirement" / "enabler-ready.md"
        source.parent.mkdir(parents=True)
        source.write_text(
            """# Requirement

Objetivo: mejorar visibilidad operativa para supervisores.
Usuarios: supervisores y analistas de operaciones.
Alcance: mostrar casos de alto riesgo con datos vigentes. Out of scope: reportes historicos.
Criterio de success: usuarios autorizados identifican casos de alto riesgo antes de la reunion diaria.
Quality: QA valida happy path, permisos faltantes, datos faltantes y datos vencidos.
Metric source: baseline from current weekly operations report.
MVP: first value slice is one authorized user viewing one high-risk case.
Auth/API enabler: role permissions and API contract are shared by the value stories in this project.
""",
            encoding="utf-8",
        )
        self.assertEqual(main(["init", "ENABLE"]), 0)
        self.assertEqual(main(["ingest", "ENABLE", "--source", str(source)]), 0)
        answer = self.temp / "input" / "client_requirement" / "enabler-answers.md"
        answer.write_text(
            "### GAP-PRD-FR-AC\n"
            "- Answer: When authorized users open the risk dashboard, the system shall show one high-risk case.\n"
            "- Owner / source: Client workshop\n"
            "- Evidence or reference: Synthetic EARS response for enabler boundary test\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["resolve-gaps", "ENABLE", "--source", str(answer)]), 0)
        self.assertEqual(main(["maturity", "ENABLE"]), 0)
        self.assertEqual(main(["specs", "ENABLE"]), 0)
        self.assertEqual(main(["backlog", "ENABLE"]), 0)

        base = self.temp / "workspaces" / "ENABLE"
        enabler_epic = base / "04_backlog" / "EPIC-002-cross-cutting-enablers.md"
        self.assertTrue(enabler_epic.exists())
        enabler_text = enabler_epic.read_text(encoding="utf-8")
        self.assertIn("Cross-Cutting Enablers", enabler_text)
        self.assertIn("Domain Context Coverage", enabler_text)
        self.assertIn("Agent Execution Contract", enabler_text)
        self.assertIn("precondition", enabler_text)
        self.assertIn("US-001", enabler_text)
        graph = (base / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"relation": "enables"', graph)

    def test_retrieval_is_project_scoped(self) -> None:
        complete = ROOT / "fixtures" / "complete_requirement.md"
        incomplete = ROOT / "fixtures" / "incomplete_requirement.md"
        self.assertEqual(main(["init", "NOVA"]), 0)
        self.assertEqual(main(["init", "ACME"]), 0)
        self.assertEqual(main(["ingest", "NOVA", "--source", str(complete)]), 0)
        self.assertEqual(main(["ingest", "ACME", "--source", str(incomplete)]), 0)
        results = ContextBroker("NOVA").retrieve("support leads SLA", "maturity")
        self.assertTrue(results)
        self.assertTrue(all(row["project_id"] == "NOVA" for row in results))

    def test_context_folders_are_indexed_for_hybrid_retrieval(self) -> None:
        complete = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "NOVA"]), 0)
        tech_context = self.temp / "workspaces" / "NOVA" / "00_raw" / "02_technology_context" / "integration.md"
        tech_context.write_text(
            "The support queue integration uses webhook retries and the Atlas CRM account identifier.",
            encoding="utf-8",
        )
        design_context = self.temp / "workspaces" / "NOVA" / "00_raw" / "03_design_context" / "states.md"
        design_context.write_text(
            "Queue screens must show loading, empty, and recoverable error states for SLA triage.",
            encoding="utf-8",
        )
        self.assertEqual(main(["ingest", "NOVA", "--source", str(complete)]), 0)
        tech_results = ContextBroker("NOVA").retrieve("Atlas CRM webhook retries", "discovery", domain="technical")
        design_results = ContextBroker("NOVA").retrieve("recoverable error state SLA triage", "discovery", domain="design")
        self.assertTrue(tech_results)
        self.assertTrue(design_results)
        self.assertEqual(tech_results[0]["artifact_type"], "technology_context")
        self.assertEqual(design_results[0]["artifact_type"], "design_context")
        self.assertEqual(main(["maturity", "NOVA"]), 0)
        self.assertEqual(main(["specs", "NOVA"]), 0)
        self.assertEqual(main(["backlog", "NOVA"]), 0)
        epic_text = (self.temp / "workspaces" / "NOVA" / "04_backlog" / "EPIC-001.md").read_text(encoding="utf-8")
        self.assertIn("Domain Context Coverage", epic_text)
        self.assertRegex(epic_text, r"\| Technology \| .* \| Confirmed \|")
        self.assertRegex(epic_text, r"\| Design \| .* \| Confirmed \|")
        self.assertIn("Agent Execution Contract", epic_text)
        self.assertIn("Retrieval Plan For Execution Agents", epic_text)
        readiness = json.loads((self.temp / "workspaces" / "NOVA" / "08_context_packs" / "implementation_readiness.json").read_text(encoding="utf-8"))
        self.assertIn(readiness["verdict"], {"READY", "PARTIAL"})
        self.assertTrue(readiness["stories"][0]["retrieval_plan"])
        changed_context = self.temp / "workspaces" / "NOVA" / "00_raw" / "02_technology_context" / "changed-contract.md"
        changed_context.write_text("New deployment command and API contract detail added after backlog generation.", encoding="utf-8")
        self.assertEqual(main(["health", "NOVA"]), 0)
        health = json.loads((self.temp / "workspaces" / "NOVA" / "06_traceability" / "health_report.json").read_text(encoding="utf-8"))
        self.assertEqual(health["verdict"], "CLEAN")
        self.assertIn("Domain context changed after backlog generation", " ".join(health["warnings"]))

    def test_sync_creates_change_impact_and_context_pack(self) -> None:
        complete = ROOT / "fixtures" / "complete_requirement.md"
        change = ROOT / "fixtures" / "change_request.md"
        self.assertEqual(main(["init", "NOVA"]), 0)
        self.assertEqual(main(["ingest", "NOVA", "--source", str(complete)]), 0)
        self.assertEqual(main(["specs", "NOVA"]), 0)
        self.assertEqual(main(["backlog", "NOVA"]), 0)
        self.assertEqual(main(["sync", "NOVA", "--source", str(change), "--note", "client follow-up"]), 0)
        graph = (self.temp / "workspaces" / "NOVA" / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "change"', graph)
        self.assertIn('"relation": "may_impact"', graph)
        self.assertEqual(
            main(
                [
                    "retrieve",
                    "NOVA",
                    "--query",
                    "SLA breach risk queue",
                    "--workflow",
                    "sync",
                    "--write-pack",
                    "--artifact-type",
                    "change",
                ]
            ),
            0,
        )
        pack = self.temp / "workspaces" / "NOVA" / "08_context_packs" / "sync.json"
        self.assertTrue(pack.exists())

    def test_autonomous_sync_detects_new_and_modified_inputs(self) -> None:
        complete = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "NOVA"]), 0)
        self.assertEqual(main(["ingest", "NOVA", "--source", str(complete)]), 0)
        self.assertEqual(main(["specs", "NOVA"]), 0)
        self.assertEqual(main(["backlog", "NOVA"]), 0)

        interactions = self.temp / "input" / "interactions"
        interactions.mkdir(parents=True)
        response = interactions / "client-gap-response.md"
        response.write_text(
            "Client confirms target users are support leads. New concern: dashboard export scope remains undefined.",
            encoding="utf-8",
        )

        self.assertEqual(main(["sync", "NOVA"]), 0)
        manifest = json.loads(
            (self.temp / "workspaces" / "NOVA" / "00_raw" / "source_manifest.json").read_text(encoding="utf-8")
        )
        self.assertIn("input/interactions/client-gap-response.md", manifest["sources"])
        graph = (self.temp / "workspaces" / "NOVA" / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "change"', graph)

        self.assertEqual(main(["sync", "NOVA"]), 0)
        response.write_text(
            "Client confirms target users are support leads and managers. New concern: dashboard export scope remains undefined.",
            encoding="utf-8",
        )
        self.assertEqual(main(["sync", "NOVA"]), 0)
        results = ContextBroker("NOVA").retrieve("managers export scope", "sync", artifact_type="change")
        self.assertTrue(results)
        self.assertIn("content", results[0])

    def test_html_sources_are_ingested_synced_and_indexed(self) -> None:
        html = self.temp / "prototype.html"
        html.write_text(
            "<html><body><h1>Risk dashboard prototype</h1><button>Filter stale queues</button></body></html>",
            encoding="utf-8",
        )
        self.assertEqual(main(["init", "HTML"]), 0)
        self.assertEqual(main(["ingest", "HTML", "--source", str(html)]), 0)
        raw_copy = self.temp / "workspaces" / "HTML" / "00_raw" / "prototype.html"
        self.assertTrue(raw_copy.exists())
        self.assertEqual(main(["reindex", "HTML"]), 0)
        results = ContextBroker("HTML").retrieve("Filter stale queues", "discovery")
        self.assertTrue(results)
        self.assertTrue(any("prototype.html" in row.get("source_path", "") for row in results))

        update = self.temp / "input" / "design_context" / "prototype-update.html"
        update.parent.mkdir(parents=True)
        update.write_text("<html><body>Empty state copy for no risk queues.</body></html>", encoding="utf-8")
        self.assertEqual(main(["sync", "HTML", "--source", str(update), "--note", "design prototype update"]), 0)
        manifest = json.loads((self.temp / "workspaces" / "HTML" / "00_raw" / "source_manifest.json").read_text(encoding="utf-8"))
        self.assertIn("input/design_context/prototype-update.html", manifest["sources"])
        synced_copy = self.temp / "workspaces" / "HTML" / "07_changes" / "03_domain_updates" / "prototype-update.html"
        self.assertTrue(synced_copy.exists())

    def test_sync_materializes_only_new_missing_gaps(self) -> None:
        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "SYNCGAP"]), 0)
        self.assertEqual(main(["ingest", "SYNCGAP", "--source", str(fixture)]), 0)
        before = (self.temp / "workspaces" / "SYNCGAP" / "01_discovery" / "gaps.md").read_text(encoding="utf-8")

        change = self.temp / "late-note.md"
        change.write_text(
            "New note: the dashboard should improve operational throughput by 40 percent.",
            encoding="utf-8",
        )
        self.assertEqual(main(["sync", "SYNCGAP", "--source", str(change), "--note", "late metric uncertainty"]), 0)
        after = (self.temp / "workspaces" / "SYNCGAP" / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        self.assertIn("| sync |", after.lower())
        self.assertIn("GAP-METRIC-SOURCE", after)
        self.assertGreater(after.count("GAP-METRIC-SOURCE"), before.count("GAP-METRIC-SOURCE"))

        same_gap_again = self.temp / "late-note-2.md"
        same_gap_again.write_text(
            "Another note: the dashboard should improve operational throughput by 40 percent.",
            encoding="utf-8",
        )
        self.assertEqual(main(["sync", "SYNCGAP", "--source", str(same_gap_again), "--note", "duplicate uncertainty"]), 0)
        final = (self.temp / "workspaces" / "SYNCGAP" / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        self.assertEqual(final.count("GAP-METRIC-SOURCE"), after.count("GAP-METRIC-SOURCE"))

    def test_doctor_passes_for_repo_root(self) -> None:
        self.assertEqual(main(["doctor", "--root", str(ROOT.parent)]), 0)
        self.assertEqual(main(["/doctor", "--root", str(ROOT.parent)]), 0)

    def test_doctor_checks_portable_agent_adapters(self) -> None:
        report = run_doctor(ROOT.parent)
        self.assertEqual(report["verdict"], "PASS")
        check_names = {check["name"] for check in report["checks"]}
        self.assertIn("Codex Desktop and agent instructions", check_names)
        self.assertIn("Codex hooks adapter", check_names)
        self.assertIn("Codex skill: sentinel-command-router", check_names)
        self.assertIn("Kilo slash command: /sentinel", check_names)
        self.assertIn("Claude Code and Claude Desktop instructions", check_names)
        self.assertIn("Claude Code slash commands", check_names)
        self.assertIn("Claude slash command: /sentinel", check_names)
        self.assertIn("Claude adapter guide", check_names)
        self.assertIn("Windows portable Sentinel launcher", check_names)
        self.assertIn("Unix portable Sentinel launcher", check_names)

    def test_inquisitive_discovery_anchors_questions_to_evidence(self) -> None:
        from sentinel.discovery import detect_gaps

        text = (
            "The goal is to reduce review time. Users are support leads. "
            "Scope: one read-only screen with case data from the existing API."
        )
        gaps = {gap["id"]: gap for gap in detect_gaps(text)}
        self.assertIn("GAP-DESIGN-FLOW", gaps)
        self.assertEqual(gaps["GAP-DESIGN-FLOW"].get("evidence_mention"), "screen")
        self.assertIn("GAP-BACKEND-SURFACE", gaps)
        self.assertEqual(gaps["GAP-BACKEND-SURFACE"].get("evidence_mention"), "api")
        described = (
            text + " The journey covers navigation from the queue to the detail view. "
            "Loading, empty, and error states are specified. The API contract documents "
            "failure behavior and retry rules. Architecture and repository notes are attached."
        )
        described_gaps = {gap["id"] for gap in detect_gaps(described)}
        self.assertNotIn("GAP-DESIGN-FLOW", described_gaps)
        self.assertNotIn("GAP-BACKEND-SURFACE", described_gaps)
        self.assertNotIn("GAP-TECH-DEEP-DIVE-INPUT", described_gaps)

    def test_objective_in_english_does_not_raise_objective_gap(self) -> None:
        from sentinel.discovery import detect_gaps

        gaps = {gap["id"] for gap in detect_gaps("The objective is that billing always has current data.")}
        self.assertNotIn("GAP-OBJECTIVE", gaps)

    def test_gaps_document_renders_evidence_trigger(self) -> None:
        fixture = ROOT / "fixtures" / "evals" / "support-dashboard" / "requirement.md"
        self.assertEqual(main(["init", "EVID"]), 0)
        self.assertEqual(main(["ingest", "EVID", "--source", str(fixture)]), 0)
        gaps_md = (self.temp / "workspaces" / "EVID" / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        self.assertIn("Evidence that triggers the question:", gaps_md)
        self.assertIn("Detected Trigger", gaps_md)

    def test_doctor_degrades_to_warn_without_lancedb(self) -> None:
        from unittest import mock
        import sentinel.doctor as doctor_module

        real_find_spec = doctor_module.importlib.util.find_spec

        def fake_find_spec(name, *args, **kwargs):
            if name == "lancedb":
                return None
            return real_find_spec(name, *args, **kwargs)

        with mock.patch.object(doctor_module.importlib.util, "find_spec", side_effect=fake_find_spec):
            report = run_doctor(ROOT.parent)
        checks = {check["name"]: check for check in report["checks"]}
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(checks["memory dependency: lancedb (optional)"]["status"], "WARN")
        self.assertIn("json", checks["memory dependency: lancedb (optional)"]["detail"].lower())
        self.assertEqual(checks["LanceDB local open/create"]["status"], "WARN")

    def test_context_broker_falls_back_to_json_without_lancedb(self) -> None:
        import sys
        from unittest import mock

        fixture = ROOT / "fixtures" / "complete_requirement.md"
        with mock.patch.dict(sys.modules, {"lancedb": None}):
            self.assertEqual(main(["init", "NOLANCE"]), 0)
            self.assertEqual(main(["ingest", "NOLANCE", "--source", str(fixture)]), 0)
            broker = ContextBroker("NOLANCE")
            self.assertEqual(broker.backend, "json-hybrid")
            self.assertIn("ModuleNotFoundError", broker.lancedb_degraded_reason)
            results = broker.retrieve("SLA risk", "discovery")
            self.assertTrue(results)
            self.assertEqual(broker.embedder_status.level, "hash")
            self.assertFalse(broker.embedder_status.semantic)

    def test_lancedb_upsert_is_incremental_without_table_overwrite(self) -> None:
        import sentinel.memory as memory_module

        class FakeTable:
            def __init__(self) -> None:
                self.deleted: list[str] = []
                self.added: list[list[dict]] = []
                self.indexed = False

            def delete(self, where: str):
                self.deleted.append(where)

            def add(self, rows):
                self.added.append(rows)

            def create_fts_index(self, *args, **kwargs):
                self.indexed = True

        class NoOverwriteDb:
            def create_table(self, *args, **kwargs):
                raise AssertionError("upsert must not recreate the LanceDB table")

        broker = object.__new__(ContextBroker)
        broker.project_id = "UPS"
        broker._table = FakeTable()
        broker._lancedb = NoOverwriteDb()
        broker.backend = "lancedb-hybrid"
        broker.lancedb_degraded_reason = ""
        broker.fts_ready = False
        broker.embedder_status = memory_module.EmbedderStatus(
            name="hash_embedding",
            level="hash",
            version="hash_embedding:v1:128",
            dimensions=128,
            detail="deterministic local hash fallback",
            semantic=False,
        )
        broker.embedder = memory_module.HashEmbedder()
        broker.data = {
            "chunks": [
                {
                    "project_id": "UPS",
                    "artifact_id": "ART-1",
                    "artifact_type": "raw_context",
                    "id": "ART-1",
                    "type": "raw_context",
                    "title": "artifact",
                    "source_path": "artifact.md",
                    "file_path": "artifact.md",
                    "domain": "product",
                    "trace_ids": ["ART-1"],
                    "iteration": 1,
                    "metadata": {},
                    "source_hash": "abc",
                    "section_path": "",
                    "language": "unknown",
                    "confidence": "unknown",
                    "sensitivity": "internal",
                    "indexed_at": "2026-06-12T00:00:00+00:00",
                    "summary": "hello",
                    "text": "hello",
                    "content": "hello",
                    "status": "active",
                    "embedder": "hash_embedding",
                    "embedding_version": "hash_embedding:v1:128",
                    "embedding": [1.0] + [0.0] * 127,
                    "chunk_id": "ART-1::chunk-001",
                }
            ]
        }

        broker._upsert_lancedb_chunks("ART-1")

        self.assertEqual(len(broker._table.deleted), 1)
        self.assertIn("artifact_id = 'ART-1'", broker._table.deleted[0])
        self.assertEqual(len(broker._table.added), 1)
        self.assertEqual(broker._table.added[0][0]["chunk_id"], "ART-1::chunk-001")
        self.assertTrue(broker._table.indexed)
        self.assertEqual(broker.backend, "lancedb-hybrid")

    def test_health_reports_memory_backend_degradation_without_dirty_finding(self) -> None:
        from unittest import mock
        import sentinel.health as health_module

        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "MEMHEALTH"]), 0)
        self.assertEqual(main(["ingest", "MEMHEALTH", "--source", str(fixture)]), 0)

        real_broker = ContextBroker("MEMHEALTH")
        real_broker.backend = "json-hybrid"
        real_broker.lancedb_degraded_reason = "test degradation"

        with mock.patch.object(health_module, "ContextBroker", return_value=real_broker):
            result = health_module.run_health("MEMHEALTH")

        self.assertEqual(result["memory_backend"], "json-hybrid")
        self.assertEqual(result["memory_backend_degradation_reason"], "test degradation")
        self.assertNotIn("test degradation", " ".join(result["findings"]))

    def test_structural_chunking_keeps_tables_whole_with_line_anchors(self) -> None:
        from sentinel.memory import chunk_records

        text = """# Support Metrics

Intro paragraph that is intentionally long enough to force separate chunks when the limit is small.

| Metric | Target |
| --- | --- |
| Prep effort | 30% reduction |
| Review time | Weekly |

## Details

Second section paragraph.
"""
        chunks = chunk_records(text, max_chars=120)
        table_chunks = [chunk for chunk in chunks if "| Metric | Target |" in chunk["text"]]

        self.assertEqual(len(table_chunks), 1)
        self.assertIn("| Prep effort | 30% reduction |", table_chunks[0]["text"])
        self.assertIn("| Review time | Weekly |", table_chunks[0]["text"])
        self.assertEqual(table_chunks[0]["section_path"], "Support Metrics")
        self.assertLessEqual(table_chunks[0]["line_start"], 5)
        self.assertGreaterEqual(table_chunks[0]["line_end"], 8)

    def test_reindex_skips_unchanged_artifacts_and_full_forces_rebuild(self) -> None:
        from sentinel.memory import reindex_workspace

        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "INCR"]), 0)
        self.assertEqual(main(["ingest", "INCR", "--source", str(fixture)]), 0)

        first = reindex_workspace("INCR")
        second = reindex_workspace("INCR")
        forced = reindex_workspace("INCR", full=True)

        self.assertEqual(second["embedded_count"], 0)
        self.assertGreater(second["skipped_count"], 0)
        self.assertGreaterEqual(forced["embedded_count"], first["embedded_count"])

    def test_reindex_full_cli_option_is_supported(self) -> None:
        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "FULLIDX"]), 0)
        self.assertEqual(main(["ingest", "FULLIDX", "--source", str(fixture)]), 0)
        self.assertEqual(main(["reindex", "FULLIDX", "--full"]), 0)

    def test_doctor_reports_semantic_embedder_fallback_as_warn(self) -> None:
        from unittest import mock
        import sentinel.doctor as doctor_module

        with mock.patch.object(
            doctor_module,
            "active_embedder_status",
            return_value={
                "name": "hash_embedding",
                "level": "hash",
                "version": "hash_embedding:v1:128",
                "dimensions": 128,
                "detail": "deterministic local hash fallback",
                "semantic": False,
            },
        ):
            report = run_doctor(ROOT.parent)
        checks = {check["name"]: check for check in report["checks"]}
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(checks["memory embedder: semantic local (optional)"]["status"], "WARN")
        self.assertIn("hash_embedding fallback", checks["memory embedder: semantic local (optional)"]["detail"])

    def test_context_broker_uses_semantic_embedder_for_cross_lingual_json_retrieval(self) -> None:
        import sys
        from unittest import mock
        import sentinel.memory as memory_module

        class FakeSemanticEmbedder:
            status = memory_module.EmbedderStatus(
                name="fake-semantic",
                level="model2vec",
                version="fake-semantic:test",
                dimensions=3,
                detail="test semantic embedder",
                semantic=True,
            )

            def embed(self, text: str) -> list[float]:
                normalized = text.lower()
                metric_terms = ("metric", "metrica", "success", "exito", "target", "objetivo", "30%")
                user_terms = ("users", "usuarios", "leads")
                dashboard_terms = ("dashboard", "tablero")
                return [
                    1.0 if any(term in normalized for term in metric_terms) else 0.0,
                    1.0 if any(term in normalized for term in user_terms) else 0.0,
                    1.0 if any(term in normalized for term in dashboard_terms) else 0.0,
                ]

        fixture = ROOT / "fixtures" / "evals" / "support-dashboard" / "requirement.md"
        with (
            mock.patch.dict(sys.modules, {"lancedb": None}),
            mock.patch.object(memory_module, "detect_embedder", return_value=FakeSemanticEmbedder()),
        ):
            self.assertEqual(main(["init", "SEMANTIC"]), 0)
            self.assertEqual(main(["ingest", "SEMANTIC", "--source", str(fixture)]), 0)
            broker = ContextBroker("SEMANTIC")
            results = broker.retrieve("cual es la metrica de exito y el objetivo del tablero", "specs")
        self.assertTrue(
            any(
                "requirement.md" in row.get("source_path", "") or "gaps.md" in row.get("source_path", "")
                for row in results
            )
        )
        self.assertIn("local semantic embedding match", results[0]["why_retrieved"])

    def test_prd_extracts_evidence_backed_personas_frs_and_kpis(self) -> None:
        fixture = ROOT / "fixtures" / "evals" / "support-dashboard" / "requirement.md"
        self.assertEqual(main(["init", "EXTR"]), 0)
        self.assertEqual(main(["ingest", "EXTR", "--source", str(fixture)]), 0)
        from sentinel.generation import render_prd

        raw = fixture.read_text(encoding="utf-8")
        prd = render_prd("EXTR", raw, {"prd_sections": {}}, "requirements.md", "en", raw)
        self.assertIn("Persona Evidence", prd)
        self.assertIn("The main users are the support team leads.", prd)
        self.assertIn("Functional Requirements", prd)
        self.assertIn("They want to see ticket volume, resolution time, and backlog ageing in one screen.", prd)
        self.assertIn("30%", prd)
        self.assertIn("`REQ-001`", prd)

    def test_prd_keeps_pending_input_without_extraction_evidence(self) -> None:
        from sentinel.generation import render_prd

        empty = "Nothing concrete here at all for extraction purposes."
        prd = render_prd("EMPTYX", empty, {"prd_sections": {}}, "requirements.md", "en", empty)
        self.assertIn("resolve `GAP-USERS`", prd)
        self.assertIn("resolve `GAP-PRD-FR-AC`", prd)
        self.assertIn("resolve `GAP-METRIC-SOURCE`", prd)

    def test_validate_scores_semantic_quality_of_artifacts(self) -> None:
        from sentinel.validation import score_artifact_text, validate_project

        scaffolding = "| KPI-01 | outcome | `[PENDING INPUT]` | `[PENDING INPUT]` |\n[PENDING DOMAIN CONTEXT]"
        backed = '| P-E1 | "The main users are support leads." |\n| FR-E01 | "They want a dashboard." |\n30% (confirm baseline)'
        self.assertEqual(score_artifact_text(scaffolding)["classification"], "scaffolding")
        self.assertEqual(score_artifact_text(backed)["classification"], "evidence-backed")
        mixed = scaffolding + "\n" + '| FR-E01 | "statement" |'
        self.assertEqual(score_artifact_text(mixed)["classification"], "mixed")

        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "SEMQ"]), 0)
        self.assertEqual(main(["ingest", "SEMQ", "--source", str(fixture)]), 0)
        self.assertEqual(main(["maturity", "SEMQ"]), 0)
        self.assertEqual(main(["specs", "SEMQ"]), 0)
        report = validate_project("SEMQ")
        self.assertIn("semantic_quality", report)
        self.assertIn("prd.md", report["semantic_quality"])
        prd_quality = report["semantic_quality"]["prd.md"]
        self.assertGreater(prd_quality["evidence_signals"], 0)
        self.assertIn(prd_quality["classification"], {"evidence-backed", "mixed"})
        self.assertEqual(main(["validate", "SEMQ"]), 0)

    def test_context_packs_include_scoring_and_coverage(self) -> None:
        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "SCOR"]), 0)
        self.assertEqual(main(["ingest", "SCOR", "--source", str(fixture)]), 0)
        self.assertEqual(main(["maturity", "SCOR"]), 0)
        self.assertEqual(main(["specs", "SCOR"]), 0)
        self.assertEqual(main(["backlog", "SCOR"]), 0)
        specs_pack = json.loads(
            (self.temp / "workspaces" / "SCOR" / "08_context_packs" / "specs_generation.json").read_text(encoding="utf-8")
        )
        self.assertIn("coverage_map", specs_pack)
        self.assertIn("coverage_score", specs_pack)
        self.assertGreaterEqual(specs_pack["coverage_score"], 0.0)
        self.assertLessEqual(specs_pack["coverage_score"], 1.0)
        for payload in specs_pack["sections"].values():
            self.assertIn(payload["evidence_strength"], {"none", "weak", "strong"})
            self.assertEqual(payload["result_count"], len(payload["results"]))
        readiness = json.loads(
            (self.temp / "workspaces" / "SCOR" / "08_context_packs" / "implementation_readiness.json").read_text(encoding="utf-8")
        )
        slice_plan = json.loads(
            (self.temp / "workspaces" / "SCOR" / "08_context_packs" / "slice_plan.json").read_text(encoding="utf-8")
        )
        self.assertIn("summary", readiness)
        self.assertEqual(slice_plan["summary"]["stories_total"], len(readiness["stories"]))
        summary = readiness["summary"]
        self.assertEqual(summary["stories_total"], len(readiness["stories"]))
        self.assertEqual(summary["stories_ready"] + summary["stories_needing_context"], summary["stories_total"])
        for story in readiness["stories"]:
            self.assertIn("readiness_score", story)
            self.assertGreaterEqual(story["readiness_score"], 0.0)
            self.assertLessEqual(story["readiness_score"], 1.0)
            if story["status"] == "ready":
                self.assertEqual(story["readiness_score"], 1.0)

    def test_maturity_and_status_expose_quantified_metrics(self) -> None:
        from sentinel.maturity import evaluate
        from sentinel.status import project_status

        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "METR"]), 0)
        self.assertEqual(main(["ingest", "METR", "--source", str(fixture)]), 0)
        first = evaluate("METR")
        metrics = first["metrics"]
        for key in ("gap_total", "gap_closure_rate", "open_gaps_by_severity", "maturity_score"):
            self.assertIn(key, metrics)
        self.assertGreaterEqual(metrics["maturity_score"], 0.0)
        self.assertLessEqual(metrics["maturity_score"], 1.0)
        self.assertEqual(main(["specs", "METR"]), 0)
        second = evaluate("METR")
        self.assertIn("trend_vs_previous_run", second["metrics"])
        self.assertIn("prd.md", second["metrics"]["artifact_evidence_scores"])
        status = project_status("METR")
        self.assertIn("maturity_metrics", status)
        self.assertIn("maturity_score", status["maturity_metrics"])

    def test_domain_context_change_warns_without_forcing_backlog_regeneration(self) -> None:
        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "STALE"]), 0)
        self.assertEqual(main(["ingest", "STALE", "--source", str(fixture)]), 0)
        self.assertEqual(main(["maturity", "STALE"]), 0)
        self.assertEqual(main(["specs", "STALE"]), 0)
        self.assertEqual(main(["backlog", "STALE"]), 0)
        self.assertEqual(main(["health", "STALE"]), 0)
        state = json.loads((self.temp / "workspaces" / "STALE" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["health"], "CLEAN")

        tech_dir = self.temp / "workspaces" / "STALE" / "00_raw" / "02_technology_context"
        tech_dir.mkdir(parents=True, exist_ok=True)
        (tech_dir / "architecture-update.md").write_text(
            "New architecture note: the risk service moves to an event-driven contract.",
            encoding="utf-8",
        )
        self.assertEqual(main(["health", "STALE"]), 0)
        report = (self.temp / "workspaces" / "STALE" / "06_traceability" / "health_report.md").read_text(encoding="utf-8")
        self.assertIn("Domain context changed after backlog generation", report)
        self.assertIn("Technology", report)
        self.assertIn("Regenerate backlog only if the change materially affects", report)
        state = json.loads((self.temp / "workspaces" / "STALE" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["health"], "CLEAN")

        self.assertEqual(main(["reindex", "STALE"]), 0)
        self.assertEqual(main(["health", "STALE"]), 0)
        state = json.loads((self.temp / "workspaces" / "STALE" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["health"], "CLEAN")

    def test_gap_resolution_distinguishes_intermediate_states(self) -> None:
        fixture = ROOT / "fixtures" / "incomplete_requirement.md"
        self.assertEqual(main(["init", "NUAN"]), 0)
        self.assertEqual(main(["ingest", "NUAN", "--source", str(fixture)]), 0)
        response = self.temp / "respuestas.md"
        response.write_text(
            """### GAP-USERS

- Answer: Primary users are operations analysts; supervisors only review weekly summaries.
- Owner / source: Client product owner
- Evidence or reference: kickoff notes
- Decision status: confirmed

### GAP-OBJECTIVE

- Answer: Reduce manual review effort for the operations team before the daily standup.
- Owner / source: Client sponsor
- Evidence or reference: email thread
- Decision status: pending

### GAP-SCOPE

- Answer: TBD
- Owner / source: Client PM
- Evidence or reference:
- Decision status: confirmed

### GAP-ACCEPTANCE

- Answer: We will define something later with QA probably.
- Owner / source:
- Evidence or reference:
- Decision status:
""",
            encoding="utf-8",
        )
        from sentinel.gap_resolution import resolve_gaps

        result = resolve_gaps("NUAN", response)
        self.assertIn("GAP-USERS", result["closed"])
        self.assertIn("GAP-OBJECTIVE", result["answered"])
        self.assertIn("GAP-SCOPE", result["partially_closed"])
        self.assertIn("GAP-ACCEPTANCE", result["partially_closed"])
        self.assertNotIn("GAP-SCOPE", result["closed"])
        counts = result["gap_counts"]
        self.assertGreaterEqual(counts["answered"], 1)
        self.assertGreater(counts["blocking_open"], 0)
        gaps_md = (self.temp / "workspaces" / "NUAN" / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        self.assertIn("ANSWERED", gaps_md)
        report_files = list((self.temp / "workspaces" / "NUAN" / "07_changes" / "00_client_responses").glob("*report*.md"))
        report_text = report_files[0].read_text(encoding="utf-8")
        self.assertIn("Answered (Awaiting Confirmation)", report_text)
        self.assertIn("confirmed-but-vague", report_text)
        self.assertNotEqual(main(["specs", "NUAN"]), 0)

    def test_regeneration_records_visible_diff(self) -> None:
        fixture = ROOT / "fixtures" / "complete_requirement.md"
        change = ROOT / "fixtures" / "change_request.md"
        self.assertEqual(main(["init", "REGEN"]), 0)
        self.assertEqual(main(["ingest", "REGEN", "--source", str(fixture)]), 0)
        self.assertEqual(main(["maturity", "REGEN"]), 0)
        self.assertEqual(main(["specs", "REGEN"]), 0)
        regen_dir = self.temp / "workspaces" / "REGEN" / "07_changes" / "04_regeneration"
        self.assertFalse(regen_dir.exists())  # first generation: no diff

        self.assertEqual(main(["sync", "REGEN", "--source", str(change), "--note", "client follow-up"]), 0)
        raw_dir = self.temp / "workspaces" / "REGEN" / "00_raw" / "00_client_requirement"
        (raw_dir / "follow-up-note.md").write_text(
            "The client confirms the dashboard must also flag SLA breach risk by queue before standup.",
            encoding="utf-8",
        )
        self.assertEqual(main(["maturity", "REGEN"]), 0)
        self.assertEqual(main(["specs", "REGEN"]), 0)
        diffs = sorted(regen_dir.glob("*.md"))
        self.assertTrue(diffs)
        diff_text = diffs[0].read_text(encoding="utf-8")
        self.assertIn("Regeneration Diff", diff_text)
        self.assertIn("Triggering change: `CHG-001`", diff_text)
        self.assertIn("Lines added:", diff_text)
        graph = (self.temp / "workspaces" / "REGEN" / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "regeneration_diff"', graph)
        self.assertIn('"relation": "triggers_regeneration"', graph)
        self.assertEqual(main(["validate", "REGEN"]), 0)

    def test_command_adapters_in_sync_with_manifest(self) -> None:
        from sentinel.adapters import manifest_command_names, out_of_sync

        names = manifest_command_names()
        self.assertEqual(len(names), 28)
        self.assertIn("sentinel", names)
        self.assertIn("dashboard", names)
        self.assertIn("annotate", names)
        self.assertIn("challenge", names)
        self.assertIn("compose", names)
        self.assertIn("refine-backlog", names)
        self.assertIn("implementation-feedback", names)
        self.assertIn("story-status", names)
        self.assertIn("backlog-status", names)
        self.assertEqual(out_of_sync(ROOT.parent), [])

    def test_skills_materialized_in_standard_directories(self) -> None:
        from sentinel.adapters import skills_out_of_sync

        self.assertEqual(skills_out_of_sync(ROOT.parent), [])
        for surface in (".agents/skills", ".claude/skills"):
            skill = ROOT.parent / surface / "sentinel-discovery" / "SKILL.md"
            self.assertTrue(skill.exists(), f"missing {surface} skill mirror")

    def test_mcp_server_exposes_lifecycle_tools(self) -> None:
        from sentinel.mcp import describe_tools, run_cli

        names = {tool["name"] for tool in describe_tools()}
        self.assertEqual(len(names), 26)
        for expected in ("sentinel_dashboard", "sentinel_init", "sentinel_ingest", "sentinel_maturity", "sentinel_backlog", "sentinel_validate", "sentinel_annotate", "sentinel_challenge", "sentinel_compose", "sentinel_refine_backlog", "sentinel_implementation_feedback", "sentinel_story_status", "sentinel_backlog_status"):
            self.assertIn(expected, names)

        result = run_cli(["init", "MCPX"])
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("workspace", result["output"])
        blocked = run_cli(["specs", "MCPX"])
        self.assertNotEqual(blocked["exit_code"], 0)
        self.assertIn("error", blocked)

        import importlib.util
        if importlib.util.find_spec("mcp") is not None:
            import asyncio
            from sentinel.mcp import build_server

            tools = asyncio.new_event_loop().run_until_complete(build_server().list_tools())
            self.assertEqual(len(tools), 25)

    def test_discovery_skill_references_maturity_gap_checklist(self) -> None:
        skill = ROOT.parent / ".codex" / "skills" / "sentinel-discovery" / "SKILL.md"
        checklist = ROOT.parent / ".codex" / "skills" / "sentinel-discovery" / "references" / "requirement-maturity-gap-checklist.md"
        self.assertTrue(checklist.exists())
        self.assertIn("requirement-maturity-gap-checklist.md", skill.read_text(encoding="utf-8"))
        checklist_text = checklist.read_text(encoding="utf-8")
        self.assertIn("Technology Deep-Dive Readiness", checklist_text)
        self.assertIn("Design / Prototype Readiness", checklist_text)

    def test_slash_command_aliases_work(self) -> None:
        self.assertEqual(main(["/init", "SLASH_DEMO"]), 0)
        workspace = self.temp / "workspaces" / "SLASH_DEMO"
        self.assertTrue((workspace / "state.json").exists())
        state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))
        config = (workspace / "sentinel.config.yaml").read_text(encoding="utf-8")
        self.assertEqual(state["project_language"], "auto")
        self.assertEqual(state["privacy_mode"], "local-only")
        self.assertIn("project_language: auto", config)
        self.assertIn("privacy_mode: local-only", config)
        self.assertIn("auto_close_rule: confirmed_structured", config)
        self.assertIn("backlog_gate:", config)
        self.assertIn("strict: false", config)
        self.assertIn("privacy_scan:", config)
        self.assertIn("mode: warn", config)
        self.assertTrue((workspace / "00_raw" / "02_technology_context").is_dir())
        self.assertTrue((workspace / "00_raw" / "03_design_context").is_dir())
        self.assertTrue((workspace / "07_changes" / "03_domain_updates").is_dir())

    def test_protocol_guard_requires_initialized_workspace(self) -> None:
        self.assertNotEqual(main(["maturity", "MISSING"]), 0)

    def test_gaps_command_regenerates_human_document(self) -> None:
        fixture = ROOT / "fixtures" / "incomplete_requirement.md"
        self.assertEqual(main(["init", "ACME"]), 0)
        self.assertEqual(main(["ingest", "ACME", "--source", str(fixture)]), 0)
        self.assertEqual(main(["gaps", "ACME"]), 0)
        gaps = (self.temp / "workspaces" / "ACME" / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        self.assertIn("# Discovery Gaps - ACME", gaps)
        self.assertIn("## Client Response Sections", gaps)
        self.assertIn("### GAP-USERS", gaps)

    def test_resolve_gaps_closes_only_confirmed_structured_answers(self) -> None:
        fixture = ROOT / "fixtures" / "incomplete_requirement.md"
        self.assertEqual(main(["init", "ACME"]), 0)
        self.assertEqual(main(["ingest", "ACME", "--source", str(fixture)]), 0)

        response = self.temp / "client-gap-response.md"
        response.write_text(
            """# Client Gap Response

### GAP-USERS

- Answer: Primary users are operations analysts. Supervisors review summary status only.
- Owner / source: Product owner
- Evidence or reference: Workshop 2026-06-04
- Decision status: confirmed

### GAP-SCOPE

- Answer: Dashboard includes operational queues only; exports are out of scope for MVP.
- Owner / source: Product owner
- Evidence or reference: Workshop 2026-06-04
- Decision status: pending
""",
            encoding="utf-8",
        )

        self.assertEqual(main(["resolve-gaps", "ACME", "--source", str(response)]), 0)
        gaps = (self.temp / "workspaces" / "ACME" / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        self.assertIn("| GAP-USERS | business | high | CLOSED |", gaps)
        self.assertIn("| GAP-SCOPE | product | critical | ANSWERED |", gaps)
        self.assertEqual(main(["maturity", "ACME"]), 0)
        report = (self.temp / "workspaces" / "ACME" / "01_discovery" / "requirement_maturity_report.md").read_text(encoding="utf-8")
        self.assertIn("`BLOCKED`", report)

    def test_resolve_gaps_creates_traceable_seeds_decisions_and_report(self) -> None:
        fixture = ROOT / "fixtures" / "incomplete_requirement.md"
        self.assertEqual(main(["init", "ACME"]), 0)
        self.assertEqual(main(["ingest", "ACME", "--source", str(fixture)]), 0)

        response = self.temp / "client-gap-response.md"
        response.write_text(
            """# Client Gap Response

### GAP-USERS

- Answer: Primary users are operations analysts. Supervisors review summary status only.
- Owner / source: Product owner
- Evidence or reference: Workshop 2026-06-04
- Decision status: confirmed

### GAP-SCOPE

- Answer: Dashboard includes operational queues only; exports are out of scope for MVP.
- Owner / source: Product owner
- Evidence or reference: Workshop 2026-06-04
- Decision status: confirmed
""",
            encoding="utf-8",
        )

        self.assertEqual(main(["resolve-gaps", "ACME", "--source", str(response)]), 0)
        base = self.temp / "workspaces" / "ACME"
        self.assertTrue((base / "01_discovery" / "gap_resolution_log.md").exists())
        self.assertIn("AUTO-SEED", (base / "01_discovery" / "identity_seeds.md").read_text(encoding="utf-8"))
        self.assertIn("AUTO-DEC", (base / "01_discovery" / "decisions.md").read_text(encoding="utf-8"))
        graph = (base / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "identity_seed"', graph)
        self.assertIn('"type": "decision"', graph)
        self.assertIn('"relation": "confirms"', graph)
        report_files = list((base / "07_changes" / "00_client_responses").glob("*_gap_resolution_report.md"))
        self.assertTrue(report_files)

    def test_brief_context_request_status_export_and_retrieve_filters(self) -> None:
        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "NOVA"]), 0)
        self.assertEqual(main(["ingest", "NOVA", "--source", str(fixture)]), 0)
        self.assertEqual(main(["brief", "NOVA"]), 0)
        self.assertEqual(main(["context-request", "NOVA", "--domain", "technology"]), 0)
        self.assertEqual(main(["context-request", "NOVA", "--domain", "design"]), 0)
        self.assertEqual(main(["status", "NOVA"]), 0)
        self.assertEqual(main(["export", "NOVA", "--artifact", "brief", "--format", "md"]), 0)

        base = self.temp / "workspaces" / "NOVA"
        self.assertTrue((base / "02_requirements" / "project-brief.md").exists())
        tech_request = (base / "08_context_packs" / "requests" / "technology_context_request.md").read_text(encoding="utf-8")
        design_request = (base / "08_context_packs" / "requests" / "design_context_request.md").read_text(encoding="utf-8")
        self.assertIn("endpoints/events", tech_request)
        self.assertIn("repositories/components", tech_request)
        self.assertIn("journeys", design_request)
        self.assertIn("prototype", design_request)
        self.assertTrue((base / "08_context_packs" / "exports" / "project-brief.md").exists())
        self.assertTrue((base / "memory.lancedb" / "artifact_manifest.json").exists())

        results = ContextBroker("NOVA").retrieve(
            "SLA support leads",
            "discovery",
            language="unknown",
            sensitivity="internal",
            max_chars=120,
            summary_only=True,
        )
        self.assertTrue(results)
        self.assertLessEqual(sum(len(row["text"]) for row in results), 120)
        self.assertIn("why_retrieved", results[0])


if __name__ == "__main__":
    unittest.main()
