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
        readiness = json.loads(readiness_pack.read_text(encoding="utf-8"))
        self.assertEqual(readiness["workflow"], "implementation_readiness")
        self.assertTrue(readiness["stories"])
        self.assertIn("retrieval_plan", readiness["stories"][0])
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
        self.assertIn("US-005", epic_text)
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
        self.assertIn('"id": "US-005"', graph)
        self.assertIn('"id": "TC-005"', graph)
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
        self.assertEqual(health["verdict"], "DIRTY")
        self.assertIn("Domain context changed after backlog generation", " ".join(health["findings"]))

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
        self.assertIn("| GAP-SCOPE | product | critical | PARTIALLY_CLOSED |", gaps)
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
