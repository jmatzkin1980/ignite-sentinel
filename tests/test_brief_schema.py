"""IMP-252: the brief v2 schema as data, its combination rules and the brief settings."""
from __future__ import annotations

import copy
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from sentinel.brief_schema import (
    SETTINGS_GAP_ID,
    applicability,
    combine,
    effective_validation_direction,
    ids_lock_problems,
    load_brief_schema,
    load_ids_lock,
    resolve_genesis,
    schema_ids,
    settings_issues,
    settings_status,
    subsections,
    validate_schema,
)
from sentinel.cli import main
from sentinel.doctor import brief_schema_check
from sentinel.mcp import run_cli
from sentinel.workspace import read_state

RAW = "# Billing Portal\n\nFinance users review monthly invoices on a dashboard screen before approval. Approval must be logged.\n"

# Framework structure §4.2: required · conditional · N/A per profile, over 57 entries.
FRAMEWORK_COUNTS = {
    "UI": (35, 20, 2), "API": (29, 16, 12), "BAT": (29, 14, 14), "INT": (28, 17, 12),
    "MIG": (33, 22, 2), "REG": (27, 29, 1), "MT": (30, 26, 1),
}


def _run(argv: list[str]) -> tuple[int, dict]:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(argv)
    text = out.getvalue()
    return code, (json.loads(text[text.index("{"):]) if "{" in text else {})


def _profile_only_counts(profile: str) -> tuple[int, int, int]:
    # With a "·" genesis everywhere the result is the profile mark alone.
    schema = copy.deepcopy(load_brief_schema())
    for sub in subsections(schema):
        sub.pop("genesis", None)
        for block in sub.get("blocks", []):
            block.pop("genesis", None)
    summary = applicability([profile], "brownfield-replacement" if profile == "MIG" else "greenfield", schema)["summary"]
    return summary["required"], summary["conditional"], summary["n/a"]


class SchemaTests(unittest.TestCase):
    def test_the_schema_is_well_formed_and_matches_its_id_golden(self) -> None:
        self.assertEqual(validate_schema(), [])
        self.assertEqual(ids_lock_problems(), [])
        self.assertEqual(len(subsections(annexes=False)), 55)
        self.assertEqual(len(subsections()), 57)
        self.assertEqual(schema_ids(), load_ids_lock()["ids"])
        self.assertEqual(brief_schema_check()["status"], "PASS")

    def test_profile_marks_reproduce_the_framework_counts(self) -> None:
        for profile, expected in FRAMEWORK_COUNTS.items():
            self.assertEqual(_profile_only_counts(profile), expected, profile)

    def test_every_entry_has_bilingual_titles_and_a_contract(self) -> None:
        for sub in subsections():
            self.assertTrue(sub["title"]["es"] and sub["title"]["en"], sub["id"])
            self.assertIn(sub["contract"]["missing"], {"client", "domain"}, sub["id"])
            for block in sub.get("blocks", []):
                self.assertTrue(block["title"]["es"] and block["title"]["en"], block["key"])

    def test_id_golden_guards_the_evolution_policy(self) -> None:
        schema = copy.deepcopy(load_brief_schema())
        removed = schema["sections"][1]["subsections"].pop()  # 1.5 disappears
        self.assertTrue(any("1.5 disappeared" in p for p in ids_lock_problems(schema)))
        schema["evolution"]["tombstones"] = [{"id": "1.5", "reason": "test"}, {"id": "1.5/criteria"}, {"id": "1.5/executable"}]
        self.assertEqual(ids_lock_problems(schema), [])
        schema["sections"][1]["subsections"].append(removed)  # reusing a tombstone
        self.assertTrue(any("cannot be reused" in p for p in ids_lock_problems(schema)))
        fresh = copy.deepcopy(load_brief_schema())
        fresh["sections"][9]["subsections"][0]["blocks"].append({"key": "new", "title": {"es": "x", "en": "x"}, "applies": "x", "profiles": "◐" * 7})
        self.assertTrue(any("not in brief_v2_ids.lock.json" in p for p in ids_lock_problems(fresh)))


