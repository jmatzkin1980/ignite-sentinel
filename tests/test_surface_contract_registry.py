"""IMP-236 (H12): guards for the registry of surface contracts.

The registry exists because the suite these tests belong to cannot cross the
surface boundary: nothing here invokes Kilo Code, Claude Code or Codex, so every
assertion about their config files says "our file is what we believe" and never
"the tool did what the file says". `kilo.jsonc` is the precedent — an
unrecognized top-level key, inert for seven weeks, `/doctor` green throughout.

These tests therefore guard what a test legitimately can: that every surface
contract present in the repo has an entry, that a new one is detected, and that
each entry carries a usable live procedure. They deliberately do NOT assert that
an `observed` date is true — no test can, and pretending otherwise would repeat
the defect the registry was built for.
"""

import json
import re
import tempfile
import unittest
from pathlib import Path

from sentinel.doctor import (
    CLAUDE_SETTINGS_SCHEMA_URL,
    SURFACE_CONTRACTS,
    SURFACE_CONTRACT_EXEMPT,
    SURFACE_CONTRACT_ROOTS,
    claude_settings_schema_check,
    discover_surface_contracts,
    surface_contract_registry_check,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ISO_DATE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")


class TheRegistryCoversThisRepo(unittest.TestCase):
    def test_repo_passes(self):
        check = surface_contract_registry_check(REPO_ROOT)
        self.assertEqual(check["status"], "PASS", check["detail"])

    def test_every_discovered_contract_is_registered_or_exempt(self):
        for path in discover_surface_contracts(REPO_ROOT):
            with self.subTest(path=path):
                self.assertTrue(
                    path in SURFACE_CONTRACTS or path in SURFACE_CONTRACT_EXEMPT,
                    f"{path} is read by a third-party surface but nothing says how it is verified",
                )

    def test_the_contracts_the_repo_ships_exist(self):
        for path, contract in SURFACE_CONTRACTS.items():
            if not contract.shipped:
                continue
            with self.subTest(path=path):
                self.assertTrue((REPO_ROOT / path).exists(), f"{path} is registered but absent")

    def test_the_four_surface_roots_are_swept(self):
        # Discovery is exhaustive inside the vendor-owned directories: that is
        # where a new contract actually appears (a new `.claude/output-styles/`).
        discovered = discover_surface_contracts(REPO_ROOT)
        for root in SURFACE_CONTRACT_ROOTS:
            if not (REPO_ROOT / root).is_dir():
                continue
            with self.subTest(root=root):
                self.assertTrue(
                    any(path.startswith(f"{root}/") for path in discovered),
                    f"{root} exists but discovery found nothing under it",
                )


class EveryEntryIsUsable(unittest.TestCase):
    def test_each_entry_names_its_surfaces_and_a_live_procedure(self):
        for path, contract in SURFACE_CONTRACTS.items():
            with self.subTest(path=path):
                self.assertTrue(contract.surfaces, f"{path} names no surface")
                # A procedure someone can follow, not a label.
                self.assertGreater(len(contract.live_check), 40, f"{path} has no usable live check")

    def test_observed_is_an_iso_date_or_explicitly_empty(self):
        # Empty means "nobody ever watched this work" — it must stay
        # distinguishable from a date, never be filled with a placeholder.
        for path, contract in SURFACE_CONTRACTS.items():
            with self.subTest(path=path):
                if contract.observed:
                    self.assertRegex(contract.observed, ISO_DATE)

    def test_every_exemption_states_a_reason(self):
        for path, reason in SURFACE_CONTRACT_EXEMPT.items():
            with self.subTest(path=path):
                self.assertGreater(len(reason), 20, f"{path} is exempt without a stated reason")

    def test_the_never_observed_count_is_reported(self):
        never = sum(1 for contract in SURFACE_CONTRACTS.values() if not contract.observed)
        detail = surface_contract_registry_check(REPO_ROOT)["detail"]
        self.assertIn(str(len(SURFACE_CONTRACTS)), detail)
        if never:
            self.assertIn("never observed live", detail)


class ANewContractIsDetected(unittest.TestCase):
    """Mutation: the check has to see a surface file nobody declared."""

    def test_an_unregistered_child_of_a_surface_root_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude" / "output-styles").mkdir(parents=True)
            check = surface_contract_registry_check(root)
            self.assertEqual(check["status"], "WARN")
            self.assertIn(".claude/output-styles", check["detail"])

    def test_an_unregistered_root_file_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "GEMINI.md").write_text("x", encoding="utf-8")
            check = surface_contract_registry_check(root)
            self.assertEqual(check["status"], "WARN")
            self.assertIn("GEMINI.md", check["detail"])

    def test_a_registered_contract_that_vanished_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            check = surface_contract_registry_check(root)
            self.assertEqual(check["status"], "WARN")
            self.assertIn("absent from the repo", check["detail"])
            self.assertIn("kilo.jsonc", check["detail"])

    def test_a_registered_contract_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "commands").mkdir()
            self.assertNotIn(".claude/commands", surface_contract_registry_check(root)["detail"])

    def test_the_exempt_authoring_source_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".codex" / "skills").mkdir(parents=True)
            self.assertNotIn(".codex/skills", surface_contract_registry_check(root)["detail"])

    def test_pycache_and_dotfiles_inside_a_surface_root_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".codex" / "__pycache__").mkdir(parents=True)
            (root / ".codex" / ".gitignore").write_text("x", encoding="utf-8")
            discovered = discover_surface_contracts(root)
            self.assertEqual(discovered, [])


class ClaudeSettingsDeclareThePublishedSchema(unittest.TestCase):
    """IMP-236 piece 3. The verdict on the vendor schema, verified against the
    installed Claude Code 2.1.208 binary rather than assumed: Anthropic publishes
    no settings-schema URL of its own, its settings parser accepts an optional
    `$schema` key (and passes unknown keys through), and SchemaStore's catalog
    carries the one URL that exists, matched to `**/.claude/settings.json`.
    """

    def test_repo_settings_declare_it(self):
        check = claude_settings_schema_check(REPO_ROOT)
        self.assertEqual(check["status"], "PASS", check["detail"])

    def test_the_declared_url_is_the_published_one(self):
        settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(settings["$schema"], CLAUDE_SETTINGS_SCHEMA_URL)
        # The IMP-179 hook policy has to survive the addition.
        self.assertIn("PreToolUse", settings["hooks"])

    def test_a_missing_declaration_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "settings.json").write_text('{ "hooks": {} }', encoding="utf-8")
            check = claude_settings_schema_check(root)
            self.assertEqual(check["status"], "WARN")
            self.assertIn("$schema", check["detail"])

    def test_a_different_url_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "settings.json").write_text('{ "$schema": "https://example.invalid/x.json" }', encoding="utf-8")
            check = claude_settings_schema_check(root)
            self.assertEqual(check["status"], "WARN")
            self.assertIn("example.invalid", check["detail"])

    def test_missing_or_unparseable_settings_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(claude_settings_schema_check(root)["status"], "WARN")
            (root / ".claude").mkdir()
            (root / ".claude" / "settings.json").write_text("{ not json", encoding="utf-8")
            self.assertEqual(claude_settings_schema_check(root)["status"], "WARN")


if __name__ == "__main__":
    unittest.main()
