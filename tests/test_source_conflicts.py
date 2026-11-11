"""IMP-251: contradictions, echo, disguised proposals and cited-but-undelivered sources.

One fixture per finding: contradictory minutes, echo, a disguised proposal and a
cited document that never arrived. Each produces exactly its own finding.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery import parse_gap_rows
from sentinel.gap_resolution import resolve_gaps
from sentinel.source_conflicts import (
    AGREE,
    CONTRADICTION,
    ECHO_SOURCE_NOTE,
    SILENCE,
    UNVALIDATED_SOURCE_NOTE,
    classify_pair,
    cited_documents,
    declares_unvalidated,
    extract_statements,
    load_ledger,
    scope_for,
)
from sentinel.source_routing import default_authority
from sentinel.sync import sync_change

RAW = (
    "# Billing Portal\n\n"
    "Finance users need a portal to review monthly invoices before approval. "
    "Approval must be logged for audit.\n"
)


class PureTests(unittest.TestCase):
    def test_statements_read_copula_and_key_value_lines(self) -> None:
        found = extract_statements(
            "El plazo de entrega es de 30 días.\n"
            "SLA de respuesta: 24 horas\n"
            "Ana: thanks everyone, talk soon\n"
            "# El título es largo\n"
        )
        self.assertEqual([s["line"] for s in found], [1, 2])
        self.assertEqual(found[0]["subject_key"], "entrega|plazo")
        self.assertEqual(found[0]["value_key"], "#30")

    def test_speaker_prefix_does_not_hide_the_statement(self) -> None:
        found = extract_statements("Luis: el plazo de entrega es de 60 días\n")
        self.assertEqual(found[0]["subject_key"], "entrega|plazo")

    def test_pair_is_agree_contradiction_or_silence(self) -> None:
        a, b = extract_statements("el plazo de entrega es de 30 días\nel plazo de entrega es de 60 días\n")
        self.assertEqual(classify_pair(a, b), CONTRADICTION)
        self.assertEqual(classify_pair(a, dict(a)), AGREE)
        self.assertEqual(classify_pair(a, None), SILENCE)  # silence is its own value, never a contradiction

    def test_unvalidated_declaration_only_counts_at_the_top(self) -> None:
        self.assertTrue(declares_unvalidated("# Propuesta\n\nDocumento no validado con el cliente.\n"))
        self.assertTrue(declares_unvalidated("DRAFT - not validated\n\nThe fee is 2%.\n"))
        body = "\n".join(f"line {n}" for n in range(30)) + "\nthe old draft was discarded\n"
        self.assertFalse(declares_unvalidated(body))

    def test_citations_need_a_document_noun(self) -> None:
        found = cited_documents("Según el contrato de API de pagos, el límite es 100.\nSegún Juan, sí.\n")
        self.assertEqual(len(found), 1)
        self.assertIn("contrato", found[0]["tokens"])

    def test_scope_from_subject_keywords(self) -> None:
        self.assertEqual(scope_for("el plazo de entrega"), "business")
        self.assertEqual(scope_for("el endpoint de alta"), "api")
        self.assertEqual(scope_for("el color del botón"), "design")
        self.assertEqual(scope_for("la cosa"), "rule")

    def test_sentinel_outputs_are_own_artifacts(self) -> None:
        self.assertEqual(default_authority("external", "workspaces/X/02_requirements/project-brief.md"), "own_artifact")
        self.assertEqual(default_authority("meeting", "workspaces/X/07_changes/01_meetings/acta_impact_report.md"), "own_artifact")
        self.assertEqual(default_authority("meeting", "workspaces/X/07_changes/01_meetings/acta.md"), "minutes")
        self.assertEqual(default_authority("external", "input/requirements.md"), "unclassified")


class FlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        raw = self.temp / "billing.md"
        raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "CTR", "--brief-version", "1"]), 0)
        self.assertEqual(main(["ingest", "CTR", "--source", str(raw)]), 0)
        self.ws = self.temp / "workspaces" / "CTR"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _file(self, relative: str, text: str) -> Path:
        path = self.temp / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def _gaps(self) -> dict[str, dict[str, str]]:
        rows = parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))
        return {row["id"]: row for row in rows if row.get("id") != "NONE"}

    def test_contradictory_minutes_anchor_both_and_block_without_choosing(self) -> None:
        sync_change("CTR", self._file("01_meetings/acta-1.md", "# Acta 1\n\nEl plazo de entrega es de 30 días.\n"), "acta 1")
        result = sync_change("CTR", self._file("01_meetings/acta-2.md", "# Acta 2\n\nEl plazo de entrega es de 60 días.\n"), "acta 2")
        conflicts = result["source_conflicts"]
        self.assertEqual(len(conflicts["contradictions"]), 1)
        self.assertEqual(conflicts["cited_not_delivered"], [])
        gap = self._gaps()[conflicts["contradictions"][0]]
        self.assertEqual(gap["origin"], "contradiction")
        self.assertEqual(gap["severity"], "high")
        self.assertEqual(gap["status"], "OPEN")
        self.assertIn("30", gap["description"])
        self.assertIn("60", gap["description"])
        # Same authority on both sides: no rule settles it, and the newest never wins.
        self.assertIn("interim: none", gap["resolution_note"])
        item = load_ledger("CTR")["contradictions"][0]
        self.assertEqual(item["interim"]["status"], "unresolved")
        self.assertEqual(len(item["statements"]), 2)

        again = sync_change("CTR", self._file("01_meetings/acta-3.md", "# Acta 3\n\nEl plazo de entrega es de 90 días.\n"), "acta 3")
        self.assertEqual(again["source_conflicts"]["contradictions"], [])  # same topic, same gap
        self.assertEqual(len(load_ledger("CTR")["contradictions"][0]["statements"]), 3)

    def test_interim_value_follows_precedence(self) -> None:
        sync_change("CTR", self._file("02_technology_context/tl.md", "# TL\n\nEl plazo de entrega es de 45 días.\n"), "tl")
        sync_change("CTR", self._file("01_meetings/acta.md", "# Acta\n\nEl plazo de entrega es de 30 días.\n"), "acta")
        item = load_ledger("CTR")["contradictions"][0]
        self.assertEqual(item["scope"], "business")
        self.assertEqual(item["interim"]["status"], "resolved")
        self.assertEqual(item["interim"]["mark"], "⏳")
        self.assertIn("30", item["interim"]["value"])  # minutes govern business (P01)
        report = (self.ws / "01_discovery" / "contradictions.md").read_text(encoding="utf-8")
        self.assertIn("Interim value ⏳", report)

    def test_built_direction_marks_interim_with_warning(self) -> None:
        config = self.ws / "sentinel.config.yaml"
        config.write_text(config.read_text(encoding="utf-8") + "\nvalidation_direction: built\n", encoding="utf-8")
        sync_change("CTR", self._file("02_technology_context/tl.md", "# TL\n\nEl plazo de entrega es de 45 días.\n"), "tl")
        sync_change("CTR", self._file("01_meetings/acta.md", "# Acta\n\nEl plazo de entrega es de 30 días.\n"), "acta")
        self.assertEqual(load_ledger("CTR")["contradictions"][0]["interim"]["mark"], "⚠")

    def test_echo_adds_no_facts_and_cannot_close(self) -> None:
        gap_id = next(iter(self._gaps()))
        echo = self.ws / "02_requirements" / "echo-note.md"
        echo.write_text(
            f"# Echo\n\nEl plazo de entrega es de 10 días.\n\n### {gap_id}\n\n"
            "- Respuesta: The portal must keep every approval in the audit log for seven years.\n"
            "- Estado de decisión: confirmado\n",
            encoding="utf-8",
        )
        result = sync_change("CTR", echo, "echo")
        self.assertTrue(result["source_conflicts"]["echo"])
        self.assertEqual(load_ledger("CTR")["statements"], [])
        gap = self._gaps()[gap_id]
        self.assertEqual(gap["status"], "ANSWERED")
        self.assertEqual(gap["resolution_note"], ECHO_SOURCE_NOTE)

    def test_disguised_proposal_enters_as_proposal_and_cannot_close(self) -> None:
        gap_id = next(iter(self._gaps()))
        draft = self._file(
            "00_client_responses/respuestas.md",
            "# Respuestas (borrador, no validado)\n\nEl plazo de entrega es de 15 días.\n\n"
            f"### {gap_id}\n\n- Respuesta: The portal must keep every approval in the audit log for seven years.\n"
            "- Estado de decisión: confirmado\n",
        )
        resolution = resolve_gaps("CTR", draft)
        self.assertNotIn(gap_id, resolution["closed"])
        self.assertEqual(self._gaps()[gap_id]["resolution_note"], UNVALIDATED_SOURCE_NOTE)

        result = sync_change("CTR", self._file("01_meetings/draft.md", "# Draft - not validated\n\nEl plazo de entrega es de 15 días.\n"), "draft")
        self.assertTrue(result["source_conflicts"]["unvalidated"])
        self.assertEqual(result["source_conflicts"]["facts"], 0)
        self.assertEqual(result["source_conflicts"]["proposals"], 1)
        self.assertEqual(result["source_conflicts"]["contradictions"], [])

    def test_new_technical_name_is_a_proposal_until_ratified(self) -> None:
        result = sync_change("CTR", self._file("01_meetings/acta.md", "# Acta\n\nEl servicio de cobro es `billingGateway`.\n"), "acta")
        self.assertEqual(result["source_conflicts"]["proposals"], 1)
        statement = load_ledger("CTR")["statements"][0]
        self.assertEqual(statement["reason"], "new-technical-name")

    def test_cited_document_never_delivered_opens_a_gap_with_who_to_ask(self) -> None:
        main(["sources", "CTR", "--id", "F-01", "--from", "Ana (cliente)"])
        source = self._file("01_meetings/acta.md", "# Acta\n\nSegún el contrato de API de pagos, los reintentos son tres.\n")
        result = sync_change("CTR", source, "acta")
        self.assertEqual(len(result["source_conflicts"]["cited_not_delivered"]), 1)
        gap = self._gaps()[result["source_conflicts"]["cited_not_delivered"][0]]
        self.assertEqual(gap["origin"], "cited_not_delivered")
        self.assertIn("contrato de api de pagos", gap["question"])
        self.assertIn("source silence", gap["description"])

        delivered = self._file("02_technology_context/contrato-api-pagos.md", "# Contrato\n\nPOST /pagos\n")
        sync_change("CTR", delivered, "contract")
        later = sync_change("CTR", self._file("01_meetings/acta-2.md", "# Acta 2\n\nSegún el contrato de API de pagos, ok.\n"), "acta 2")
        self.assertEqual(later["source_conflicts"]["cited_not_delivered"], [])

    def test_schema_origin_enum_matches_code(self) -> None:
        schema = json.loads(Path(self.old_cwd / "sentinel" / "schemas" / "gap.schema.json").read_text(encoding="utf-8"))
        origins = set(schema["properties"]["origin"]["enum"])
        for origin in ("checklist", "agent", "challenge", "scrutiny", "implementability-probe", "self-review",
                       "sync", "injection_signal", "contradiction", "cited_not_delivered"):
            self.assertIn(origin, origins)


if __name__ == "__main__":
    unittest.main()
