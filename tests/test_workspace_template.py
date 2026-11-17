"""IMP-175 (E1): the versioned `workspaces/_template` scaffold is a single source
of truth with `WORKSPACE_DIRS` (what `/init` actually builds). Before this, three
definitions of the same tree drifted: `_template` had lost
`08_context_packs/requests`+`exports`, and `/doctor` checked a third partial subset.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from sentinel.doctor import workspace_template_check
from sentinel.workspace import WORKSPACE_DIRS, WORKSPACE_GITIGNORE, ensure_release_paths_ignored, ensure_workspace

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "workspaces" / "_template"


class WorkspaceGitignore(unittest.TestCase):
    def test_init_writes_a_user_controlled_workspace_gitignore(self) -> None:
        # IMP-212: every workspace carries its own .gitignore so a user versioning
        # their project keeps reconstructible paths out of git while the matured
        # artifacts stay tracked. The public framework repo ignores workspaces/*
        # wholesale instead, so this file never contradicts that maintainer default.
        with tempfile.TemporaryDirectory() as tmp:
            base = ensure_workspace("GITIGN", root=Path(tmp))
            gitignore = base / ".gitignore"
            self.assertTrue(gitignore.exists())
            text = gitignore.read_text(encoding="utf-8")
            self.assertEqual(text, WORKSPACE_GITIGNORE)
            for path in ("memory.lancedb/", "08_context_packs/views/*.html", "08_context_packs/synthetic/"):
                self.assertIn(path, text)

    def test_release_mirrors_and_release_views_are_ignored(self) -> None:
        # IMP-361: `.series_work/` is a full workspace copy (raw sources included) and release
        # views land in 08_context_packs/<rN>/views/; neither was ignored.
        lines = WORKSPACE_GITIGNORE.splitlines()
        self.assertIn(".series_work/", lines)
        self.assertIn("08_context_packs/r*/views/*.html", lines)

    def test_git_applies_the_rules_to_the_paths_sentinel_writes(self) -> None:
        git = shutil.which("git")
        if not git:
            self.skipTest("git not installed")
        with tempfile.TemporaryDirectory() as tmp:
            base = ensure_workspace("GITIGN", root=Path(tmp))
            subprocess.run([git, "init", "-q", str(base)], check=True)

            def ignored(relative: str) -> bool:
                return subprocess.run(
                    [git, "-C", str(base), "check-ignore", "-q", "--no-index", relative], check=False
                ).returncode == 0

            for relative in (".series_work/r1/workspaces/GITIGN/00_raw/req.md", "08_context_packs/r1/views/prd.html",
                             "08_context_packs/r1.2/views/backlog.html", "08_context_packs/views/prd.html"):
                self.assertTrue(ignored(relative), relative)
            for relative in ("08_context_packs/r1/release_guide.md", "03_specs/r1/prd.md", "00_raw/req.md"):
                self.assertFalse(ignored(relative), relative)

    def test_an_existing_workspace_gitignore_gets_the_release_rules_once(self) -> None:
        old = (
            "memory.lancedb/\r\n08_context_packs/views/*.html\r\n08_context_packs/synthetic/\r\n"
            "# IMP-241: workspace-local themes (brand palettes, fonts) never enter git.\r\n.sentinel/\r\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "workspaces" / "OLDIGN"
            base.mkdir(parents=True)
            (base / ".gitignore").write_bytes(old.encode("ascii"))
            ensure_workspace("OLDIGN", root=Path(tmp))
            raw = (base / ".gitignore").read_bytes()
            self.assertTrue(raw.startswith(old.encode("ascii")))  # append-only
            self.assertTrue(raw.endswith(b".series_work/\r\n08_context_packs/r*/views/*.html\r\n"))
            self.assertFalse(ensure_release_paths_ignored(base / ".gitignore"))  # idempotent
            self.assertEqual((base / ".gitignore").read_bytes(), raw)

    def test_a_user_spelling_of_the_rule_is_respected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".gitignore"
            path.write_bytes(b"/.series_work\n")
            self.assertTrue(ensure_release_paths_ignored(path))
            self.assertEqual(path.read_bytes().count(b"series_work"), 1)
            self.assertIn(b"08_context_packs/r*/views/*.html\n", path.read_bytes())


class TemplateMatchesWorkspaceDirs(unittest.TestCase):
    def test_template_tree_equals_workspace_dirs_exactly(self):
        present = {
            str(path.relative_to(TEMPLATE)).replace("\\", "/")
            for path in TEMPLATE.rglob("*")
            if path.is_dir()
        }
        self.assertEqual(present, set(WORKSPACE_DIRS))

    def test_every_template_dir_is_git_tracked(self):
        for relative in WORKSPACE_DIRS:
            self.assertTrue(
                (TEMPLATE / relative / ".gitkeep").exists(),
                f"{relative} has no .gitkeep so git would not track the empty dir",
            )


class WorkspaceTemplateDoctorCheck(unittest.TestCase):
    def test_repo_template_passes(self):
        self.assertEqual(workspace_template_check(REPO)["status"], "PASS")

    def test_missing_dir_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "workspaces" / "_template"
            for relative in WORKSPACE_DIRS[:-1]:  # omit the last dir on purpose
                (base / relative).mkdir(parents=True, exist_ok=True)
            check = workspace_template_check(root)
            self.assertEqual(check["status"], "FAIL")
            self.assertIn(WORKSPACE_DIRS[-1], check["detail"])

    def test_absent_template_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            check = workspace_template_check(Path(tmp))
            self.assertEqual(check["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
