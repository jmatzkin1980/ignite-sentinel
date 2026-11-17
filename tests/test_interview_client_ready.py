"""IMP-344: the interview export is the list of questions a BA can send to the client.

It leaves out the BA's own brief settings gap (its question is a CLI command), names no
internal improvement id, and every catalogue gap it shows asks a specific question instead
of the generic fallback.
"""
import unittest

GENERIC = ("What confirmed information resolves this uncertainty?", "¿Qué información confirmada resuelve esta incertidumbre?")
PRD_GAPS = ("GAP-PRD-PERSONA-DETAIL", "GAP-PRD-FR-AC", "GAP-PRD-NFR-KPI", "GAP-PRD-DEPENDENCIES-ROADMAP")


def rows():
    gaps = [{"id": "GAP-BRIEF-PROFILE", "lens": "product", "severity": "critical", "status": "OPEN",
             "question": "Confirm the brief profile(s) and genesis: /brief PROJECT_ID --profile UI,REG --genesis greenfield"},
            {"id": "GAP-ACCEPTANCE", "lens": "quality", "severity": "critical", "status": "OPEN", "question": ""}]
    gaps += [{"id": gap, "lens": "product", "severity": "medium", "status": "OPEN", "question": ""} for gap in PRD_GAPS]
    return gaps


class InterviewClientReadyTest(unittest.TestCase):
    def test_interview_script_reads_for_a_client(self):
        from sentinel.discovery import render_interview_script

        for language in ("en", "es"):
            text = render_interview_script("CLIENT", rows(), language)
            self.assertNotIn("GAP-BRIEF-PROFILE", text, language)
            self.assertNotIn("/brief", text, language)
            self.assertNotIn("IMP-", text, language)
            for generic in GENERIC:
                self.assertNotIn(generic, text, language)
            for gap in PRD_GAPS:
                self.assertIn(gap, text, language)

    def test_prd_gaps_have_their_own_question(self):
        from sentinel.gaps import question_for_gap

        for language in ("en", "es"):
            for gap in PRD_GAPS:
                self.assertNotIn(question_for_gap(gap, language), GENERIC, (gap, language))


if __name__ == "__main__":
    unittest.main()
