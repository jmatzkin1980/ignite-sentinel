"""IMP-369: the BA never stays in DIRTY without a command that gets them out.

Each test reproduces a dead end found on a live project run:
- a semantic change (/sync "now ... out of scope") had no way to record the BA review;
- the DIRTY refusal of /backlog showed one finding and "(1 more finding(s))";
- /next said "Fix what makes the project unhealthy" without naming the command;
- /backlog ran on specs older than the brief when /resolve-gaps left health CLEAN;
- /resolve-gaps whose only ids were unknown still marked the downstream stale;
- a refused /specs wrote gaps.md and the next /brief called it a hand edit.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from sentinel.cli import main
from sentinel.health import pending_stale_artifacts

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, build_matured_workspace, gap_acceptance_answer  # noqa: E402

PROJECT = "EXITS"
RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads.

In scope: read-only risk dashboard for open queues, with an export of each queue.
"""
EARS = "When queue metrics are available, the system shall display open risk queues."
SCOPE_CUT = "Steering decision: the queue export is now out of scope for the first release.\n"
SEMANTIC = "Semantic change may invalidate downstream trace links"


def run(args: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


def ok(args: list[str]) -> dict:
    code, out, err = run(args)
    if code != 0:
        raise AssertionError(f"{args[0]} exited {code}: {err}")
    return json.loads(out) if out.strip().startswith("{") else {}


def run_health(project: str) -> dict:
    """/health through the CLI: a direct call keeps an in-process write snapshot that the
    per-test workspace restore invalidates (WriteConflict on health_report.json)."""
    return ok(["health", project])


class DirtyExitTests(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        build_matured_workspace(PROJECT, RAW, gap_acceptance_answer(EARS))

    def ws(self) -> Path:
        return self.temp / "workspaces" / PROJECT

    def state(self) -> dict:
        return json.loads((self.ws() / "state.json").read_text(encoding="utf-8"))

    def write_state(self, state: dict) -> None:
        (self.ws() / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

    def scope_cut(self) -> str:
        (self.temp / "scope-cut.md").write_text(SCOPE_CUT, encoding="utf-8")
        result = ok(["sync", PROJECT, "--source", str(self.temp / "scope-cut.md"), "--note", "steering decision"])
        self.assertTrue(result["suspicious_trace_links"], "the change words must flag the trace links")
        return str(result["change_id"])

    def age_semantic_marker(self) -> None:
        """Move the change and the artifacts generated before it into the past (1 s mtime granularity)."""
        state = self.state()
        marker = state["suspicious_trace_links"]
        now = datetime.now(timezone.utc).replace(microsecond=0)
        marker["recorded_at"] = (now - timedelta(seconds=10)).isoformat()
        self.write_state(state)
        before = (now - timedelta(seconds=60)).timestamp()
        for item in marker["downstream_artifacts"]:
            os.utime(item, (before, before))

    # --- 1. the semantic-change finding has a clearing command --------------------------

    def test_semantic_change_names_the_review_command_and_trace_reviewed_clears_it(self) -> None:
        change = self.scope_cut()
        findings = [f for f in run_health(PROJECT)["findings"] if SEMANTIC in f]
        self.assertEqual(len(findings), 1)
        self.assertIn(f"/trace {PROJECT} --reviewed {change}", findings[0])
        self.assertIn("then run /brief, then /specs, then /backlog", findings[0])

        code, _, err = run(["backlog", PROJECT])
        self.assertEqual(code, 4, err)
        self.assertIn(f"/trace {PROJECT} --reviewed {change}", err)

        code, _, err = run(["trace", PROJECT, "--reviewed", "CHG-999"])
        self.assertEqual(code, 3, err)  # only the change /health names
        result = ok(["trace", PROJECT, "--reviewed", change, "--reason", "Export cut agreed; stories unaffected."])
        self.assertEqual(result["change_id"], change)
        self.assertGreater(result["reviewed_links"], 0)
        self.assertFalse([f for f in run_health(PROJECT)["findings"] if SEMANTIC in f])
        graph = json.loads((self.ws() / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8"))
        flagged = [e for e in graph["edges"] if e.get("from") == change and e.get("suspicious")]
        self.assertTrue(flagged)
        self.assertTrue(all(e["review_status"] == "reviewed" for e in flagged))
        self.assertEqual(self.state()["suspicious_trace_links"]["reviewed"]["reason"], "Export cut agreed; stories unaffected.")

    def test_regenerating_the_downstream_clears_the_semantic_change(self) -> None:
        self.scope_cut()
        self.age_semantic_marker()
        code, _, err = run(["backlog", PROJECT])
        self.assertEqual(code, 4, err)
        self.assertIn("Run /brief, then /specs, then /backlog.", err)
        ok(["brief", PROJECT])
        ok(["specs", PROJECT])
        # only the backlog artifacts are left: /backlog is the step that clears it
        ok(["backlog", PROJECT])
        self.assertFalse([f for f in run_health(PROJECT)["findings"] if SEMANTIC in f])

    def test_a_neutral_sync_does_not_wipe_a_pending_review(self) -> None:
        change = self.scope_cut()
        (self.temp / "note.md").write_text("Minutes: the team met and agreed the agenda.\n", encoding="utf-8")
        ok(["sync", PROJECT, "--source", str(self.temp / "note.md"), "--note", "minutes"])
        findings = [f for f in run_health(PROJECT)["findings"] if SEMANTIC in f]
        self.assertEqual(len(findings), 1)
        self.assertIn(change, findings[0])

    # --- 4/5/6. /next and the refusal name every fix, in order ------------------------

    def test_refusal_lists_each_finding_with_its_fix_in_order(self) -> None:
        state = self.state()
        state["story_lifecycle"]["US-001"] = {"status": "Stale", "owner": ""}
        state["health"] = "DIRTY"
        self.write_state(state)
        with mock.patch("sentinel.health.has_blocking_open_gap", return_value=True):
            code, _, err = run(["backlog", PROJECT])
        self.assertEqual(code, 4, err)
        self.assertNotIn("more finding(s)", err)
        first = err.index("1. Blocking gaps remain open.")
        second = err.index("2. Backlog contains Stale stories after source changes: US-001. ")
        self.assertLess(first, second)
        self.assertIn(f"/story-status {PROJECT} --story US-001 --set Draft", err)
        self.assertIn("3. Run /backlog again.", err)
        self.assertIn(f"next step: Run /resolve-gaps {PROJECT} --source ANSWERS, then "
                      f"/story-status {PROJECT} --story US-001 --set Draft, then /backlog.", err)

        step = ok(["next", PROJECT])
        self.assertEqual(step["command"], f"/story-status {PROJECT} --story US-001 --set Draft")
        self.assertEqual(step["title"], "Review the Stale stories")

    def test_next_and_backlog_name_the_regeneration_chain_even_when_health_reads_clean(self) -> None:
        # /resolve-gaps sets health CLEAN on its own criteria; the marker still says the
        # specs are older than the brief. /backlog must not run on them.
        base = self.ws()
        state = self.state()
        now = datetime.now(timezone.utc).replace(microsecond=0)
        artifacts = [(base / rel).as_posix() for rel in ("03_specs/prd.md", "03_specs/specs.md", "04_backlog/BACKLOG.md")]
        state["knowledge_staleness"] = {"change_id": "CHG-001", "impacted_knowledge_units": [],
                                        "downstream_artifacts": artifacts, "recorded_at": (now + timedelta(seconds=30)).isoformat()}
        state["health"] = "CLEAN"
        self.write_state(state)

        step = ok(["next", PROJECT])
        self.assertEqual(step["command"], f"/specs {PROJECT}")
        self.assertIn("Run /specs, then /backlog.", step["text"])
        self.assertEqual(step["title"], "Regenerate what the change made stale")

        code, _, err = run(["backlog", PROJECT])
        self.assertEqual(code, 4, err)
        self.assertIn("Run /specs, then /backlog.", err)

    def test_quality_without_change_still_refuses_a_dirty_project(self) -> None:
        """IMP-431: only `--change` leaves the project's DIRTY gate; the project's /quality keeps today's refusal."""
        state = self.state()
        state["story_lifecycle"]["US-001"] = {"status": "Stale", "owner": ""}
        state["health"] = "DIRTY"
        self.write_state(state)
        with mock.patch("sentinel.health.has_blocking_open_gap", return_value=True):
            code, _, err = run(["quality", PROJECT])
        self.assertEqual(code, 4, err)
        self.assertIn("1. Blocking gaps remain open.", err)
        self.assertIn("Run /quality again.", err)

    def test_next_names_reindex_when_a_node_is_not_indexed(self) -> None:
        with mock.patch("sentinel.health.collect_health") as collect:
            collect.return_value = {"findings": ["CHG-042 is not indexed in memory."], "knowledge_staleness": [],
                                    "suspicious_trace_links": [], "remediated_by_backlog": []}
            state = self.state()
            state["health"] = "DIRTY"
            self.write_state(state)
            step = ok(["next", PROJECT])
        self.assertEqual(step["command"], f"/reindex {PROJECT}")

    # --- 2. a command indexes the records it adds ----------------------------------------

    def test_stakeholders_add_keeps_health_clean(self) -> None:
        # IMP-369 (with IMP-370's finding): /stakeholders --add wrote a DISC node that was
        # never indexed, so /health said "DISC-005 is not indexed in memory." until /reindex.
        before = run_health(PROJECT)
        self.assertEqual(before["verdict"], "CLEAN", before["findings"])
        ok(["stakeholders", PROJECT, "--add", "--name", "Ana Ruiz", "--domain", "quality", "--topic", "acceptance"])
        report = run_health(PROJECT)
        self.assertFalse([f for f in report["findings"] if "not indexed" in f], report["findings"])
        self.assertEqual(report["verdict"], "CLEAN", report["findings"])

    # --- 7. /resolve-gaps that moved nothing marks nothing stale -------------------------

    def test_resolve_gaps_with_only_unknown_ids_marks_nothing_stale(self) -> None:
        state = self.state()
        state.pop("knowledge_staleness", None)
        self.write_state(state)
        answers = self.temp / "feedback-answer.md"
        answers.write_text(
            "# Answers\n\n### GAP-FEEDBACK-001\n- Answer: The developers confirmed the export is fine as built.\n"
            "- Owner / source: Tech lead\n- Evidence or reference: standup\n- Decision status: confirmed\n",
            encoding="utf-8",
        )
        result = ok(["resolve-gaps", PROJECT, "--source", str(answers)])
        self.assertEqual(result["closed"], [])
        self.assertEqual(result["unknown_gap_ids"], ["GAP-FEEDBACK-001"])
        self.assertEqual(result["knowledge_metabolism"]["downstream_stale_artifacts"], [])
        self.assertEqual(pending_stale_artifacts(PROJECT), [])


class RefusedCommandHandEditTests(unittest.TestCase):
    """IMP-369 (8): a refused /specs wrote gaps.md; the next /brief called it a hand edit."""

    def setUp(self) -> None:
        self.old = Path.cwd()
        self.tmp = Path(tempfile.mkdtemp())
        os.chdir(self.tmp)

    def tearDown(self) -> None:
        os.chdir(self.old)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_refused_specs_does_not_turn_its_own_write_into_a_hand_edit(self) -> None:
        (self.tmp / "raw.md").write_text(RAW, encoding="utf-8")
        ok(["init", "REFUSED"])
        ok(["ingest", "REFUSED", "--source", str(self.tmp / "raw.md")])
        code, _, err = run(["specs", "REFUSED"])
        self.assertEqual(code, 4, err)
        code, _, err = run(["brief", "REFUSED", "--profile", "UI", "--genesis", "greenfield"])
        self.assertEqual(code, 0, err)
        self.assertNotIn("hand-edited", err)
        report = run_health("REFUSED")
        self.assertFalse([w for w in report["warnings"] if "edited outside the CLI" in w], report["warnings"])


class BriefRiskAndNonSoftwareAnswerTests(unittest.TestCase):
    """IMP-369 (9): answers to §7.1 and §9.1 (and the glossary gap) stay in the brief.

    Before, GAP-BRIEF-S7 and GAP-BRIEF-S9 closed on /resolve-gaps and reopened on the
    next compile, and the dropped answers failed the self-correction gate, so /next said
    "Fix what stopped the brief".
    """

    FIXTURE = Path(__file__).resolve().parent / "fixtures" / "evals" / "support-dashboard" / "requirement.md"

    def setUp(self) -> None:
        self.old = Path.cwd()
        self.tmp = Path(tempfile.mkdtemp())
        os.chdir(self.tmp)

    def tearDown(self) -> None:
        os.chdir(self.old)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def answer_everything(self, pid: str) -> Path | None:
        from sentinel.gaps import parse_gap_table

        gaps_path = self.tmp / "workspaces" / pid / "01_discovery" / "gaps.md"
        blocks = []
        for gap in parse_gap_table(gaps_path.read_text(encoding="utf-8")):
            if str(gap.get("status", "")).upper() == "CLOSED":
                continue
            gid = str(gap["id"]).strip("`")
            places = list(dict.fromkeys(re.findall(r"(\d+\.\d+) ", str(gap.get("question", "")))))
            text = (" ".join(f"{p}: confirmed by the sponsor in the workshop of 12 March." for p in places)
                    if gid.startswith("GAP-BRIEF-S") else
                    f"Confirmed by the sponsor in the workshop: the rule and the owner for {gid} are fixed in the minutes.")
            blocks.append(f"### {gid}\n- Answer: {text}\n- Owner / source: Client sponsor\n"
                          "- Evidence or reference: workshop minutes, 12 March\n- Decision status: confirmed\n")
        if not blocks:
            return None
        path = self.tmp / f"answers-{len(list(self.tmp.glob('answers-*.md')))}.md"
        path.write_text("# Answers (synthetic)\n\n" + "\n".join(blocks), encoding="utf-8")
        return path

    def test_umbrella_answers_for_7_1_and_9_1_stay_closed_after_the_brief(self) -> None:
        from sentinel.gaps import parse_gap_table
        from sentinel.memory import ContextBroker

        pid = "RISKS"
        with mock.patch.object(ContextBroker, "_connect_lancedb", lambda self: None):
            ok(["init", pid])
            ok(["ingest", pid, "--source", str(self.FIXTURE)])
            ok(["brief", pid, "--profile", "UI", "--genesis", "greenfield"])
            # the first round closes the routed gaps; the recompile opens the §7/§9
            # umbrellas, which the later rounds answer place by place (`7.1: …`)
            gaps_path = self.tmp / "workspaces" / pid / "01_discovery" / "gaps.md"
            seen: set[str] = set()
            for _ in range(3):
                seen |= {g["id"] for g in parse_gap_table(gaps_path.read_text(encoding="utf-8"))
                         if g["id"] in ("GAP-BRIEF-S7", "GAP-BRIEF-S9")}
                answers = self.answer_everything(pid)
                if answers is None:
                    break
                ok(["resolve-gaps", pid, "--source", str(answers)])
            brief = ok(["brief", pid])
        self.assertFalse(brief["self_correction"]["findings"], brief["self_correction"]["findings"])
        self.assertFalse(brief["blocked"])
        rows = {g["id"]: g for g in parse_gap_table(gaps_path.read_text(encoding="utf-8"))}
        self.assertTrue(seen, "the rounds must reach a §7 or §9 umbrella")
        for gid in seen:
            self.assertEqual(rows[gid]["status"], "CLOSED", gid)
        text = (self.tmp / "workspaces" / pid / "02_requirements" / "project-brief.md").read_text(encoding="utf-8")
        for gid in seen:
            self.assertIn(f"(`{gid}`)", text)
        self.assertIn("(`GAP-PRD-DEPENDENCIES-ROADMAP`)", text)  # §7.1 carries its confirmed answer


if __name__ == "__main__":
    unittest.main()
