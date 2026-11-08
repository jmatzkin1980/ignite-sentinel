"""IMP-283 — SECURITY.md, threat model and admin guide.

The documents are only useful while they match the code: every `/doctor` check,
browser storage key, log file and cleanup flag they cite must exist, and the
example managed settings must be a policy Claude Code accepts as written.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECURITY = ROOT / "SECURITY.md"
THREAT_MODEL = ROOT / "user_guide" / "19-threat-model.md"
ADMIN_GUIDE = ROOT / "user_guide" / "20-admin-guide.md"
POLICY = ROOT / "user_guide" / "references" / "managed-settings.json"
REPO = "jmatzkin1980/ignite-sentinel"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _doc_text() -> str:
    return "\n".join(_read(p) for p in (SECURITY, THREAT_MODEL, ADMIN_GUIDE))


class SecurityPolicyTests(unittest.TestCase):
    def test_reporting_channel_and_supported_versions(self) -> None:
        text = _read(SECURITY)
        self.assertIn("## Reporting a vulnerability", text)
        self.assertIn("private vulnerability reporting", text.lower())
        self.assertIn(f"https://github.com/{REPO}/security/advisories/new", text)
        self.assertIn("## Supported versions", text)
        self.assertNotRegex(text, r"[\w.+-]+@[\w-]+\.[\w.]+", "no personal e-mail in a public file")

    def test_links_to_threat_model_and_admin_guide(self) -> None:
        text = _read(SECURITY)
        self.assertIn("user_guide/19-threat-model.md", text)
        self.assertIn("user_guide/20-admin-guide.md", text)

    def test_readme_lists_the_three_documents(self) -> None:
        readme = _read(ROOT / "README.md")
        for target in ("SECURITY.md", "user_guide/19-threat-model.md", "user_guide/20-admin-guide.md"):
            self.assertIn(f"]({target})", readme)


class ThreatModelTests(unittest.TestCase):
    def test_assets(self) -> None:
        text = _read(THREAT_MODEL)
        self.assertIn("## Assets", text)
        self.assertIn("workspaces/", text)
        self.assertIn("localStorage", text)

    def test_every_threat_has_a_section(self) -> None:
        text = _read(THREAT_MODEL)
        for threat in (
            "Prompt injection through sources",
            "Path traversal and unconfined writes",
            "Secret leakage",
            "Supply chain",
            "Hooks",
            "Auto-update",
        ):
            self.assertRegex(text, rf"(?m)^### T\d+ — {re.escape(threat)}", threat)

    def test_every_threat_names_control_and_evidence(self) -> None:
        sections = re.split(r"(?m)^### ", _read(THREAT_MODEL))[1:]
        threats = [s for s in sections if s.startswith("T")]
        self.assertGreaterEqual(len(threats), 6)
        for section in threats:
            title = section.splitlines()[0]
            self.assertIn("**Control:**", section, title)
            self.assertIn("**Evidence:**", section, title)
            self.assertIn("**Residual risk:**", section, title)

    def test_storage_keys_match_the_views(self) -> None:
        text = _read(THREAT_MODEL)
        scripts = _read(ROOT / "sentinel" / "themes" / "templates" / "view.js") + _read(
            ROOT / "sentinel" / "themes" / "templates" / "shell.js"
        ) + _read(ROOT / "sentinel" / "themes" / "templates" / "shell.html")
        cited = set(re.findall(r"`(ignite-sentinel:[a-z-]+)", text))
        self.assertTrue(cited, "the threat model names the localStorage keys")
        for key in cited:
            self.assertIn(f'"{key}', scripts, key)


class CitationsExistTests(unittest.TestCase):
    """What the documents cite is real."""

    def test_doctor_checks(self) -> None:
        doctor = _read(ROOT / "sentinel" / "doctor.py")
        cited = set(re.findall(r"`(\w+_checks?)`", _doc_text()))
        self.assertTrue(cited)
        for name in cited:
            self.assertRegex(doctor, rf"def {name}\(", name)

    def test_workspace_logs(self) -> None:
        sources = "\n".join(_read(p) for p in (ROOT / "sentinel").rglob("*.py"))
        cited = set(re.findall(r"`(0\d_\w+/[\w.-]+\.md)`", _doc_text()))
        self.assertTrue(cited)
        for rel in cited:
            folder, name = rel.split("/")
            self.assertTrue(
                rel in sources or (folder in sources and name in sources), rel
            )

    def test_repo_paths(self) -> None:
        for rel in set(re.findall(r"`((?:tools|tests|sentinel|plugins|constraints|\.github|\.claude-plugin)/[\w./-]+)`", _doc_text())):
            self.assertTrue((ROOT / rel.rstrip("/")).exists(), rel)

    def test_clean_local_flags(self) -> None:
        tool = _read(ROOT / "tools" / "clean_local.py")
        cited = set(re.findall(r"(?m)^.*clean_local\.py.*$", _read(ADMIN_GUIDE)))
        flags = {f for line in cited for f in re.findall(r"--[a-z-]+", line)}
        self.assertIn("--include-workspaces", flags)
        for flag in flags:
            self.assertIn(f'"{flag}"', tool, flag)


class ManagedSettingsExampleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = json.loads(_read(POLICY))

    def test_marketplace_is_allowlisted_exactly_as_registered(self) -> None:
        # The allowlist matches repo, ref and path exactly, so the registered
        # source must be the same object or Claude Code refuses to register it.
        allow = self.policy["strictKnownMarketplaces"]
        registered = self.policy["extraKnownMarketplaces"]["ignite-sentinel"]
        self.assertIn(registered["source"], allow)
        self.assertEqual(registered["source"]["source"], "github")
        self.assertEqual(registered["source"]["repo"], REPO)
        self.assertRegex(registered["source"]["ref"], r"^v\d+\.\d+\.\d+$", "pinned to a release tag")
        self.assertIs(registered["autoUpdate"], False)

    def test_plugins_forced(self) -> None:
        self.assertEqual(
            self.policy["enabledPlugins"],
            {"ignite-sentinel@ignite-sentinel": True, "ignite-sentinel-mcp@ignite-sentinel": False},
        )

    def test_lockdown_keys(self) -> None:
        for key in ("disableSideloadFlags", "allowManagedHooksOnly", "disableCommandPluginSources"):
            self.assertIs(self.policy[key], True, key)

    def test_plugin_names_exist_in_the_marketplace(self) -> None:
        marketplace = json.loads(_read(ROOT / ".claude-plugin" / "marketplace.json"))
        names = {p["name"] for p in marketplace["plugins"]}
        self.assertEqual(marketplace["name"], "ignite-sentinel")
        for plugin_id in self.policy["enabledPlugins"]:
            self.assertIn(plugin_id.split("@")[0], names)

    def test_guide_embeds_the_example_verbatim(self) -> None:
        guide = _read(ADMIN_GUIDE)
        blocks = [json.loads(b) for b in re.findall(r"```json\n(.*?)```", guide, re.S)]
        self.assertIn(self.policy, blocks)

    def test_commit_pin_targets_the_plugin_directory(self) -> None:
        guide = _read(ADMIN_GUIDE)
        blocks = [json.loads(b) for b in re.findall(r"```json\n(.*?)```", guide, re.S)]
        pins = [
            entry["source"]
            for block in blocks
            for market in block.get("extraKnownMarketplaces", {}).values()
            if market["source"]["source"] == "settings"
            for entry in market["source"]["plugins"]
        ]
        self.assertTrue(pins, "the guide shows a commit-pinned settings catalog")
        for source in pins:
            self.assertEqual(source["source"], "git-subdir")
            self.assertEqual(source["path"], "plugins/ignite-sentinel")
            self.assertTrue((ROOT / source["path"] / ".claude-plugin" / "plugin.json").is_file())
            self.assertIn("sha", source)

    def test_guide_documents_every_requested_control(self) -> None:
        guide = _read(ADMIN_GUIDE)
        for needle in (
            "strictKnownMarketplaces",
            "enabledPlugins",
            "disableSideloadFlags",
            '"autoUpdate": false',
            '"sha"',
            "## Before you approve",
            "## Retention and cleanup",
            "## Audit trail",
            "/status",
            "Enterprise managed settings",
        ):
            self.assertIn(needle, guide, needle)


if __name__ == "__main__":
    unittest.main()
