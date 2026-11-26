"""H27 inc 7c walk: a change too big for one release is assessed, proposed and confirmed, and its series guide is viewed."""
from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SyncCase, run_ok  # noqa: E402

from sentinel.cli import main  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = "W7C"
CID = "CHG-001"
INC7 = SyncCase.FIXTURES / "change_inc7"


class Inc7cWalk(SyncCase):
    PID = PID

    def next_key(self) -> str:
        forget_read_snapshots()
        return json.loads(run_ok(["next", PID, "--change", CID]))["key"]

    def test_walk(self) -> None:
        before = self.next_key()
        assessment = json.loads(run_ok(["split", PID, "--assess", "--change", CID]))
        self.assertIn(assessment.get("recommendation"), ("split", "no_split", "cannot_decide"))
        self.assertEqual(json.loads(run_ok(["split", PID, "--propose", "--source", str(INC7 / "propuesta_serie_cambio.json"),
                                            "--change", CID]))["status"], "proposal")
        run_ok(["split", PID, "--confirm", "--ba", "Ana", "--tech", "Equipo", "--change", CID])
        run_ok(["view", PID, "--artifact", "release-guide", "--change", CID])
        base = workspace_path(PID)
        self.assertTrue((base / "08_context_packs" / "views" / f"{CID}-release-guide.html").is_file())
        self.assertTrue((base / "02_requirements" / CID / "series" / "release-guide.md").is_file())
        self.assertFalse((base / "02_requirements" / "series").exists())
        # the series of a change does not move where the change goes next
        self.assertEqual(self.next_key(), before)
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = main(["split", PID, "--close", "r1", "--evidence", "x.md", "--ba", "Ana", "--tech", "Equipo", "--change", CID])
        self.assertNotEqual(code, 0)
        self.assertIn("llegan con las sub-releases de un cambio", err.getvalue())


if __name__ == "__main__":
    unittest.main()
