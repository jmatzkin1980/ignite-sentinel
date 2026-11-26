"""H27 inc 8b walk: a change after its backlog is refined, composed and given feedback over its own stories, from the CLI."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import (  # noqa: E402
    SnapshotWorkspaceCase, class_deferred, complete_extraction, export_final_brief, run_ok, waive_coherence, waive_crosses,
)
from sentinel.commands import skill_for_command  # noqa: E402
from sentinel.compilers.change_backlog import _change_story_ids, read_change_units  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402
from test_change_flow import SCOPE_ANSWER  # noqa: E402
from test_change_next import FIXTURES, cli_json, load_baseline  # noqa: E402
from test_change_specs import ALL_ANSWERS, answer  # noqa: E402
from test_h27_change_release import cli  # noqa: E402

PID = "BORR"
CID = "CHG-001"
ROOT = Path(__file__).resolve().parents[1]
QUOTE = "Guardar borrador"


def next_key() -> str:
    return cli_json(["next", PID, "--change", CID])["key"]


def validation() -> dict:
    """`/validate --change`: each check's status and the findings (a crash or a usage error fails the walk)."""
    code, out = cli(["validate", PID, "--change", CID])
    if code not in (0, 5):
        raise AssertionError(out)
    result = json.loads(out)
    return {"checks": {c["id"]: c["status"] for c in result["checks"]}, "findings": list(result["findings"])}


def write(name: str, payload: dict) -> str:
    Path(name).write_text(json.dumps(payload), encoding="utf-8")
    return name


class Inc8bWalk(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        waive_crosses(PID, CID)
        load_baseline(PID)
        answer(PID, CID, "a.md", ALL_ANSWERS)
        waive_coherence(PID, CID)
        complete_extraction(PID, CID)
        run_ok(["brief", PID, "--change", CID])
        class_deferred(PID, CID)
        export_final_brief(PID, CID)
        run_ok(["specs", PID, "--change", CID])

    def test_walk(self) -> None:
        base = workspace_path(PID)
        run_ok(["backlog", PID, "--change", CID])
        run_ok(["quality", PID, "--change", CID])
        self.assertEqual(next_key(), "done")
        before = validation()
        unit = read_change_units(PID, CID)[0]["id"]
        story = _change_story_ids(base, CID)[0]

        proposal = {"kind": "reslice", "target_stories": [story], "source_units": [unit], "recommendation": "Keep the draft story small.",
                    "rationale": "One observable result.", "citations": [QUOTE]}
        refined = json.loads(run_ok(["refine-backlog", PID, "--source", write("p.json", {"proposals": [proposal]}), "--change", CID]))
        self.assertEqual(refined["accepted"], ["BREF-001"])
        self.assertTrue((base / "04_backlog" / CID / "refinements" / "refinement_report.md").is_file())
        self.assertEqual(next_key(), "quality")
        run_ok(["quality", PID, "--change", CID])
        self.assertEqual(next_key(), "done")

        block = {"section": "1", "paragraphs": [{"text": "The change keeps a draft of the registration.", "citations": [QUOTE]}]}
        run_ok(["compose", PID, "--source", write("b.json", {"blocks": [block]}), "--change", CID])
        prd = base / "03_specs" / CID / "prd.md"
        self.assertIn("### Agent Composition", prd.read_text(encoding="utf-8"))
        forget_read_snapshots()
        export_final_brief(PID, CID)
        run_ok(["specs", PID, "--change", CID])
        self.assertIn("### Agent Composition", prd.read_text(encoding="utf-8"))

        found = {"type": "surface-not-covered", "story": story, "source_units": [unit], "summary": "The draft list loses the last entry.",
                 "evidence": "Implementation test run: the last draft is missing after saving."}
        fed = json.loads(run_ok(["implementation-feedback", PID, "--source", write("f.json", {"findings": [found]})]))
        self.assertEqual(len(fed["accepted"]), 1)
        report = (base / "07_changes" / "05_implementation_feedback" / "feedback_report.md").read_text(encoding="utf-8")
        self.assertIn("Change", report)

        # M7 (review inc 8b): refine and compose change no validation result; only the open feedback may add a finding
        after = validation()
        self.assertEqual(after["checks"], before["checks"])
        added = [f for f in after["findings"] if f not in before["findings"]]
        self.assertTrue(all("feedback" in f.lower() or "IFB-" in f for f in added), added)
        self.assertEqual([f for f in before["findings"] if f not in after["findings"]], [])

    def test_commands_and_guide_name_the_change_form(self) -> None:
        self.assertEqual(skill_for_command(f"/refine-backlog {PID} --source x --change {CID}"), "sentinel-backlog-refine §Change")
        self.assertEqual(skill_for_command(f"/compose {PID} --source x --change {CID}"), "sentinel-compose §Change")
        manifest = json.loads((ROOT / "sentinel" / "templates" / "commands_manifest.json").read_text(encoding="utf-8"))
        entries = {entry["name"]: entry for entry in manifest["commands"]}
        for name in ("refine-backlog", "compose"):
            self.assertIn("[--change CHG-NNN]", entries[name]["argument_hint"])
            self.assertIn(f"/{name} PROJECT_ID --source PATH --change CHG-NNN", entries[name]["body"])
        self.assertIn("change", entries["implementation-feedback"]["body"].lower())
        guide = ROOT / "user_guide"
        self.assertIn("`CHG-nnn/refinements/`", (guide / "02-artifact-reference.md").read_text(encoding="utf-8"))
        self.assertIn("`CHG-nnn/compositions/`", (guide / "02-artifact-reference.md").read_text(encoding="utf-8"))
        chat = (guide / "11-chat-commands.md").read_text(encoding="utf-8")
        self.assertIn("Refine this change's stories", chat)
        self.assertIn("Compose the PRD of this change", chat)
        self.assertRegex((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), r"(?s)\[Unreleased\].*?`/refine-backlog --change CHG-NNN`")


if __name__ == "__main__":
    unittest.main()
