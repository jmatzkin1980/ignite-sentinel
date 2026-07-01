from __future__ import annotations

import unittest

from sentinel.validation import artifact_faithfulness_report, extract_atomic_claims


class FaithfulnessClaimTests(unittest.TestCase):
    def test_extract_atomic_claims_ignores_sources_and_headings(self) -> None:
        text = """
# Brief

- El portal permite registrar reclamos con motivo y descripcion.
- Fuente: 00_raw/client.md
| Campo | Valor |
| --- | --- |
| SLA | El SLA inicial es responder dentro de 48 horas habiles. |
"""
        claims = extract_atomic_claims(text)

        self.assertEqual(
            [claim["text"] for claim in claims],
            [
                "El portal permite registrar reclamos con motivo y descripcion",
                "El SLA inicial es responder dentro de 48 horas habiles",
            ],
        )

    def test_report_scores_faithful_artifact_as_complete(self) -> None:
        evidence = [
            {
                "source": "00_raw/client.md",
                "quote": "El portal permite registrar reclamos con motivo y descripcion.",
            },
            {
                "source": "00_raw/client.md",
                "quote": "El SLA inicial es responder dentro de 48 horas habiles.",
            },
        ]
        artifact = """
- El portal permite registrar reclamos con motivo y descripcion.
- El SLA inicial es responder dentro de 48 horas habiles.
"""

        report = artifact_faithfulness_report(artifact, evidence, artifact="project-brief.md")

        self.assertEqual(report["score"], 1.0)
        self.assertEqual(report["unsupported_claim_count"], 0)

    def test_report_exposes_silent_unsupported_claim(self) -> None:
        evidence = [
            {
                "source": "00_raw/client.md",
                "quote": "El portal permite registrar reclamos con motivo y descripcion.",
            }
        ]
        artifact = """
- El portal permite registrar reclamos con motivo y descripcion.
- El sistema asigna prioridad automaticamente usando IA.
"""

        report = artifact_faithfulness_report(artifact, evidence, artifact="project-brief.md")
        unsupported = [claim["text"] for claim in report["claims"] if not claim["supported"]]

        self.assertLess(report["score"], 1.0)
        self.assertEqual(report["unsupported_claim_count"], 1)
        self.assertIn("El sistema asigna prioridad automaticamente usando IA", unsupported)


if __name__ == "__main__":
    unittest.main()
