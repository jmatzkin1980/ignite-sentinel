"""IMP-224 (H12): anti-leak guards for the command metadata mirrored to every surface.

`description` is the single string a user reads in the autocomplete of Claude,
Kilo and Codex alike, and all three are generated from one manifest entry. Two
of the 33 descriptions named a concrete surface (`doctor` claimed to validate
"this VS Code workspace", `sentinel` advertised "one generic Kilo workflow"), so
they were wrong on two surfaces out of three. The repo has carried this
invariant for *skills* since IMP-163 (`skill_metadata_checks`); commands had no
equivalent, which is precisely why the leak survived. These guards close that
asymmetry — in the manifest (source) and in the generated adapters (what the
user actually reads).
"""

import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path

from sentinel import adapters, cli
from sentinel.adapters import load_manifest, runtime_command_names
from sentinel.core.markdown import parse_frontmatter
from sentinel.doctor import command_description_neutrality_check, surface_leaks

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_COMMAND_DIRS = (".claude/commands", ".kilo/commands")
# The two commands whose parser takes no `project_id` (IMP-225).
PORTFOLIO_COMMANDS = frozenset({"dashboard", "doctor"})
# Manifest entry with no argparse subcommand: the generic chat router.
ROUTER_COMMAND = "sentinel"


def _usage(command: str) -> str:
    """Return the real argparse usage line for a runtime command.

    `cli.main` builds the parser internally, so the usage is captured the way a
    user would see it — `--help` under redirect_stdout — rather than by
    re-declaring the signature anywhere. That is the whole point: the hint is
    checked against the parser, not against a second hand-written copy.
    """
    buffer = io.StringIO()
    with contextlib.suppress(SystemExit), contextlib.redirect_stdout(buffer):
        cli.main([command, "--help"])
    return " ".join(buffer.getvalue().split("\n\n")[0].split())


def _required_options(usage: str) -> list[str]:
    """Options argparse prints unbracketed, i.e. `required=True`."""
    stripped = re.sub(r"\[[^\]]*\]", " ", usage)
    return re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", stripped)


def _choice_sets(usage: str) -> dict[str, set[str]]:
    """Map each option to the choice set argparse advertises, e.g. `{a,b,c}`."""
    return {
        option: set(choices.split(","))
        for option, choices in re.findall(r"(--[a-z][a-z-]*) \{([^}]+)\}", usage)
    }


class SurfaceLeakDetector(unittest.TestCase):
    def test_flags_every_generated_surface(self):
        for text, expected in (
            ("Run it from one generic Kilo workflow.", "Kilo"),
            ("Ready in this VS Code workspace.", "VS Code"),
            ("Ready in this vscode workspace.", "vscode"),
            ("Ask Claude to run it.", "Claude"),
            ("Ask Codex to run it.", "Codex"),
            ("Open it in Cursor.", "Cursor"),
            ("Open it in Gemini.", "Gemini"),
        ):
            self.assertEqual(surface_leaks(text), [expected], f"missed leak in {text!r}")

    def test_reports_each_distinct_surface_once(self):
        self.assertEqual(surface_leaks("Kilo and Claude and Kilo again"), ["Kilo", "Claude"])

    def test_repo_file_citations_are_not_leaks(self):
        # A description may legitimately point at the rules files; naming the
        # file is not a claim about which agent is running.
        self.assertEqual(surface_leaks("The rules are in AGENTS.md and CLAUDE.md."), [])

    def test_ordinary_prose_does_not_trip_the_detector(self):
        for benign in ("codexes of medieval law", "the cursorless flow", "kilobytes of evidence"):
            self.assertEqual(surface_leaks(benign), [], f"false positive on {benign!r}")


class ManifestDescriptionsAreSurfaceNeutral(unittest.TestCase):
    def test_no_manifest_description_names_a_surface(self):
        offenders = {
            entry["name"]: leaks
            for entry in load_manifest()["commands"]
            if (leaks := surface_leaks(str(entry.get("description", ""))))
        }
        self.assertEqual(offenders, {}, f"manifest descriptions leak a surface: {offenders}")

    def test_generated_adapters_expose_neutral_descriptions(self):
        # What the manifest holds only matters because it is mirrored; assert on
        # the files each surface actually reads.
        for directory in GENERATED_COMMAND_DIRS:
            files = sorted((REPO_ROOT / directory).glob("*.md"))
            self.assertTrue(files, f"no generated commands in {directory}")
            for path in files:
                description = str(
                    parse_frontmatter(path.read_text(encoding="utf-8-sig")).get("description", "")
                )
                self.assertEqual(
                    surface_leaks(description),
                    [],
                    f"{directory}/{path.name} shows a surface-specific description",
                )


