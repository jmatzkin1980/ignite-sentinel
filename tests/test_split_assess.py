"""IMP-263 (H17a): /split --assess.

Deterministic signals over a brief v2, read from the release split model
(IMP-264). No numeric threshold on the signals: the assessment reports which
signals are lit, each with its anchor, and recommends split, no split or cannot
decide, each with its reason. A v1 brief is rejected [A43].
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from sentinel import split as sp
from sentinel.cli import main
from sentinel.release_split_model import load_release_split_model

MARKER = "<!-- sentinel-artifact: v2 -->"
TITLES = {
    "1": "Overview", "1.3": "Success Metrics / Scope", "1.4": "Starting Point and End Point",
    "1.5": "Release Acceptance Criteria", "2": "Business Lens", "2.1": "Actors and Goals by Role",
    "2.4": "Business Need", "3": "Product Lens", "3.2": "To-Be Process", "3.6": "Error Handling / Edge Cases",
    "4": "Design Lens", "4.2": "UX Considerations", "5": "Technical Lens", "5.1": "Architecture and Integrations",
    "5.6": "Integration Map", "5.17": "Parity Verification", "6": "Release Agreements", "6.1": "In Scope",
    "6.2": "Out of Scope", "7": "Dependencies and Open Questions", "7.1": "Open Items Table",
    "9": "Things to Build", "9.1": "Build List or Phases",
}
PENDING = "⏳ PENDING (GAP-BRIEF-S1)"


def fact(text: str, n: int = 1) -> str:
    return f"- {text} [[sources § Log # F-{n:02d} — supports: x]]"


def brief(places: dict[str, list[str]]) -> str:
    """A minimal v2 brief: every listed place with its lines, the rest pending."""
    lines = [MARKER, "# Project Brief — P", ""]
    for section in ("1", "2", "3", "4", "5", "6", "7", "9"):
        lines += [f"## {section}. {TITLES[section]}", ""]
        for sid in [k for k in TITLES if k.startswith(section + ".")]:
            lines += [f"### {sid} {TITLES[sid]}", "", *(places.get(sid) or [PENDING]), ""]
    return "\n".join(lines) + "\n"


def build_items(n: int) -> list[str]:
    return [f"- `C-{i:02d}` item {i} [[sources § Log # F-01 — supports: Build]] — depends on: none" for i in range(1, n + 1)]


SMALL = {
    "1.5": [fact("the agent sees the queue", 1), fact("the lead sees the trend", 2)],
    "2.1": [fact("support agent answers tickets", 1)],
    "6.1": [fact("ticket volume chart", 1)],
    "9.1": build_items(3),
}
SETTINGS = {"profiles": ["UI"], "genesis": "greenfield"}


def assess(places: dict[str, list[str]], settings: dict | None = None, report: dict | None = None,
           gaps: list[dict] | None = None) -> dict:
    return sp.assess_brief(brief(places), report or {}, settings or SETTINGS, gaps or [])


def status(result: dict, sid: str) -> str:
    return next(s["status"] for s in result["signals"] if s["id"] == sid)


class SignalTests(unittest.TestCase):
    def test_every_model_signal_is_assessed_once(self) -> None:
        model = load_release_split_model()
        expected = [s["id"] for s in model["signals"]["split"]] + [s["id"] for s in model["signals"]["no_split"]]
        self.assertEqual([s["id"] for s in assess(SMALL)["signals"]], expected)

    def test_small_brief_lights_nothing_and_recommends_no_split(self) -> None:
        result = assess(SMALL)
        self.assertEqual([s["id"] for s in result["signals"] if s["status"] == "lit"], [])
        self.assertEqual(result["recommendation"]["value"], "no_split")
        self.assertTrue(result["recommendation"]["why"])

    def test_session_size(self) -> None:
        result = assess({**SMALL, "9.1": build_items(sp.SESSION_BUILD_ITEMS + 1)})
        self.assertEqual(status(result, "S1"), "lit")
        anchor = next(s for s in result["signals"] if s["id"] == "S1")["anchors"][0]
        self.assertEqual(anchor["place"], "9.1")
        self.assertEqual(status(assess(SMALL), "S1"), "off")
        self.assertEqual(status(assess({**SMALL, "9.1": []}), "S1"), "undetermined")

    def test_actor_change_needs_two_actors_and_an_operator(self) -> None:
        two = [fact("customer submits a claim", 1), fact("back office operator approves the claim", 2)]
        self.assertEqual(status(assess({**SMALL, "2.1": two}), "S2"), "lit")
        self.assertEqual(status(assess({**SMALL, "2.1": two[:1]}), "S2"), "off")
        self.assertEqual(status(assess({**SMALL, "2.1": []}), "S2"), "undetermined")

    def test_different_timing(self) -> None:
        places = {**SMALL, "6.1": [fact("the export ships in a second stage", 1)]}
        self.assertEqual(status(assess(places), "S3"), "lit")

    def test_third_party_block(self) -> None:
        places = {**SMALL, "5.6": [fact("the third-party scoring API contract is not delivered yet", 1)]}
        self.assertEqual(status(assess(places), "S4"), "lit")
        calm = {**SMALL, "5.6": [fact("the third-party scoring API is consumed over REST", 1)]}
        self.assertEqual(status(assess(calm), "S4"), "off")

    def test_missing_oracle_only_for_replacements(self) -> None:
        replacement = {"profiles": ["MIG"], "genesis": "brownfield-replacement"}
        self.assertEqual(status(assess(SMALL, replacement), "S5"), "lit")
        with_oracle = {**SMALL, "5.17": [fact("outputs are compared file by file with the legacy run", 1)]}
        self.assertEqual(status(assess(with_oracle, replacement), "S5"), "off")
        self.assertEqual(status(assess(SMALL), "S5"), "off")

    def test_shared_surface(self) -> None:
        places = {**SMALL, "5.1": [fact("every module uses a shared authorization filter", 1)]}
        self.assertEqual(status(assess(places), "S6"), "lit")

    def test_suggested_scope(self) -> None:
        report = {"inferred": [{"place": "6.1", "assumption": "ASM-001", "gap": "GAP-X"}]}
        self.assertEqual(status(assess(SMALL, report=report), "S7"), "lit")
        places = {**SMALL, "6.1": [fact("an optional nice to have export", 1)]}
        self.assertEqual(status(assess(places), "S7"), "lit")

    def test_nothing_demonstrable(self) -> None:
        self.assertEqual(status(assess({**SMALL, "1.5": [fact("it works", 1)]}), "N1"), "lit")
        self.assertEqual(status(assess(SMALL), "N1"), "off")
        self.assertEqual(status(assess({**SMALL, "1.5": []}), "N1"), "undetermined")

    def test_proposal_level_signals_wait_for_the_proposal(self) -> None:
        result = assess(SMALL)
        for sid in ("N2", "N3", "N5"):
            self.assertEqual(status(result, sid), "on_proposal")

    def test_undecided_dependency(self) -> None:
        report = {"fill_sites": [{"id": "6.1", "class": "client", "gap": "GAP-BRIEF-S6", "gap_open": True}]}
        gaps = [{"id": "GAP-BRIEF-S6", "severity": "critical", "status": "OPEN"}]
        self.assertEqual(status(assess(SMALL, report=report, gaps=gaps), "N4"), "lit")
        self.assertEqual(status(assess(SMALL, report=report, gaps=[{**gaps[0], "severity": "low"}]), "N4"), "off")


class RecommendationTests(unittest.TestCase):
    def test_split_when_a_split_signal_is_lit_and_no_no_split_signal(self) -> None:
        result = assess({**SMALL, "9.1": build_items(sp.SESSION_BUILD_ITEMS + 1)})
        self.assertEqual(result["recommendation"]["value"], "split")
        self.assertIn("S1", " ".join(result["recommendation"]["why"]))

    def test_cannot_decide_when_both_kinds_are_lit(self) -> None:
        places = {**SMALL, "9.1": build_items(sp.SESSION_BUILD_ITEMS + 1), "1.5": [fact("it works", 1)]}
        result = assess(places)
        self.assertEqual(result["recommendation"]["value"], "cannot_decide")
        why = " ".join(result["recommendation"]["why"])
        self.assertIn("S1", why)
        self.assertIn("N1", why)

    def test_cannot_decide_without_a_build_list(self) -> None:
        self.assertEqual(assess({**SMALL, "9.1": []})["recommendation"]["value"], "cannot_decide")

    def test_step_0_is_reported(self) -> None:
        step0 = assess(SMALL)["step_0"]
        self.assertEqual([q["id"] for q in step0], ["Q1", "Q2", "Q3"])
        q2 = next(q for q in step0 if q["id"] == "Q2")
        self.assertEqual(q2["answer"], "yes")

    def test_pure_and_deterministic(self) -> None:
        self.assertEqual(assess(SMALL), assess(SMALL))


class RunAssessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["init", "P"]), 0)
        from sentinel.brief_schema import set_brief_settings

        set_brief_settings("P", profiles=["UI"], genesis="greenfield", brief_version=2)
        self.base = Path("workspaces") / "P"

    def tearDown(self) -> None:
        os.chdir(self.old)
        self.tmp.cleanup()

    def write_brief(self, text: str) -> None:
        path = self.base / "02_requirements" / "project-brief.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_writes_markdown_and_json(self) -> None:
        self.write_brief(brief(SMALL))
        result = sp.run_assess("P")
        data = json.loads((self.base / "01_discovery" / "split_assessment.json").read_text(encoding="utf-8"))
        self.assertEqual(data["recommendation"]["value"], "no_split")
        self.assertEqual(result["recommendation"], "no_split")
        md = (self.base / "01_discovery" / "split_assessment.md").read_text(encoding="utf-8")
        self.assertIn("S1", md)
        self.assertIn("no_split", md)
        self.assertEqual(data["brief_sha256"], sp.brief_hash(self.base / "02_requirements" / "project-brief.md"))

    def test_rejects_a_v1_brief(self) -> None:
        self.write_brief("# Project Brief\n\n## 1. Identidad y Valor\n\ntext\n")
        with self.assertRaises(ValueError) as caught:
            sp.run_assess("P")
        self.assertIn("A43", str(caught.exception))

    def test_rejects_a_missing_brief(self) -> None:
        with self.assertRaises(ValueError):
            sp.run_assess("P")

    def test_reassesses_when_the_brief_changes(self) -> None:
        self.write_brief(brief(SMALL))
        sp.run_assess("P")
        self.assertIsNone(sp.refresh_if_stale("P"))
        self.write_brief(brief({**SMALL, "9.1": build_items(sp.SESSION_BUILD_ITEMS + 1)}))
        refreshed = sp.refresh_if_stale("P")
        self.assertEqual(refreshed["recommendation"], "split")

    def test_cli(self) -> None:
        self.write_brief(brief(SMALL))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["split", "P", "--assess"]), 0)
        self.assertEqual(json.loads(out.getvalue())["recommendation"], "no_split")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main(["split", "P"])  # a mode is required

    def test_no_refresh_without_an_assessment(self) -> None:
        self.write_brief(brief(SMALL))
        self.assertIsNone(sp.refresh_if_stale("P"))
        self.assertFalse((self.base / "01_discovery" / "split_assessment.json").exists())


if __name__ == "__main__":
    unittest.main()