class CombinationTests(unittest.TestCase):
    def test_combine_table(self) -> None:
        cases = {
            ("◐", "●"): ("●", False), ("●", "—"): ("—", False), ("◐", "—"): ("—", False),
            ("●", "Δ"): ("●", True), ("—", "Δ"): ("—", False), ("—", "◐"): ("—", False),
            ("●", "◐"): ("●", False), ("◐", "◐"): ("◐", False), ("◐", "·"): ("◐", False),
        }
        for (profile, genesis), expected in cases.items():
            self.assertEqual(combine(profile, genesis), expected, (profile, genesis))

    def test_several_profiles_take_the_strongest_mark(self) -> None:
        entries = applicability(["UI", "BAT"], "greenfield")["entries"]
        self.assertEqual(entries["4.1"]["mark"], "required")  # UI
        self.assertEqual(entries["2.5"]["mark"], "required")  # BAT
        self.assertEqual(entries["5.12"]["blocks"]["jobs"]["mark"], "required")
        self.assertEqual(entries["5.12"]["blocks"]["client_state"]["mark"], "required")

    def test_genesis_raises_lowers_and_reshapes(self) -> None:
        integration = applicability(["UI"], "brownfield-integration")["entries"]
        self.assertEqual(integration["1.4"]["mark"], "required")  # ◐ profile, ● genesis
        greenfield = applicability(["UI"], "greenfield")["entries"]
        self.assertEqual(greenfield["5.5"]["mark"], "n/a")  # genesis — wins
        self.assertEqual(greenfield["3.2"]["mark"], "required")  # an N/A sub-block never switches its parent off
        self.assertEqual(greenfield["3.2"]["blocks"]["cutover"]["mark"], "n/a")
        extension = applicability(["UI"], "brownfield-extension")["entries"]
        self.assertIn("column by column", extension["5.4"]["blocks"]["model"]["fill_note"])  # Δ
        self.assertEqual(extension["5.17"]["mark"], "n/a")  # genesis ◐ with profile — stays N/A
        self.assertEqual(extension["5.7"]["blocks"]["versioning"]["mark"], "required")

    def test_na_is_grouped_with_its_counterfactual(self) -> None:
        result = applicability(["API"], "greenfield")
        groups = {line["group"]: line for line in result["na_lines"]}
        self.assertIn("no_ui", groups)
        self.assertIn("5.12/client_state", groups["no_ui"]["members"])
        self.assertTrue(groups["no_ui"]["line"]["es"].startswith("N/A — el proyecto no tiene superficie"))
        self.assertEqual(result["na_ungrouped"], [])
        batch = {line["group"] for line in applicability(["BAT"], "greenfield")["na_lines"]}
        self.assertIn("no_api_batch", batch)

    def test_mig_implies_replacement(self) -> None:
        self.assertTrue(any("contradiction" in issue for issue in settings_issues(["MIG"], "greenfield")))
        self.assertEqual(settings_issues(["MIG"], "brownfield-replacement"), [])
        self.assertEqual(settings_issues(["BAT"], "greenfield"), [])  # an initial load in greenfield is not MIG

    def test_mixed_genesis_declares_the_most_demanding(self) -> None:
        self.assertEqual(resolve_genesis(["brownfield-integration", "brownfield-extension"]),
                         {"genesis": "brownfield-extension", "also": ["brownfield-integration"]})
        with self.assertRaisesRegex(ValueError, "unknown genesis"):
            resolve_genesis(["sideways"])

    def test_combined_fixtures_measure_what_stays_pending(self) -> None:
        # The volume a fresh project of each kind must fill (required + conditional), and what is N/A.
        expected = {
            ("UI+BAT", "greenfield"): {"required": 37, "conditional": 17, "n/a": 3},
            ("REG", "brownfield-extension"): {"required": 31, "conditional": 25, "n/a": 1},
            ("MIG", "brownfield-replacement"): {"required": 34, "conditional": 21, "n/a": 2},
        }
        for (profiles, genesis), summary in expected.items():
            self.assertEqual(applicability(profiles.split("+"), genesis)["summary"], summary, profiles)


class SettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        raw = self.temp / "billing.md"
        raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(_run(["init", "BRV2"])[0], 0)
        self.assertEqual(_run(["ingest", "BRV2", "--source", str(raw)])[0], 0)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_unconfirmed_settings_show_a_proposal_and_the_blocking_gap(self) -> None:
        code, result = _run(["brief", "BRV2"])
        self.assertEqual(code, 0)
        status = result["brief_settings"]
        self.assertFalse(status["confirmed"])
        self.assertIn("UI", status["proposal"]["profiles"])
        self.assertEqual(status["gap"]["id"], SETTINGS_GAP_ID)
        self.assertTrue(status["gap"]["blocking"])
        self.assertNotIn("brief_settings", read_state("BRV2"))  # a proposal is never applied

    def test_the_ba_confirms_them(self) -> None:
        brief = self.temp / "workspaces" / "BRV2" / "02_requirements" / "project-brief.md"
        _run(["brief", "BRV2"])
        before = brief.read_text(encoding="utf-8")
        code, result = _run(["brief", "BRV2", "--profile", "ui,reg", "--genesis", "brownfield-integration,brownfield-extension"])
        self.assertEqual(code, 0)
        status = result["brief_settings"]
        self.assertTrue(status["confirmed"])
        self.assertEqual(status["settings"]["profiles"], ["UI", "REG"])
        self.assertEqual(status["settings"]["genesis"], "brownfield-extension")
        self.assertEqual(status["settings"]["genesis_also"], ["brownfield-integration"])
        self.assertEqual(status["applicability"]["required"] + status["applicability"]["conditional"] + status["applicability"]["n/a"], 57)
        self.assertEqual(brief.read_text(encoding="utf-8"), before)  # the v1 brief is untouched
        code, result = _run(["brief", "BRV2", "--validation-direction", "built"])  # partial update keeps the rest
        self.assertEqual(result["brief_settings"]["settings"]["profiles"], ["UI", "REG"])
        self.assertEqual(effective_validation_direction("BRV2", {"validation_direction": "to-build"}), "built")

    def test_contradiction_and_bad_values(self) -> None:
        code, result = _run(["brief", "BRV2", "--profile", "MIG", "--genesis", "greenfield"])
        self.assertEqual(code, 0)
        status = result["brief_settings"]
        self.assertFalse(status["confirmed"])
        self.assertIn("contradiction", status["contradictions"][0])
        self.assertIn("contradiction", status["gap"]["reason"])
        self.assertEqual(_run(["brief", "BRV2", "--profile", "XYZ", "--genesis", "greenfield"])[0], 1)

    def test_mcp_passes_the_settings(self) -> None:
        result = run_cli(["brief", "BRV2", "--profile", "API", "--genesis", "greenfield"])
        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(result["output"]["brief_settings"]["confirmed"])
        self.assertTrue(settings_status("BRV2")["confirmed"])


if __name__ == "__main__":
    unittest.main()
