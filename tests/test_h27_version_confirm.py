"""H27 inc 6a task 4: confirming a new version re-crosses what changed; /next --change shows the unconfirmed one."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SyncCase, run_ok  # noqa: E402

from sentinel.changes import list_changes  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.state import cross_status  # noqa: E402
from sentinel.readiness_verdict import build_change_verdict  # noqa: E402
from sentinel.status import change_status  # noqa: E402
from sentinel.workspace import update_state, workspace_path  # noqa: E402

PID = "TVCF"
CID = "CHG-001"


class VersionCase(SyncCase):
    PID = PID

    def load_candidate(self) -> str:
        """Overwrite pedido.md with v2 and load it from the same path: a candidate version."""
        self.write_v2()
        out = run_ok(["sources", PID, "--load", "pedido.md", "--role", "pedido", "--change", CID])
        forget_read_snapshots()
        return json.loads(out)["source_id"]

    def confirm(self, flag: str = "--superseded-by") -> tuple[str, str, dict]:
        old = self.ids()["pedido"]
        new = self.load_candidate()
        if flag == "--superseded-by":
            argv = ["sources", PID, "--id", old, "--superseded-by", new, "--reason", "v2"]
        else:
            argv = ["sources", PID, "--id", new, "--current", "--reason", "v2"]
        result = json.loads(run_ok(argv))
        forget_read_snapshots()
        return old, new, result


class VersionConfirmTests(VersionCase):
    def test_next_names_unconfirmed_version_once(self):
        old = self.ids()["pedido"]
        new = self.load_candidate()
        step = self.step()
        self.assertEqual(step["versions"], [
            {"id": new, "version_of": old, "command": f"/sources {PID} --id {old} --superseded-by {new}"}])
        self.assertEqual(step["text"].count("versión nueva sin confirmar"), 1)
        changes = {key: dict(value) for key, value in list_changes(PID).items()}
        changes[CID]["language"] = "en"
        update_state(PID, changes=changes)
        self.assertEqual(self.step()["text"].count("unconfirmed new version"), 1)

    def test_verdict_and_status_warn(self):
        new = self.load_candidate()
        gaps_before = self.open_gaps()
        verdict = build_change_verdict(PID, CID)
        found = [w for w in verdict["warnings"] if new in str(w) and "--superseded-by" in str(w)]
        self.assertEqual(len(found), 1)
        self.assertFalse([b for b in verdict["blockers"] if new in str(b)])
        forget_read_snapshots()
        shown = json.dumps(change_status(PID, CID), ensure_ascii=False)
        self.assertIn(new, shown)
        self.assertIn("--superseded-by", shown)
        self.assertEqual(self.open_gaps(), gaps_before)

    def test_confirm_runs_touched_set(self):
        _, _, result = self.confirm()
        self.assertEqual(result["sync"][0]["change_id"], CID)
        self.assertTrue(Path(result["sync"][0]["report_path"]).is_file())
        self.assertTrue((workspace_path(PID) / "01_discovery" / CID / "sync_report.md").is_file())
        forget_read_snapshots()
        kinds = cross_status(PID, CID)["kinds"]
        self.assertEqual(kinds["diseno"]["delta"]["touched"], [5])

    def test_no_version_note_after_confirm(self):
        self.confirm()
        step = self.step()
        self.assertNotIn("versions", step)
        self.assertNotIn("sin confirmar", step["text"])
        self.assertTrue(step["command"].endswith("--delta"), step["command"])

    def test_current_runs_touched_set_as_new(self):
        _, _, result = self.confirm("--current")
        self.assertEqual(result["sync"][0]["change_id"], CID)
        text = Path(result["sync"][0]["report_path"]).read_text(encoding="utf-8")
        self.assertIn("RN-02", text.split("## Elementos nuevos, cambiados o quitados")[1])
        forget_read_snapshots()
        kinds = cross_status(PID, CID)["kinds"]
        self.assertTrue(kinds["diseno"]["delta"])
        self.assertTrue(kinds["contradicciones"]["delta"])


class ProjectConfirmTests(unittest.TestCase):
    def test_project_source_confirm_unchanged(self):
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                shutil.copy(Path(__file__).resolve().parent / "fixtures" / "change_crosses" / "pedido_contradiccion.md", "a.md")
                Path("b.md").write_text(Path("a.md").read_text(encoding="utf-8").replace("5.000.000", "3.000.000"), encoding="utf-8")
                run_ok(["init", "TVCP"])
                run_ok(["ingest", "TVCP", "--source", "a.md"])
                run_ok(["sync", "TVCP", "--source", "b.md"])
                ids = [r["id"] for r in json.loads(run_ok(["sources", "TVCP"]))["registry"]]
                self.assertEqual(len(ids), 2)
                result = json.loads(run_ok(["sources", "TVCP", "--id", ids[0], "--superseded-by", ids[1], "--reason", "v2"]))
                self.assertNotIn("sync", result)
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
