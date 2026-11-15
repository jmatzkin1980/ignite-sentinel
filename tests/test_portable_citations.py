"""IMP-308: generated artifacts cite paths as `workspaces/<id>/...`, never absolute.

IMP-301 made the stored paths (graph, memory, state) workspace-relative; the
artifacts still quoted the absolute folder in backlog anchors, the traceability
matrix, the maturity and gap-resolution reports, the MDX export and the context
packs. A moved workspace then regenerated different bytes. Here the matured flow
runs once, every generated text file is scanned for the absolute folder, and the
workspace is moved and regenerated: every Markdown file must come out the same.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, gap_acceptance_answer, run_ok  # noqa: E402

PROJECT = "CITES"

RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads.

In scope: risk dashboard for open queues. Out of scope: editing cases.

Metric: reduce manual preparation by 30 percent in the first release month.
"""

EARS = (
    "When queue metrics are available, the system shall display open risk queues. "
    "When a case breaches SLA, the system shall flag the queue as high risk."
)

# The commands that regenerate the artifacts, after the gaps are answered.
REGENERATE = (["brief"], ["specs"], ["backlog"], ["quality"], ["trace"], ["maturity"],
              ["export", "--artifact", "prd", "--format", "mdx"])
# Binary index files, and the command log, which records each command's own output.
SKIPPED = ("memory.lancedb/lance/", ".sentinel/command_log.jsonl")
_TIMESTAMP_RE = re.compile(r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d+)?(?:[+-]\d\d:?\d\d|Z)?")


def text_files(base: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(base.rglob("*")):
        relative = path.relative_to(base).as_posix()
        if not path.is_file() or relative.startswith(SKIPPED):
            continue
        try:
            files[relative] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return files


def root_forms(folder: Path) -> set[str]:
    forms = {folder.as_posix(), str(folder), folder.resolve().as_posix(), str(folder.resolve())}
    return forms | {form.replace("\\", "\\\\") for form in forms}


class PortableCitationsTests(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        root = Path.cwd()
        (root / "raw.md").write_text(RAW, encoding="utf-8")
        (root / "answers.md").write_text(gap_acceptance_answer(EARS), encoding="utf-8")
        run_ok(["init", PROJECT, "--brief-version", "1"])
        run_ok(["ingest", PROJECT, "--source", str(root / "raw.md")])
        run_ok(["resolve-gaps", PROJECT, "--source", str(root / "answers.md")])
        for argv in REGENERATE:
            run_ok([argv[0], PROJECT, *argv[1:]])

    def workspace(self) -> Path:
        return Path.cwd() / "workspaces" / PROJECT

    def test_no_generated_file_cites_the_absolute_folder(self) -> None:
        forms = root_forms(self.temp)
        leaks = {
            name: next(line for line in text.splitlines() if any(form in line for form in forms))[:200]
            for name, text in text_files(self.workspace()).items()
            if any(form in text for form in forms)
        }
        self.assertEqual(leaks, {})

    def test_a_moved_workspace_regenerates_the_same_markdown(self) -> None:
        def regenerate() -> dict[str, str]:
            for argv in REGENERATE:
                run_ok([argv[0], PROJECT, *argv[1:]])
            return {name: _TIMESTAMP_RE.sub("[TIMESTAMP]", text)
                    for name, text in text_files(self.workspace()).items() if name.endswith(".md")}

        # Each /specs rerun adds a numbered delta report, so both runs start from the
        # same copy: one regenerates in place, the other in a different folder.
        moved = self.temp.parent / "moved" / "clone"
        try:
            shutil.copytree(self.temp / "workspaces", moved / "workspaces")
            before = regenerate()
            os.chdir(moved)
            after = regenerate()
        finally:
            os.chdir(self.temp)
            shutil.rmtree(moved.parent, ignore_errors=True)
        self.assertGreater(len(before), 20)
        self.assertEqual(sorted(after), sorted(before))
        changed = [name for name in before if before[name] != after[name]]
        self.assertEqual(changed, [])


class WorkspaceCitationTests(unittest.TestCase):
    def test_inside_paths_become_repo_relative_and_outside_paths_stay(self) -> None:
        from sentinel.core.paths import workspace_citation

        root = Path("C:/repo")
        self.assertEqual(workspace_citation("P", "C:/repo/workspaces/P/03_specs/prd.md", root), "workspaces/P/03_specs/prd.md")
        self.assertEqual(workspace_citation("P", "/old/clone/workspaces/P/a.md", root), "workspaces/P/a.md")
        self.assertEqual(workspace_citation("P", "03_specs/prd.md", root), "workspaces/P/03_specs/prd.md")
        self.assertEqual(workspace_citation("P", "workspaces/P/a.md", root), "workspaces/P/a.md")
        self.assertEqual(workspace_citation("P", "C:/elsewhere/notes.md", root), "C:/elsewhere/notes.md")
        self.assertEqual(workspace_citation("P", "", root), "")


if __name__ == "__main__":
    unittest.main()
