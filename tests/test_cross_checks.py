"""IMP-260: deterministic cross-consistency of the brief v2."""

import sys
import unittest
from pathlib import Path

from sentinel.compilers.brief_v2 import render_brief_v2
from sentinel.cross_checks import rules, run_cross_checks

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from test_brief_v2_compiler import inputs  # noqa: E402

LOG = "Source log - X"


def cite(supports="x"):
    return f"[[sources § {LOG} # F-01 — supports: {supports}]]"


def brief(*sections):
    lines = ["<!-- sentinel-artifact: v2 -->", "# Project Brief — X", ""]
    for heading, body in sections:
        lines += [heading, ""] + list(body) + [""]
    return "\n".join(lines)


def status(text):
    return {r["id"]: (r["status"], r["issues"]) for r in run_cross_checks(text)}


class CatalogTests(unittest.TestCase):
    def test_ids_must_reach_their_target_places(self):
        text = brief(
            ("## 2. Business Lens", []),
            ("### 2.1 Actors and Goals by Role", [f"- R-1 lead and R-2 analyst read the queues. {cite()}"]),
            ("### 2.2 Critical Business Rules", [f"- RN-01 breach marks high risk; RN-02 refunds need approval. {cite()}"]),
            ("## 3. Product Lens", []),
            ("### 3.2 To-Be Process", [f"- Step 1 applies RN-01. {cite()}"]),
            ("## 4. Design Lens", []),
            ("### 4.1 Screen Flow", [f"- R-1 sees every queue. {cite()}"]),
            ("### 4.2 UX Considerations", [f"- ERR_QUEUE_STALE shows 'data is old'. {cite()}"]),
            ("## 5. Technical Lens", []),
            ("### 5.11 Governance and Constraints", [f"- R-2 reads only its queue. {cite()}"]),
            ("### 5.15 Error Handling and Status Codes", [f"- ERR_OTHER is retryable. {cite()}"]),
        )
        result = status(text)
        self.assertEqual(result["roles_named_alike"], ("PASS", []))
        self.assertEqual(result["rules_have_steps"][0], "WARN")
        self.assertIn("RN-02", result["rules_have_steps"][1][0])
        self.assertIn("ERR_QUEUE_STALE", result["error_codes_have_text"][1][0])

    def test_nothing_to_cross_is_skip_and_na_targets_skip(self):
        text = brief(("## 2. Business Lens", []), ("### 2.1 Actors and Goals by Role", [f"- R-1 lead. {cite()}"]),
                     ("## 4. Design Lens", []), ("### 4.1 Screen Flow", ["N/A — no screens. If one is added, it opens."]),
                     ("## 5. Technical Lens", []), ("### 5.11 Governance and Constraints", ["N/A — none. If any, it opens."]))
        result = status(text)
        self.assertEqual(result["roles_named_alike"][0], "SKIP")
        self.assertEqual(result["flags_in_parameters"][0], "SKIP")


class ScopeTests(unittest.TestCase):
    def test_build_items_trace_to_scope_and_exclusions_are_not_built(self):
        text = brief(
            ("## 6. Release Agreements", []),
            ("### 6.1 In Scope", [f"- Read-only dashboard. {cite()}", f"- Daily export. {cite()}"]),
            ("### 6.2 Out of Scope", [f"- Editing cases. {cite()}"]),
            ("## 9. Things to Build", []),
            ("### 9.1 Build List or Phases", [f"- `C-01` Read-only dashboard. {cite()} — depends on: none",
                                              f"- `C-02` Editing cases. {cite()} — depends on: none"]),
        )
        result = status(text)
        self.assertIn("C-02", result["build_within_scope"][1][0])
        self.assertIn("Daily export", result["scope_has_build_item"][1][0])
        self.assertIn("C-02", result["excluded_not_built"][1][0])
        self.assertIn("Editing cases", result["exclusion_has_destination"][1][0])

    def test_exclusion_with_destination_passes(self):
        text = brief(("## 6. Release Agreements", []),
                     ("### 6.2 Out of Scope", [f"- Editing cases — OUT OF SCOPE — returns in release 2 {cite()}"]))
        self.assertEqual(status(text)["exclusion_has_destination"], ("PASS", []))


class OtherRuleTests(unittest.TestCase):
    def test_priority_assumptions_and_technical_items(self):
        text = brief(
            ("## 2. Business Lens", []),
            ("### 2.3 Main Use Case", [f"- Must have: the daily view. {cite()}"]),
            ("## 3. Product Lens", []),
            ("### 3.2 To-Be Process", [f"- Priority: high for the export. {cite()}"]),
            ("## 5. Technical Lens", []),
            ("### 5.1 Architecture and Integrations", [f"- Reads the metrics service. {cite()}"]),
            ("## 8. Assumptions", []),
            ("### 8.1 Assumptions List", ["- `ASM-A` — used. (ASSUMED)", "- `ASM-B` — unused. (ASSUMED)"]),
            ("## 4. Design Lens", []),
            ("### 4.1 Screen Flow", ["- (inferred) One screen. (`ASM-A`)"]),
        )
        result = status(text)
        self.assertEqual(result["priority_only_in_2_3"][1], ["priority stated outside 2.3 (in 3.2)"])
        self.assertEqual(result["assumption_has_use"][1], ["assumption ASM-B is not used anywhere in the body"])
        self.assertEqual(result["technical_piece_has_item"][0], "WARN")

    def test_rules_are_data_and_v1_is_skipped(self):
        self.assertGreaterEqual(len(rules()), 14)
        self.assertEqual(run_cross_checks("# Brief\n\n## 1. Identity\n\n- claim\n"), [])


class CompiledBriefTests(unittest.TestCase):
    def test_compiled_brief_builds_only_what_is_in_scope(self):
        text, _ = render_brief_v2(inputs())
        result = status(text)
        for rule in ("build_within_scope", "scope_has_build_item", "excluded_not_built"):
            self.assertEqual(result[rule][0], "PASS", rule)
        self.assertEqual(result["exclusion_has_destination"][0], "WARN")  # the raw says "Out of scope: editing cases."

    def test_validate_reports_them_as_cross_consistency_warnings(self):
        import tempfile

        from sentinel.validation import cross_artifact_consistency

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "02_requirements").mkdir()
            (base / "02_requirements" / "project-brief.md").write_text(render_brief_v2(inputs())[0], encoding="utf-8")
            report = cross_artifact_consistency("X", base)
        ids = {c["id"]: c["status"] for c in report["checks"]}
        self.assertEqual(ids["brief_v2:exclusion_has_destination"], "WARN")
        self.assertTrue(any(w["check"] == "brief_v2:exclusion_has_destination" for w in report["warnings"]))


if __name__ == "__main__":
    unittest.main()
