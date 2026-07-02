import unittest

from sentinel.discovery import detect_gaps
from sentinel.lens_registry import load_smell_catalog


class WeakWordSmellTests(unittest.TestCase):
    def test_weak_quality_word_fires_with_location_and_mechanism(self):
        text = (
            "The expense approval workflow is for finance users. "
            "Quality matters and the request is successful once approvers are happy."
        )

        gap = next(g for g in detect_gaps(text) if g["id"] == "GAP-QUALITY-WEAK-WORD-SMELL")

        self.assertIn("Quality matters", gap["evidence_mention"])
        self.assertEqual(gap["smell_mechanism"], "names quality without testable expectation")
        self.assertEqual(gap["severity"], "low")

    def test_weak_business_rule_word_fires_with_location_and_mechanism(self):
        text = (
            "The scope is expense approval for finance users. "
            "There are business rules around thresholds."
        )

        gap = next(g for g in detect_gaps(text) if g["id"] == "GAP-BUSINESS-RULE-WEAK-WORD-SMELL")

        self.assertIn("business rules around thresholds", gap["evidence_mention"])
        self.assertEqual(
            gap["smell_mechanism"],
            "rule area named without thresholds, exceptions, or decision logic",
        )

    def test_clean_quality_text_does_not_fire_weak_word_smell(self):
        text = (
            "Scope is expense approval for finance users. "
            "Acceptance criteria: approval completes in under two minutes in 95 percent "
            "of normal requests, measured from submit to final approver decision."
        )

        gap_ids = {gap["id"] for gap in detect_gaps(text)}

        self.assertNotIn("GAP-QUALITY-WEAK-WORD-SMELL", gap_ids)
        self.assertNotIn("GAP-BUSINESS-RULE-WEAK-WORD-SMELL", gap_ids)

    def test_weak_word_catalog_loads_from_registry(self):
        catalog = load_smell_catalog()["weak_words"]

        self.assertIn("weak_quality_evidence", catalog["categories"])
        self.assertIn("weak_business_rule_evidence", catalog["categories"])


if __name__ == "__main__":
    unittest.main()