class DoctorReportsDescriptionNeutrality(unittest.TestCase):
    def test_repo_manifest_passes(self):
        check = command_description_neutrality_check()
        self.assertEqual(check["status"], "PASS", check["detail"])

    def test_doctor_warns_and_names_the_offending_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            leaky = Path(tmp) / "commands_manifest.json"
            leaky.write_text(
                '{"version": 1, "commands": ['
                '{"name": "doctor", "description": "Ready in this VS Code workspace.", "body": "x"},'
                '{"name": "init", "description": "Create a new Sentinel project workspace.", "body": "x"}'
                "]}",
                encoding="utf-8",
            )
            original = adapters.MANIFEST_PATH
            adapters.MANIFEST_PATH = leaky
            try:
                check = command_description_neutrality_check()
            finally:
                adapters.MANIFEST_PATH = original
            self.assertEqual(check["status"], "WARN")
            self.assertIn("/doctor", check["detail"])
            self.assertIn("VS Code", check["detail"])
            self.assertNotIn("/init", check["detail"])

    def test_doctor_warns_when_the_manifest_is_unreadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "commands_manifest.json"
            broken.write_text("{ not json", encoding="utf-8")
            original = adapters.MANIFEST_PATH
            adapters.MANIFEST_PATH = broken
            try:
                check = command_description_neutrality_check()
            finally:
                adapters.MANIFEST_PATH = original
            self.assertEqual(check["status"], "WARN")


class ArgumentHintsMatchTheRealParser(unittest.TestCase):
    """IMP-225 (H12): `argument-hint` is the signature a Claude Code user reads in
    the autocomplete, so a hand-written one is a third copy of the signature
    (parser -> body -> hint) and repeats the anti-pattern H10 punished in
    `test_doctor_commands_surface_derives_from_runtime` (a hardcoded list stuck
    at 29 while the runtime already exposed 32). These guards anchor every hint
    to the usage argparse actually prints.
    """

    def setUp(self):
        self.hints = {entry["name"]: entry.get("argument_hint", "") for entry in load_manifest()["commands"]}

    def test_every_command_declares_a_hint(self):
        missing = sorted(name for name, hint in self.hints.items() if not hint.strip())
        self.assertEqual(missing, [], f"commands without argument-hint: {missing}")

    def test_hint_names_every_required_option_of_the_parser(self):
        for command in runtime_command_names():
            usage = _usage(command)
            for option in _required_options(usage):
                self.assertIn(
                    option,
                    self.hints[command],
                    f"/{command} hint omits required {option} (usage: {usage})",
                )

    def test_hint_only_promises_project_id_where_the_parser_takes_one(self):
        for command in runtime_command_names():
            hint = self.hints[command]
            takes_project = "project_id" in _usage(command)
            self.assertEqual(
                takes_project,
                "PROJECT_ID" in hint,
                f"/{command} hint disagrees with the parser about PROJECT_ID: {hint!r}",
            )
        # The router is manifest-only (no argparse subcommand) and does take one.
        self.assertIn("PROJECT_ID", self.hints[ROUTER_COMMAND])
        for command in PORTFOLIO_COMMANDS:
            self.assertNotIn("PROJECT_ID", self.hints[command])

    def test_enumerated_choices_match_the_parser(self):
        # A hint that spells out `a|b|c` must spell out the real choice set —
        # otherwise adding an artifact type silently leaves the hint lying.
        checked = 0
        for command in runtime_command_names():
            hint = self.hints[command]
            for option, choices in _choice_sets(_usage(command)).items():
                match = re.search(rf"{re.escape(option)} ([a-z|-]+)", hint)
                if not match or "|" not in match.group(1):
                    continue
                self.assertEqual(
                    set(match.group(1).split("|")),
                    choices,
                    f"/{command} hint enumerates stale choices for {option}",
                )
                checked += 1
        self.assertGreaterEqual(checked, 3, "expected view/export/context-request to enumerate choices")

    def test_claude_frontmatter_carries_the_hint_and_kilo_does_not(self):
        for name, hint in self.hints.items():
            claude = parse_frontmatter((REPO_ROOT / ".claude" / "commands" / f"{name}.md").read_text(encoding="utf-8-sig"))
            self.assertEqual(claude.get("argument-hint"), hint, f"{name}.md hint out of sync with the manifest")
            kilo = parse_frontmatter((REPO_ROOT / ".kilo" / "commands" / f"{name}.md").read_text(encoding="utf-8-sig"))
            self.assertNotIn("argument-hint", kilo, f"argument-hint leaked into the Kilo adapter for {name}")

    def test_arguments_channel_survives_the_new_frontmatter(self):
        # `$ARGUMENTS` is the only channel by which a body receives arguments;
        # `argument-hint` is display-only and must not have displaced it.
        for name in self.hints:
            text = (REPO_ROOT / ".claude" / "commands" / f"{name}.md").read_text(encoding="utf-8-sig")
            self.assertIn("Arguments received from the user invocation: `$ARGUMENTS`", text, name)


if __name__ == "__main__":
    unittest.main()
