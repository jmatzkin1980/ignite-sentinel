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

import tempfile
import unittest
from pathlib import Path

from sentinel import adapters
from sentinel.adapters import load_manifest
from sentinel.core.markdown import parse_frontmatter
from sentinel.doctor import command_description_neutrality_check, surface_leaks

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_COMMAND_DIRS = (".claude/commands", ".kilo/commands")


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


if __name__ == "__main__":
    unittest.main()
