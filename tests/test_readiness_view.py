"""IMP-247 — build-readiness view: what is missing, per item, and from whom.

`/view PROJECT_ID --artifact readiness` renders, inside the common shell (CSP,
themes), one card per item (workspace, each backlog story, each SLICE-PLAN wave)
with the governed verdict of IMP-248, and every open request grouped by
recipient with "copy request". The view is the only owner of the per-recipient
request. Rules:
- recipients come from the stakeholder registry by lens; no match is shown as
  unassigned, never an invented owner;
- a wave takes the most severe verdict of its stories; a wave without stories is
  never green;
- local marks live in localStorage (`ignite-sentinel:readiness:...`, try/catch),
  with export and import; an open request degrades a READY item in the page.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.readiness_verdict import build_readiness_verdict
from sentinel.readiness_view import (
    ReadinessModelError,
    collect_readiness_model,
    merge_verdicts,
    render_readiness_view,
    validate_readiness_model,
)
from sentinel.themes import load_theme

RAW = (
    "# Reporting Portal\n\n"
    "We need a reporting portal for the operations team. The objective is to "
    "reduce manual work. Data is stored in the legacy billing system.\n"
)


class MergeTests(unittest.TestCase):
    def test_merge_takes_the_most_severe(self) -> None:
        self.assertEqual(merge_verdicts(["READY", "NOT_READY", "READY_WITH_WARNINGS"]), "NOT_READY")
        self.assertEqual(merge_verdicts(["READY", "READY_WITH_WARNINGS"]), "READY_WITH_WARNINGS")
        self.assertEqual(merge_verdicts(["READY"]), "READY")

    def test_nothing_to_merge_is_never_green(self) -> None:
        self.assertEqual(merge_verdicts([]), "READY_WITH_WARNINGS")


class ReadinessModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        src = self.temp / "raw.md"
        src.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "RDV"]), 0)
        self.assertEqual(main(["ingest", "RDV", "--source", str(src)]), 0)
        self.ws = self.temp / "workspaces" / "RDV"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _add_backlog(self) -> None:
        backlog = self.ws / "04_backlog"
        backlog.mkdir(parents=True, exist_ok=True)
        for story in ("US-001", "US-002"):
            (backlog / f"{story}.md").write_text(f"# {story}\n", encoding="utf-8")
        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        state["story_gates"] = {
            "US-001": {"dor": {"passed": True, "missing": []}, "dod": {"passed": False, "missing": []}},
            "US-002": {"dor": {"passed": False, "missing": ["acceptance criteria owner"]}, "dod": {"passed": False, "missing": []}},
        }
        (self.ws / "state.json").write_text(json.dumps(state), encoding="utf-8")
        plan = {"checkpoints": [
            {"id": "CHK-WAVE-01", "stories": ["US-001"]},
            {"id": "CHK-WAVE-02", "stories": ["US-001", "US-002"]},
            {"id": "CHK-WAVE-03", "stories": []},
        ]}
        (self.ws / "08_context_packs").mkdir(parents=True, exist_ok=True)
        (self.ws / "08_context_packs" / "slice_plan.json").write_text(json.dumps(plan), encoding="utf-8")

    def _items(self, model: dict) -> dict:
        return {item["id"]: item for item in model["items"]}

    def test_workspace_item_carries_the_governed_verdict(self) -> None:
        model = collect_readiness_model("RDV")
        verdict = build_readiness_verdict("RDV")
        self.assertEqual(self._items(model)["workspace"]["verdict"], verdict["verdict"])
        self.assertEqual(model["verdict"]["verdict"], verdict["verdict"])
        self.assertEqual(validate_readiness_model(model), [])

    def test_every_open_gap_is_a_request_and_blocking_ones_block_the_start(self) -> None:
        model = collect_readiness_model("RDV")
        verdict = build_readiness_verdict("RDV")
        requests = {r["source_id"]: r for r in model["requests"] if r["kind"] == "gap"}
        open_total = verdict["counts"]["open"] + verdict["counts"]["answered"] + verdict["counts"]["partially_closed"]
        self.assertEqual(len(requests), open_total)
        for gap_id in verdict["blocking_open"]:
            self.assertEqual(requests[gap_id]["blocks"], "start")
        self.assertTrue(all(r["blocks"] in {"start", "slice", "no"} for r in model["requests"]))

    def test_unregistered_owners_are_unassigned_never_invented(self) -> None:
        model = collect_readiness_model("RDV")
        self.assertTrue(model["recipients"])
        self.assertTrue(all(not r["assigned"] for r in model["recipients"]))

    def test_a_registered_stakeholder_receives_its_lens(self) -> None:
        self.assertEqual(main(["stakeholders", "RDV", "--add", "--id", "STK-001", "--name", "Dana Ops", "--domain", "business"]), 0)
        model = collect_readiness_model("RDV")
        dana = [r for r in model["recipients"] if r["key"] == "stk:STK-001"]
        self.assertEqual(len(dana), 1)
        self.assertTrue(dana[0]["assigned"])
        self.assertTrue(dana[0]["request_ids"])

    def test_stories_and_waves(self) -> None:
        self._add_backlog()
        model = collect_readiness_model("RDV")
        items = self._items(model)
        self.assertEqual(items["US-001"]["verdict"], "READY")
        self.assertEqual(items["US-002"]["verdict"], "NOT_READY")
        dor = [r for r in model["requests"] if r["item"] == "US-002"]
        self.assertEqual([(r["kind"], r["blocks"], r["recipient"]) for r in dor], [("dor", "slice", "ba")])
        self.assertEqual(items["CHK-WAVE-01"]["verdict"], "READY")
        self.assertEqual(items["CHK-WAVE-02"]["verdict"], "NOT_READY")  # the most severe of its stories
        self.assertEqual(items["CHK-WAVE-03"]["verdict"], "READY_WITH_WARNINGS")  # no stories: never green
        self.assertTrue(items["CHK-WAVE-03"]["empty"])
        self.assertEqual(validate_readiness_model(model), [])

    def test_validation_rejects_an_inconsistent_model(self) -> None:
        self._add_backlog()
        model = collect_readiness_model("RDV")
        broken = json.loads(json.dumps(model))
        broken["requests"].append(dict(broken["requests"][0]))
        broken["requests"][-1]["item"] = "US-999"
        broken["summary"]["requests"] += 5
        for item in broken["items"]:
            if item["id"] == "CHK-WAVE-03":
                item["verdict"] = "READY"
        errors = validate_readiness_model(broken)
        self.assertTrue(any("duplicate request" in e for e in errors), errors)
        self.assertTrue(any("US-999" in e for e in errors), errors)
        self.assertTrue(any("summary.requests" in e for e in errors), errors)
        self.assertTrue(any("CHK-WAVE-03" in e and "green" in e for e in errors), errors)
        with self.assertRaises(ReadinessModelError):
            render_readiness_view(broken, load_theme())

    def test_render_is_deterministic_and_self_contained(self) -> None:
        model = collect_readiness_model("RDV")
        first = render_readiness_view(model, load_theme())
        second = render_readiness_view(collect_readiness_model("RDV"), load_theme())
        self.assertEqual(first, second)
        self.assertIn("Content-Security-Policy", first)
        self.assertIn('id="readiness-data"', first)
        self.assertIn("ignite-sentinel:readiness:", first)
        self.assertIn("try {", first)
        self.assertNotIn(str(self.temp), first)

    def test_cli_writes_the_view(self) -> None:
        self.assertEqual(main(["view", "RDV", "--artifact", "readiness"]), 0)
        out = self.ws / "08_context_packs" / "views" / "readiness.html"
        self.assertTrue(out.exists())
        self.assertIn("readiness-data", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
