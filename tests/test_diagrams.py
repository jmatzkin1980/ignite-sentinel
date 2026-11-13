"""IMP-273 (H17b): to-be diagrams, deterministic Mermaid from the v2 brief.

Golden per type (state, sequence, architecture with its compared As-Is, series), pending
sections dashed with their GAP, nothing inferred from prose, big diagrams split, labels
sanitized, the vendored mermaid pinned by sha256 (/doctor) and the view working offline
under the CSP.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel import diagrams
from sentinel.brief_model import parse_brief
from sentinel.cli import main
from sentinel.diagrams import (
    COPY, DASHED, MAX_EDGES, build_cards, inline_mermaid, mermaid_status, parse_components, parse_edges,
    read_section, series_mermaid, validate_diagrams_model,
)
from sentinel.doctor import vendored_mermaid_check
from sentinel.shell import VIEW_CSP

ROOT = Path(__file__).resolve().parent
BRIEF = ROOT / "fixtures" / "golden" / "brief_v2" / "en" / "project-brief.md"
SECTIONS = ROOT / "fixtures" / "synthetic_diagrams" / "sections.json"
GOLDEN = ROOT / "fixtures" / "golden" / "diagrams"

# Synthetic series (labelled): three releases in two waves, one soft edge.
SERIES_WAVES = {"1": ["r1"], "2": ["r2", "r3"]}
SERIES_RELEASES = [
    {"id": "r1", "name": "Claim intake", "type": "mvp", "status": "closed", "depends_on": []},
    {"id": "r2", "name": "Payout", "type": "increment", "status": "open",
     "depends_on": [{"release": "r1", "strength": "hard", "consumes": "K1"}]},
    {"id": "r3", "name": "Reporting", "type": "enabler", "status": "waiting",
     "depends_on": [{"release": "r2", "strength": "hard", "consumes": ""}, {"release": "r1", "strength": "soft", "consumes": ""}]},
]


def without_library(page: str) -> str:
    """The page the workspace produced, without the vendored third-party library."""
    return re.sub(r"/\*! mermaid.*?</script>", "</script>", page, flags=re.DOTALL)


def replace_sections(text: str, bodies: dict[str, list[str]]) -> str:
    """The brief with the body of each given section replaced (bottom-up, so indexes hold)."""
    lines = text.splitlines()
    model = parse_brief(text)
    for sid in sorted(bodies, key=lambda s: model.sections[s].start, reverse=True):
        section = model.sections[sid]
        lines[section.start + 1:section.end] = ["", *bodies[sid], ""]
    return "\n".join(lines) + "\n"


def synthetic_brief(extra: dict[str, list[str]] | None = None) -> str:
    bodies = {k: v for k, v in json.loads(SECTIONS.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    bodies.update(extra or {})
    return replace_sections(BRIEF.read_text(encoding="utf-8"), bodies)


def cards_by_id(text: str, language: str = "en") -> dict[str, dict]:
    return {card["id"]: card for card in build_cards("NO_SUCH_PROJECT", text, language)}


class GoldenTests(unittest.TestCase):
    def test_golden_per_type(self) -> None:
        cards = cards_by_id(synthetic_brief())
        produced = {key: cards[key]["mermaid"] for key in ("state", "sequence", "architecture", "architecture-asis")}
        produced["series"] = series_mermaid(SERIES_WAVES, SERIES_RELEASES, COPY["en"])
        for key, code in produced.items():
            with self.subTest(diagram=key):
                self.assertEqual(code, (GOLDEN / f"{key}.mmd").read_text(encoding="utf-8"))

    def test_two_builds_are_identical(self) -> None:
        text = synthetic_brief()
        self.assertEqual(build_cards("NO_SUCH_PROJECT", text, "en"), build_cards("NO_SUCH_PROJECT", text, "en"))

    def test_what_changes_and_what_is_missing(self) -> None:
        cards = cards_by_id(synthetic_brief())
        architecture = cards["architecture"]
        self.assertEqual(architecture["status"], "drawn")
        self.assertIn("4 components (1 new, 1 extends, 1 unchanged, 1 retired), 3 integrations", architecture["changes"])
        self.assertTrue(any(m.startswith("Payments gateway: in the integration map but not among") for m in architecture["missing"]))
        self.assertIn("GAP-TECH-DEEP-DIVE-INPUT", architecture["gaps"])  # §5.6 resilience is still pending
        self.assertIn("pending1", architecture["mermaid"])
        self.assertEqual(cards["sequence"]["sources"], ["F-01"])
        self.assertIn("1 conditional or optional (dashed)", cards["state"]["changes"])

    def test_spanish_copy(self) -> None:
        cards = cards_by_id(synthetic_brief(), "es")
        self.assertEqual(cards["state"]["title"], "Máquina de estados y ciclo de vida")
        self.assertIn("4 componentes (1 nuevo, 1 extiende, 1 sin cambios, 1 se retira), 3 integraciones", cards["architecture"]["changes"])


class PendingAndNotationTests(unittest.TestCase):
    def test_pending_sections_are_dashed_with_their_gap(self) -> None:
        cards = cards_by_id(BRIEF.read_text(encoding="utf-8"))
        for key in ("state", "sequence", "architecture"):
            with self.subTest(card=key):
                self.assertEqual(cards[key]["status"], "pending")
                self.assertIn(DASHED, cards[key]["mermaid"])
                self.assertTrue(cards[key]["gaps"])
        self.assertIn("GAP-PRODUCT-ASIS-TOBE", cards["state"]["mermaid"])
        self.assertNotIn("architecture-asis", cards)

    def test_prose_is_not_diagrammed(self) -> None:
        text = synthetic_brief({"3.4": ["- The claim goes through several steps until it is paid. [[sources § Source log # F-01 — supports: States]]"]})
        card = cards_by_id(text)["state"]
        self.assertEqual(card["status"], "no_notation")
        self.assertEqual(card["mermaid"], "")
        self.assertIn("STATE → STATE: event", card["missing"][0])

    def test_not_applicable(self) -> None:
        card = cards_by_id(synthetic_brief({"3.3": ["N/A — the flow is simple."]}))["sequence"]
        self.assertEqual(card["status"], "not_applicable")
        self.assertEqual(card["mermaid"], "")

    def test_a_big_diagram_is_split(self) -> None:
        rows = [f"- S{i} → S{i + 1}: step {i}" for i in range(MAX_EDGES + 6)]
        cards = cards_by_id(synthetic_brief({"3.4": rows}))
        self.assertNotIn("state", cards)
        self.assertEqual(cards["state-1"]["title"], "State machine and lifecycle — part 1 of 2")
        self.assertEqual(cards["state-1"]["mermaid"].count(" : step "), MAX_EDGES)
        self.assertEqual(cards["state-2"]["mermaid"].count(" : step "), 6)

    def test_labels_are_sanitized(self) -> None:
        text = synthetic_brief({"3.3": ['- A"]; click A call alert(1) → <b>B</b>: x|y{z}#1']})
        code = cards_by_id(text)["sequence"]["mermaid"]
        body = code.split("\n", 1)[1]
        for character in '"[];<>|{}#':
            self.assertNotIn(character, body.replace("->>", ""), character)

    def test_table_headers_must_name_their_columns(self) -> None:
        facts = read_section(synthetic_brief({"3.4": ["| A | B | C |", "|---|---|---|", "| x | y | z |"]}), ("3.4",))
        self.assertEqual(parse_edges(facts), [])
        facts = read_section(synthetic_brief({"5.1": ["| Componente | Estado |", "|---|---|", "| Portal | nuevo |", "| Fax | se retira |"]}), ("5.1",))
        self.assertEqual(parse_components(facts), [{"name": "Portal", "status": "new"}, {"name": "Fax", "status": "retired"}])

    def test_the_model_validator(self) -> None:
        model = {"cards": [{"id": "x", "status": "pending", "mermaid": "flowchart LR\n"}], "summary": {"cards": 1},
                 "provenance": {"cutoff": "c", "source_sha256": "s"}}
        self.assertEqual(validate_diagrams_model(model), ["x: a pending card must be dashed"])


class VendoredMermaidTests(unittest.TestCase):
    def test_pinned_and_checked_by_doctor(self) -> None:
        self.assertEqual(mermaid_status(), ("ok", ""))
        self.assertEqual(vendored_mermaid_check(ROOT.parent)["status"], "PASS")

    def test_a_tampered_file_fails(self) -> None:
        with patch.object(diagrams, "MERMAID_SHA256", "0" * 64):
            self.assertEqual(mermaid_status()[0], "hash")
            self.assertEqual(vendored_mermaid_check(ROOT.parent)["status"], "FAIL")
            self.assertEqual(inline_mermaid(), (None, "hash"))

    def test_missing_outside_a_checkout_passes(self) -> None:
        with patch.object(diagrams, "mermaid_status", return_value=("missing", "not bundled")):
            self.assertEqual(vendored_mermaid_check(Path(tempfile.gettempdir()))["status"], "PASS")
            self.assertEqual(vendored_mermaid_check(ROOT.parent)["status"], "FAIL")

    def test_inline_carries_the_mit_notice_and_no_script_close(self) -> None:
        library, reason = inline_mermaid()
        self.assertEqual(reason, "ok")
        self.assertTrue(library.startswith(f"/*! mermaid {diagrams.MERMAID_VERSION}\nThe MIT License (MIT)"))
        self.assertIsNone(re.search(r"</script", library, re.IGNORECASE))

    def test_package_data_and_attributes(self) -> None:
        pyproject = (ROOT.parent / "pyproject.toml").read_text(encoding="utf-8")
        for glob in ('"vendor/mermaid/*.js"', '"vendor/mermaid/LICENSE"'):
            self.assertIn(glob, pyproject)
        self.assertIn("**/vendor/mermaid/* -text", (ROOT.parent / ".gitattributes").read_text(encoding="utf-8"))


class ViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        self.assertEqual(self.cli("init", "P")[0], 0)
        self.base = Path("workspaces") / "P"
        (self.base / "02_requirements" / "project-brief.md").write_text(synthetic_brief(), encoding="utf-8")
        self.page = self.base / "08_context_packs" / "views" / "diagrams.html"

    def tearDown(self) -> None:
        os.chdir(self.old)
        self.tmp.cleanup()

    def cli(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = main(list(argv))
        return code, out.getvalue()

    def test_the_view_is_self_contained(self) -> None:
        code, out = self.cli("view", "P", "--artifact", "diagrams")
        self.assertEqual(code, 0, out)
        page = self.page.read_text(encoding="utf-8")
        self.assertTrue(f'content="{VIEW_CSP}"' in page)
        self.assertTrue("Rendered locally with the vendored mermaid 11.17.2" in page)
        self.assertTrue("/*! mermaid 11.17.2" in page)
        own = without_library(page)
        self.assertLess(len(own), 200_000)
        self.assertEqual(own.count("<script"), own.count("</script>"))
        self.assertEqual(page.count("</script>"), own.count("</script>"))  # the library closes no script early
        self.assertIsNone(re.search(r"<(?:link|iframe|img)\b|\ssrc=|https?://", own))
        self.assertIn('id="dg-state"', own)
        self.assertIn("stateDiagram-v2", own)
        first = self.page.read_bytes()
        self.assertEqual(self.cli("view", "P", "--artifact", "diagrams")[0], 0)
        self.assertTrue(self.page.read_bytes() == first, "two renders differ")

    def test_without_the_library_the_code_is_shown(self) -> None:
        with patch.object(diagrams, "MERMAID_SHA256", "0" * 64):
            self.assertEqual(self.cli("view", "P", "--artifact", "diagrams")[0], 0)
        page = self.page.read_text(encoding="utf-8")
        self.assertIn("No renderer available: the vendored mermaid failed its sha256 check", page)
        self.assertIn("Not rendered: the code is shown as is.", page)
        self.assertNotIn("/*! mermaid", page)

    def test_a_v1_workspace_is_refused(self) -> None:
        (self.base / "02_requirements" / "project-brief.md").write_text("# Project Brief\n\n## 1. Overview\n\nx\n", encoding="utf-8")
        code, out = self.cli("view", "P", "--artifact", "diagrams")
        self.assertNotEqual(code, 0)
        self.assertIn("reads the v2 brief", out)

    def test_the_series_card(self) -> None:
        series = self.base / "02_requirements" / "series"
        series.mkdir(parents=True, exist_ok=True)
        (series / "partition.json").write_text(json.dumps({
            "status": "confirmed", "releases": ["r1", "r2", "r3"], "waves": SERIES_WAVES,
            "closed": {"r1": {"date": "2026-11-01", "evidence": "check.md"}},
        }), encoding="utf-8")
        releases = [{"id": r["id"], "name": r["name"], "type": r["type"], "wave": 1 if r["id"] == "r1" else 2,
                     "depends_on": [{**d, "why": "synthetic"} for d in r["depends_on"]]} for r in SERIES_RELEASES]
        (series / "proposal.json").write_text(json.dumps({"proposal": {"releases": releases}}), encoding="utf-8")
        cards = {c["id"]: c for c in build_cards("P", synthetic_brief(), "en")}
        self.assertEqual(cards["series"]["mermaid"], (GOLDEN / "series.mmd").read_text(encoding="utf-8"))
        self.assertEqual([c["text"] for c in cards["series"]["chips"]], ["r1 · closed", "r2 · open", "r3 · waiting on a dependency"])


if __name__ == "__main__":
    unittest.main()
