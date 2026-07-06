"""IMP-175 (E1): the versioned `workspaces/_template` scaffold is a single source
of truth with `WORKSPACE_DIRS` (what `/init` actually builds). Before this, three
definitions of the same tree drifted: `_template` had lost
`08_context_packs/requests`+`exports`, and `/doctor` checked a third partial subset.
"""

import tempfile
import unittest
from pathlib import Path

from sentinel.doctor import workspace_template_check
from sentinel.workspace import WORKSPACE_DIRS

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "workspaces" / "_template"


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
