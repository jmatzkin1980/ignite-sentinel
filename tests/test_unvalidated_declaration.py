"""IMP-390: a source is unvalidated only when it declares itself so, or says so in metadata.

Mentioning "borrador"/"draft" as a topic (a "Save draft" feature) never counts.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery import parse_gap_rows
from sentinel.gap_resolution import resolve_gaps
from sentinel.source_conflicts import declares_unvalidated

POSITIVE = {
    "heading": "# Borrador de requerimientos\n\nEl plazo es 30 días.\n",
    "estado": "Estado: borrador\n\nEl plazo es 30 días.\n",
    "bullet status": "- status: draft\n\nEl plazo es 30 días.\n",
    "frontmatter": "---\ntitle: Alta\nstatus: draft\n---\n\nEl plazo es 30 días.\n",
    "mark alone": "BORRADOR\n\nEl plazo es 30 días.\n",
    "bracket mark": "[DRAFT]\n\nThe term is 30 days.\n",
    "bold mark": "**Borrador**\n\nEl plazo es 30 días.\n",
    "self es": "Este documento es un borrador.\n",
    "self is still": "This document is still a draft.\n",
    "self en estado": "Este archivo está en estado de borrador.\n",
    "state phrase": "Respuestas sin validar\n",
    "state phrase en": "Not yet validated\n",
}
NEGATIVE = {
    "answer line": '- Respuesta: Cuando el usuario presiona "Guardar borrador", el sistema debe…\n',
    "prose": "El usuario puede guardar un borrador del alta.\n",
    "table": 'nuevo | pantalla | Botón "Guardar borrador"\n',
    "english": "Users can save a draft and resume later.\n",
    "body only": "# Alta de proveedores\n\nEl analista puede guardar el borrador del formulario.\n",
    "evidence line": "- Evidencia o referencia: pantalla de borrador\n",
    "non metadata key": "Nota: el borrador se guarda solo\n",
}


class DeclarationTests(unittest.TestCase):
    def test_self_declaration_or_metadata_counts(self) -> None:
        for name, text in POSITIVE.items():
            with self.subTest(name):
                self.assertTrue(declares_unvalidated(text))

    def test_mentioning_the_word_as_a_topic_does_not_count(self) -> None:
        for name, text in NEGATIVE.items():
            with self.subTest(name):
                self.assertFalse(declares_unvalidated(text))

    def test_only_the_first_citable_lines_count(self) -> None:
        body = "\n".join(f"line {n}" for n in range(20)) + "\nEstado: borrador\n"
        self.assertFalse(declares_unvalidated(body))


class ResolveGapsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        raw = self.temp / "billing.md"
        raw.write_text("# Billing Portal\n\nFinance users review monthly invoices before approval.\n", encoding="utf-8")
        self.assertEqual(main(["init", "CTR", "--brief-version", "1"]), 0)
        self.assertEqual(main(["ingest", "CTR", "--source", str(raw)]), 0)
        self.ws = self.temp / "workspaces" / "CTR"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _gaps(self) -> dict[str, dict[str, str]]:
        rows = parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))
        return {row["id"]: row for row in rows if row.get("id") != "NONE"}

    def test_a_save_draft_mention_in_the_opening_lines_still_closes_confirmed_gaps(self) -> None:
        gap_id = next(iter(self._gaps()))
        path = self.temp / "00_client_responses" / "respuestas.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '# Respuestas del cliente\n\nEl botón "Guardar borrador" guarda lo tipeado.\n\n'
            f"### {gap_id}\n\n- Respuesta: The portal must keep every approval in the audit log for seven years.\n"
            "- Estado de decisión: confirmado\n",
            encoding="utf-8",
        )
        resolution = resolve_gaps("CTR", path)
        self.assertIn(gap_id, resolution["closed"])


if __name__ == "__main__":
    unittest.main()
