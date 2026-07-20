"""IMP-219 (H11, F-TRACE-4): the traceability matrix and the mermaid graph must
annotate a suspicious edge in lockstep.

The symmetric code already lives in `traceability.py` (matrix at ~159-160, mermaid
at ~221-223), but H10 Phase 3 flagged the assert as *vacuous*: no fixture ever fed
a `suspicious: true` edge through both renders, so a regression that dropped the
annotation on one side would pass silently. This drives a minimal graph with one
suspicious edge and one ordinary edge and asserts:

  - both renders carry the `SUSPICIOUS: <reason>` warning for the suspicious edge, and
  - neither render annotates the ordinary edge (no blanket labelling).
"""

import contextlib
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.core.graph import save_graph
from sentinel.traceability import (
    graph_path,
    write_mermaid_graph,
    write_traceability_matrix,
)

# Deliberately free of the substring "SUSPICIOUS" so the project-id echo in the
# matrix title cannot inflate the annotation count below.
PID = "TRACE_FTRACE4"
SUSPICION_REASON = "citation not found in source"

GRAPH = {
    "nodes": [
        {"id": "REQ-001", "type": "requirement", "domain": "product", "status": "active", "path": "01_discovery/gaps.md"},
        {"id": "US-001", "type": "user_story", "domain": "product", "status": "ready", "path": "04_backlog/US-001.md"},
        {"id": "SPEC-U-001", "type": "spec_unit", "domain": "product", "status": "active", "path": "03_specs/specs.md"},
    ],
    "edges": [
        {"from": "REQ-001", "to": "SPEC-U-001", "relation": "refines"},
        {
            "from": "REQ-001",
            "to": "US-001",
            "relation": "traces_to",
            "suspicious": True,
            "suspicion_reason": SUSPICION_REASON,
        },
    ],
}


class TraceSuspiciousSymmetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_cwd = Path.cwd()
        self._tmp = Path(tempfile.mkdtemp())
        os.chdir(self._tmp)
        from sentinel.cli import main

        with contextlib.redirect_stdout(io.StringIO()):
            if main(["init", PID]) != 0:
                raise AssertionError("init failed")
        graph_path(PID).parent.mkdir(parents=True, exist_ok=True)
        save_graph(PID, GRAPH)

    def tearDown(self) -> None:
        os.chdir(self._old_cwd)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_matrix_and_mermaid_annotate_suspicious_edge_in_lockstep(self) -> None:
        matrix = write_traceability_matrix(PID).read_text(encoding="utf-8")
        mermaid = write_mermaid_graph(PID).read_text(encoding="utf-8")

        warning = f"SUSPICIOUS: {SUSPICION_REASON}"
        self.assertIn(warning, matrix, "matrix dropped the suspicious annotation")
        self.assertIn(warning, mermaid, "mermaid dropped the suspicious annotation")

        # Exactly one edge is suspicious in each render — the ordinary `refines`
        # edge must stay unannotated (guards against blanket labelling that would
        # make the symmetry assert pass for the wrong reason). Count the `(SUSPICIOUS:`
        # annotation token, which only edge rows carry.
        self.assertEqual(matrix.count("(SUSPICIOUS:"), 1, "matrix over-annotated")
        self.assertEqual(mermaid.count("(SUSPICIOUS:"), 1, "mermaid over-annotated")


if __name__ == "__main__":
    unittest.main()
