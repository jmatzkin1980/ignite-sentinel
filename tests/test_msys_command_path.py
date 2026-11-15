"""IMP-315: Git Bash (MSYS) rewrites a leading `/init` into a Windows path before
Python sees it (`C:/Program Files/Git/init`). Claude Code on Windows runs the
plugin's commands through Git Bash, so the CLI must read that path back as the
command."""

import unittest

from sentinel.cli import normalize_slash_command


class MsysCommandPathTest(unittest.TestCase):
    def test_slash_command_is_unchanged(self):
        self.assertEqual(normalize_slash_command(["/init", "walk"]), ["init", "walk"])

    def test_git_bash_path_is_read_as_the_command(self):
        self.assertEqual(
            normalize_slash_command(["C:/Program Files/Git/init", "walk"]),
            ["init", "walk"],
        )

    def test_other_msys_roots_and_backslashes(self):
        self.assertEqual(
            normalize_slash_command(["D:\\tools\\msys64\\ingest", "walk", "--source", "r.md"]),
            ["ingest", "walk", "--source", "r.md"],
        )
        self.assertEqual(normalize_slash_command(["C:/msys64/doctor"]), ["doctor"])

    def test_hyphenated_command(self):
        self.assertEqual(
            normalize_slash_command(["C:/Program Files/Git/resolve-gaps", "walk"]),
            ["resolve-gaps", "walk"],
        )

    def test_unknown_basename_or_relative_path_is_left_alone(self):
        self.assertEqual(
            normalize_slash_command(["C:/Program Files/Git/bogus", "walk"]),
            ["C:/Program Files/Git/bogus", "walk"],
        )
        self.assertEqual(normalize_slash_command(["docs/init", "walk"]), ["docs/init", "walk"])

    def test_only_the_first_argument_is_rewritten(self):
        self.assertEqual(
            normalize_slash_command(["init", "C:/Program Files/Git/init"]),
            ["init", "C:/Program Files/Git/init"],
        )


if __name__ == "__main__":
    unittest.main()
