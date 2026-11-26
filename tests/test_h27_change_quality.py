"""IMP-431: `/quality --change` audits only the stories of a change, with a verdict of its own."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import (  # noqa: E402
    SnapshotWorkspaceCase, build_matured_workspace, complete_extraction, export_final_brief, gap_acceptance_answer, run_ok,
)
from sentinel.changes import get_change  # noqa: E402
from sentinel.compilers.change_backlog import _change_story_ids, change_backlog_digest, read_change_units  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.errors import GateRefusal  # noqa: E402
from sentinel.quality import generate_quality  # noqa: E402
from sentinel.validation import validate_project  # noqa: E402
from sentinel.workspace import read_json, update_state, workspace_path  # noqa: E402
import test_change_next as tcn  # noqa: E402
from test_change_next import load_baseline  # noqa: E402
from test_change_affected_stories import ANSWERS as REMOVED_ANSWERS  # noqa: E402
from test_change_specs import PROJECT_EARS, PROJECT_RAW, answer, open_change  # noqa: E402
from test_h27_change_release import CID, PID, ReleaseFlowCase, cli  # noqa: E402
from test_h27_series_scope import ROOT, normalized_sha256  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "change_inc8"
BASELINE = FIXTURES / "quality_project_sha256.json"


def build_mix_without_stories() -> str:
    """The project (with its backlog) plus a change that has a baseline and no stories yet; returns the change id."""
    build_matured_workspace("MIX", PROJECT_RAW, gap_acceptance_answer(PROJECT_EARS))
    cid = open_change("MIX")
    load_baseline("MIX", cid)
    return cid


def project_quality_hashes(work: Path) -> dict[str, str]:
    """Normalized sha256 of every file under 05_quality/ (independent of the machine and the checkout path)."""
    base = workspace_path("MIX")
    tokens = []
    for root, token in ((ROOT.parent, "<REPO>"), (work, "<WORK>"), (base, "<WORK>")):
        for value in {str(root), root.as_posix(), str(root.resolve()), root.resolve().as_posix()}:
            tokens.append((value, token))
    tokens.sort(key=lambda item: -len(item[0]))
    found = {}
    for path in sorted((base / "05_quality").rglob("*")):
        if path.is_file():
            found[path.relative_to(base).as_posix()] = normalized_sha256(path.read_bytes(), tokens)
    return found


def project_stories(base: Path, cid: str = "CHG-001") -> list[str]:
    ids = {path.stem for path in (base / "04_backlog").glob("US-*.md")}
    return sorted(ids - set(_change_story_ids(base, cid)))


class ProjectQualityBytes(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        cls.cid = build_mix_without_stories()

    def test_project_quality_bytes_unchanged(self):
        """RF 2: the baseline was taken with the code before IMP-431."""
        run_ok(["quality", "MIX"])
        self.assertEqual(project_quality_hashes(self.temp), json.loads(BASELINE.read_text(encoding="utf-8")))


class ChangeQualityWithProject(SnapshotWorkspaceCase):
    """A project with its backlog and a change with its own backlog."""

    @classmethod
    def build_workspace(cls):
        cls.cid = build_mix_without_stories()
        answer("MIX", cls.cid, "a.md", REMOVED_ANSWERS)
        complete_extraction("MIX", cls.cid)
        run_ok(["brief", "MIX", "--change", cls.cid])
        export_final_brief("MIX", cls.cid)
        run_ok(["specs", "MIX", "--change", cls.cid])
        run_ok(["backlog", "MIX", "--change", cls.cid])

    def setUp(self):
        super().setUp()
        forget_read_snapshots()

    def state(self) -> dict:
        return read_json(workspace_path("MIX") / "state.json", {})

    def test_change_audit_only_change_stories(self):
        base = workspace_path("MIX")
        own = set(_change_story_ids(base, self.cid))
        self.assertTrue(own)
        result = generate_quality("MIX", change_id=self.cid)
        self.assertEqual(set(result["story_quality"]), own)
        self.assertEqual(result["change_id"], self.cid)
        self.assertTrue(project_stories(base, self.cid))
        self.assertTrue((base / "05_quality" / self.cid / "TC-001.md").is_file())
        self.assertTrue((base / "05_quality" / self.cid / "backlog_readiness_audit.md").is_file())
        self.assertEqual(len(list((base / "05_quality" / self.cid).glob("TC-*.md"))), len(own))

    def test_project_audit_skips_change_stories(self):
        base = workspace_path("MIX")
        generate_quality("MIX", change_id=self.cid)
        forget_read_snapshots()
        before = {p.name: p.read_bytes() for p in (base / "05_quality" / self.cid).iterdir()}
        result = generate_quality("MIX")
        own = set(_change_story_ids(base, self.cid))
        self.assertFalse(own & set(result["story_quality"]))
        self.assertEqual(set(result["story_quality"]), set(project_stories(base, self.cid)))
        self.assertFalse(own & set(self.state()["story_quality"]))
        self.assertEqual({p.name: p.read_bytes() for p in (base / "05_quality" / self.cid).iterdir()}, before)

    def test_change_quality_leaves_project_state(self):
        generate_quality("MIX")
        forget_read_snapshots()
        before = self.state()
        mine = project_stories(workspace_path("MIX"), self.cid)[0]
        generate_quality("MIX", change_id=self.cid)
        after = self.state()
        self.assertEqual(after["phase"], before["phase"])
        self.assertEqual(after.get("health"), before.get("health"))
        self.assertEqual(after["story_quality"][mine], before["story_quality"][mine])
        record = after["changes"][self.cid]["quality"]
        self.assertEqual(record["backlog_digest"], change_backlog_digest("MIX", self.cid))
        self.assertIn(record["verdict"], {"PASS", "PARTIAL", "ATTENTION"})
        own = _change_story_ids(workspace_path("MIX"), self.cid)
        self.assertEqual(record["stories"], own)
        self.assertEqual(sum(record["counts"].values()), len(own))
        self.assertEqual(set(record["counts"]), {"PASS", "PARTIAL", "FAIL"})
        self.assertEqual(record["audit"], f"05_quality/{self.cid}/backlog_readiness_audit.md")
        self.assertEqual(len(record["test_cases"]), len(own))
        self.assertTrue(record["audited_at"])

    def test_digest_follows_the_story_files(self):
        base = workspace_path("MIX")
        digest = change_backlog_digest("MIX", self.cid)
        self.assertEqual(digest, change_backlog_digest("MIX", self.cid))
        path = base / "04_backlog" / f"{_change_story_ids(base, self.cid)[0]}.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nnota\n", encoding="utf-8")
        self.assertNotEqual(change_backlog_digest("MIX", self.cid), digest)

    def test_change_audit_does_not_hide_project_finding(self):
        finding = "Backlog exists without backlog_readiness_audit."
        self.assertIn(finding, validate_project("MIX")["findings"])
        generate_quality("MIX", change_id=self.cid)
        forget_read_snapshots()
        self.assertIn(finding, validate_project("MIX")["findings"])
        generate_quality("MIX")
        forget_read_snapshots()
        self.assertNotIn(finding, validate_project("MIX")["findings"])


class ChangeQualityOnly(SnapshotWorkspaceCase):
    """A workspace that only holds a change, walked up to its backlog."""

    @classmethod
    def build_workspace(cls):
        tcn.ChangeNextSequence.build_workspace()
        tcn.ChangeNextSequence.test_each_row_of_the_table_in_order(unittest.TestCase())

    def setUp(self):
        super().setUp()
        forget_read_snapshots()

    def changes(self) -> dict:
        return read_json(workspace_path("BORR") / "state.json", {})["changes"]

    def audit_files(self) -> dict:
        folder = workspace_path("BORR") / "05_quality" / "CHG-001"
        return {path.name: path.read_bytes() for path in folder.glob("*.md")} if folder.exists() else {}

    def test_change_quality_language(self):
        generate_quality("BORR", change_id="CHG-001")
        folder = workspace_path("BORR") / "05_quality" / "CHG-001"
        case = (folder / "TC-001.md").read_text(encoding="utf-8")
        audit = (folder / "backlog_readiness_audit.md").read_text(encoding="utf-8")
        self.assertTrue(case.startswith("# Casos de prueba - US-"), case[:80])
        self.assertTrue(audit.startswith("# Auditoría de preparación del backlog - BORR / CHG-001"), audit[:80])
        for text in (case, audit):
            self.assertNotIn("## Coverage Matrix", text)
        self.assertIn("## Matriz de cobertura", case)
        self.assertIn("| Paso de prueba | Criterio de aceptación |", case)
        self.assertIn("## Notas de automatización", case)
        self.assertIn("- Historia de origen:", case)
        self.assertIn("- Proyecto:", case)

    def test_change_quality_in_english(self):
        changes = self.changes()
        changes["CHG-001"]["language"] = "en"
        update_state("BORR", changes=changes)
        forget_read_snapshots()
        generate_quality("BORR", change_id="CHG-001")
        folder = workspace_path("BORR") / "05_quality" / "CHG-001"
        self.assertTrue((folder / "TC-001.md").read_text(encoding="utf-8").startswith("# Test Case Set - US-"))
        audit = (folder / "backlog_readiness_audit.md").read_text(encoding="utf-8")
        self.assertTrue(audit.startswith("# Backlog Readiness Audit - BORR / CHG-001"))

    def test_change_quality_refusals(self):
        before = self.audit_files()
        changes = self.changes()
        changes["CHG-001"].pop("backlog")
        update_state("BORR", changes=changes)
        forget_read_snapshots()
        with self.assertRaises(GateRefusal) as caught:
            generate_quality("BORR", change_id="CHG-001")
        self.assertEqual(caught.exception.next_step, "/backlog BORR --change CHG-001")
        self.assertIn("El backlog de CHG-001 falta o está atrasado", str(caught.exception))
        self.assertEqual(self.audit_files(), before)  # nothing was written
        with self.assertRaises(GateRefusal) as unknown:
            generate_quality("BORR", change_id="CHG-999")
        with self.assertRaises(GateRefusal) as expected:
            get_change("BORR", "CHG-999")
        self.assertEqual(str(unknown.exception), str(expected.exception))

    def test_change_quality_refuses_a_backlog_that_is_behind(self):
        (workspace_path("BORR") / "04_backlog" / "CHG-001" / "SLICE-PLAN.md").unlink()
        with self.assertRaises(GateRefusal) as caught:
            generate_quality("BORR", change_id="CHG-001")
        self.assertEqual(caught.exception.next_step, "/backlog BORR --change CHG-001")

    def test_change_without_stories_refuses(self):
        base = workspace_path("BORR")
        for sid in _change_story_ids(base, "CHG-001"):
            (base / "04_backlog" / f"{sid}.md").unlink()
        changes = self.changes()  # every unit dropped on purpose: the backlog is current and has no story
        changes["CHG-001"]["backlog"]["dropped_units"] = [unit["id"] for unit in read_change_units("BORR", "CHG-001")]
        update_state("BORR", changes=changes)
        forget_read_snapshots()
        with self.assertRaises(GateRefusal) as caught:
            generate_quality("BORR", change_id="CHG-001")
        self.assertEqual(str(caught.exception), "CHG-001 no tiene historias para auditar")
        self.assertEqual(caught.exception.next_step, "/backlog BORR --change CHG-001")

    def test_cli_quality_change_on_dirty_change_only_workspace(self):
        """The project of a change-only workspace is DIRTY: `--change` answers to its own gate."""
        found = json.loads(run_ok(["quality", "BORR", "--change", "CHG-001"]))
        self.assertEqual(found["change_id"], "CHG-001")

    def test_project_quality_refused_on_change_only(self):
        code, out = cli(["quality", "BORR"])
        self.assertNotEqual(code, 0, out)
        self.assertIn("/quality BORR --change CHG-001", out)

    def test_quality_change_with_release_refused(self):
        before = self.audit_files()
        code, out = cli(["quality", "BORR", "--change", "CHG-001", "--release", "r1"])
        self.assertNotEqual(code, 0, out)
        self.assertIn("para el resto corré /quality BORR --change CHG-001", out)
        self.assertEqual(self.audit_files(), before)  # nothing was written


class SeriesQuality(ReleaseFlowCase):
    """BINDING ruling: a change with a confirmed series has `backlog_releases`, not `backlog`; its stories are audited."""

    def quality(self) -> dict:
        forget_read_snapshots()
        return json.loads(run_ok(["quality", PID, "--change", CID]))

    def test_series_change_is_audited(self):
        self.derive("r1", "r2")
        self.assertFalse(get_change(PID, CID).get("backlog"))
        found = self.quality()
        self.assertEqual(found["change_id"], CID)
        base = self.base()
        own = _change_story_ids(base, CID)
        self.assertEqual(sorted(self.stories("r1") + self.stories("r2")), sorted(own))
        record = get_change(PID, CID)["quality"]
        self.assertEqual(sorted(record["stories"]), sorted(own))
        self.assertEqual(record["backlog_digest"], change_backlog_digest(PID, CID))

    def test_series_change_without_derivation_refuses(self):
        code, out = cli(["quality", PID, "--change", CID])
        self.assertNotEqual(code, 0, out)
        self.assertIn(f"/backlog {PID} --change {CID}", out)

    def test_quality_step_after_the_last_release_closes(self):
        evidence = Path("evidencia.md")
        evidence.write_text("Evidencia sintetica.\n", encoding="utf-8")
        for rid in ("r1", "r2"):
            self.derive(rid)
            self.finish(rid)
            self.assertEqual(self.close(rid, evidence)[0], 0)
            if rid == "r1":
                self.assertNotEqual(self.step()["key"], "quality")  # the walk stays intact
        step = self.step()
        self.assertEqual((step["key"], step["command"]), ("quality", f"/quality {PID} --change {CID}"))
        self.quality()
        self.assertEqual(self.step()["key"], "done")
        path = self.base() / "04_backlog" / f"{self.stories('r1')[0]}.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nNota.\n", encoding="utf-8")
        self.assertEqual(self.step()["key"], "quality")

    def step(self) -> dict:
        forget_read_snapshots()
        with patch("sentinel.readiness_verdict._change_prep_key", return_value=""):
            return json.loads(run_ok(["next", PID, "--change", CID]))


if __name__ == "__main__":
    unittest.main()
