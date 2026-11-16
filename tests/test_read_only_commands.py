"""IMP-306: a read-only command writes no artifact.

The registry (`sentinel/commands.py`) says which commands are read-only. Here each
one runs on a matured workspace, and every file it writes, even with the same
bytes, must be one of these:
- the protocol's bookkeeping (state, command log);
- a derived cache rebuilt from the artifacts (the memory index);
- a report the command declares in `DERIVED_OUTPUTS`, never a governed artifact.

A command that writes anything else belongs in `MUTATING`, where the protocol
snapshots the governed artifacts after it. `/health` stays read-only on purpose:
it compares the governed artifacts against that snapshot, so snapshotting after
it would hide a hand edit.
"""
from __future__ import annotations

import fnmatch
import hashlib
import sys
import unittest
from pathlib import Path

from sentinel.commands import BY_NAME, MUTATING, READ_ONLY_COMMANDS
from sentinel.protocols import GOVERNED_ARTIFACT_GLOBS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, build_matured_workspace, gap_acceptance_answer, run_cli  # noqa: E402

PROJECT = "READONLY"

RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads.

In scope: risk dashboard for open queues. Out of scope: editing cases.

Metric: reduce manual preparation by 30 percent in the first release month.
"""

EARS = "When queue metrics are available, the system shall display open risk queues."

# Every command inside the protocol writes these.
BOOKKEEPING = (
    "state.json",
    ".sentinel/state.json.bak",  # IMP-331: the copy of state.json kept before each state write
    ".sentinel/lock",
    ".sentinel/command_log.jsonl",
    "06_traceability/command_protocol_log.md",
)
# Caches rebuilt from the artifacts; any command that reads memory may refresh them.
DERIVED_CACHES = (
    "memory.lancedb/*",
    ".sentinel/derived/*",
)
# Reports a read-only command writes, each with its reason.
DERIVED_OUTPUTS: dict[str, tuple[str, ...]] = {
    # The audit result; /health must not snapshot the artifacts it audits.
    "health": ("06_traceability/health_report.json", "06_traceability/health_report.md"),
    # A derived HTML snapshot of one artifact.
    "view": ("08_context_packs/views/*",),
    # IMP-313: --write-pack saves the retrieved context as a pack, derived from memory.
    "retrieve": ("08_context_packs/*.json",),
}

ARGV: dict[str, list[str]] = {
    "view": ["--artifact", "brief"],
    "retrieve": ["--query", "risk queues", "--workflow", "discovery", "--write-pack"],
}


def file_stamps(base: Path) -> dict[str, tuple[int, str]]:
    return {
        path.relative_to(base).as_posix(): (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(base.rglob("*"))
        if path.is_file()
    }


def written_files(before: dict[str, tuple[int, str]], after: dict[str, tuple[int, str]]) -> set[str]:
    return {key for key in set(before) | set(after) if before.get(key) != after.get(key)}


def matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


class ReadOnlyCommandsWriteNoArtifact(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        build_matured_workspace(PROJECT, RAW, gap_acceptance_answer(EARS))

    def run_and_collect(self, command: str) -> set[str]:
        """Run the command (its exit code is not the point) and return the files it wrote."""
        base = self.temp / "workspaces" / PROJECT
        before = file_stamps(base)
        run_cli([command, PROJECT, *ARGV.get(command, [])])
        return written_files(before, file_stamps(base))

    def test_every_read_only_command_writes_no_artifact(self) -> None:
        self.assertTrue(READ_ONLY_COMMANDS)
        for command in sorted(READ_ONLY_COMMANDS):
            with self.subTest(command=command):
                written = self.run_and_collect(command)
                allowed = BOOKKEEPING + DERIVED_CACHES + DERIVED_OUTPUTS.get(command, ())
                self.assertEqual({p for p in written if not matches(p, allowed)}, set(),
                                 f"/{command} writes artifacts; register it as MUTATING")
                self.assertEqual({p for p in written if matches(p, GOVERNED_ARTIFACT_GLOBS)}, set())

    def test_retrieve_write_pack_writes_its_pack(self) -> None:
        written = self.run_and_collect("retrieve")
        self.assertTrue(any(matches(p, DERIVED_OUTPUTS["retrieve"]) for p in written), written)

    def test_declared_outputs_belong_to_read_only_commands(self) -> None:
        self.assertLessEqual(set(DERIVED_OUTPUTS), READ_ONLY_COMMANDS)

    def test_trace_and_maturity_write_artifacts_and_are_mutating(self) -> None:
        expected = {
            "trace": "06_traceability/traceability_matrix.md",
            "maturity": "01_discovery/requirement_maturity_report.md",
        }
        for command, artifact in expected.items():
            with self.subTest(command=command):
                self.assertEqual(BY_NAME[command].protocol, MUTATING)
                self.assertIn(artifact, self.run_and_collect(command))


if __name__ == "__main__":
    unittest.main()
