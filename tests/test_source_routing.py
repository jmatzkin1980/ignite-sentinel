"""IMP-250b — precedence by scope, impact matrix and closing report.

Every F-NN row gets an authority (from its bucket, or `example` by file name) and
an impact matrix (document x section) from `templates/source_routing.json`. A
person closes each cell; a retired source cascades to every document. Precedence
depends on the scope of the clash, an own artifact is never an authority, an
example never closes a rule, and when no rule settles a clash the newest source
does not win by default. The closing report groups the cells by recipient and
lists the originals that are ready to delete without deleting anything.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery import parse_gap_rows
from sentinel.source_registry import SourceRegistryError
from sentinel.source_routing import (
    default_authority,
    precedence_rules,
    resolve_precedence,
    routing_data,
)
from sentinel.sources import load_source_manifest, update_source

RAW = (
    "# Reporting Portal\n\n"
    "We need a reporting portal for the operations team. The objective is to "
    "reduce manual work. Data is stored in the legacy billing system.\n"
)
MEETING = (
    "# Weekly sync\n\n"
    "- We decided the portal exports to CSV only.\n"
    "- Report data is retained for 24 months in the billing service.\n"
)


def _run(argv: list[str]) -> dict:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(argv)
    if code != 0:
        raise AssertionError(f"{argv} exited {code}: {out.getvalue()}")
    return json.loads(out.getvalue())


def _c(source_id: str, authority: str) -> dict[str, str]:
    return {"id": source_id, "authority": authority}


class PrecedenceTests(unittest.TestCase):
    def test_precedence_depends_on_scope(self) -> None:
        minutes, api, proto = _c("F-01", "minutes"), _c("F-02", "api_contract"), _c("F-03", "prototype")
        self.assertEqual(resolve_precedence("business", [minutes, _c("F-04", "client_document")])["winner"], "F-01")
        api_clash = resolve_precedence("api", [api, proto])
        self.assertEqual(api_clash["winner"], "F-02")
        self.assertTrue(api_clash["opens_gap"])
        self.assertEqual(api_clash["rules"], ["P06"])
        # Minutes govern business, not the API: no rule there, so nobody wins.
        self.assertEqual(resolve_precedence("api", [minutes, api])["status"], "unresolved")
        # Two minutes in business: "over: *" never lets an authority beat itself.
        self.assertEqual(resolve_precedence("business", [minutes, _c("F-05", "minutes")])["status"], "unresolved")

    def test_tech_lead_governs_the_stack_below_a_decision(self) -> None:
        decision, lead, doc = _c("F-01", "decision_record"), _c("F-02", "tech_lead"), _c("F-03", "client_document")
        self.assertEqual(resolve_precedence("stack_to_be", [lead, doc])["winner"], "F-02")
        self.assertEqual(resolve_precedence("stack_to_be", [lead, decision, doc])["winner"], "F-01")

    def test_echo_and_signoff_outside_design_are_not_authorities(self) -> None:
        echo = resolve_precedence("business", [_c("F-01", "own_artifact"), _c("F-02", "interaction")])
        self.assertEqual(echo["winner"], "F-02")
        self.assertIn("echo", echo["excluded"][0]["why"])
        only_echo = resolve_precedence("business", [_c("F-01", "own_artifact")])
        self.assertEqual(only_echo["status"], "unresolved")
        signoff = [_c("F-01", "prototype_signoff"), _c("F-02", "prototype")]
        self.assertEqual(resolve_precedence("design", signoff)["winner"], "F-01")
        self.assertEqual(resolve_precedence("behavior", signoff)["winner"], "F-02")

    def test_same_authority_is_never_settled_by_date(self) -> None:
        result = resolve_precedence("business", [_c("F-01", "interaction"), _c("F-07", "interaction")])
        self.assertEqual(result["status"], "unresolved")
        self.assertIsNone(result["winner"])

    def test_config_chain_replaces_one_scope(self) -> None:
        config = {"precedence": {"business": "client_document > minutes"}}
        clash = [_c("F-01", "minutes"), _c("F-02", "client_document")]
        self.assertEqual(resolve_precedence("business", clash)["winner"], "F-01")
        self.assertEqual(resolve_precedence("business", clash, config)["winner"], "F-02")
        # Other scopes keep the defaults.
        self.assertTrue(any(rule["id"] == "P06" for rule in precedence_rules(config)))
        with self.assertRaises(SourceRegistryError):
            precedence_rules({"precedence": {"business": "minutes > boss"}})
        with self.assertRaises(SourceRegistryError):
            resolve_precedence("everything", clash)

    def test_example_named_files_are_examples(self) -> None:
        self.assertEqual(default_authority("quality_context", "x/03_specs/payload-example.md"), "example")
        self.assertEqual(default_authority("client_requirement", "x/ejemplo_alta.md"), "example")
        self.assertEqual(default_authority("client_requirement", "x/exemplary-rules.md"), "client_document")
        self.assertEqual(default_authority("meeting", "x/weekly.md"), "minutes")

    def test_routing_data_is_consistent(self) -> None:
        data = routing_data()
        names = set(data["authorities"])
        self.assertEqual(set(data["routes"]), names)
        self.assertTrue(set(data["authority_by_kind"].values()) <= names)
        for rule in data["precedence"]:
            self.assertIn(rule["winner"], names)
            self.assertTrue(rule["over"] == "*" or set(rule["over"]) <= names)
        for routes in data["routes"].values():
            for route in routes:
                self.assertIn(route["section"], data["documents"][route["document"]]["sections"])


class ImpactMatrixFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        src = self.temp / "raw.md"
        src.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "IMX", "--brief-version", "1"]), 0)
        self.assertEqual(main(["ingest", "IMX", "--source", str(src)]), 0)
        self.ws = self.temp / "workspaces" / "IMX"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _row(self, source_id: str) -> dict:
        return next(row for row in load_source_manifest("IMX")["registry"] if row["id"] == source_id)

    def _sync_meeting(self, digest: bool = False) -> dict:
        path = self.ws / "07_changes" / "01_meetings" / "weekly.md"
        path.write_text(MEETING, encoding="utf-8")
        return _run(["sync", "IMX", "--source", str(path)] + (["--digest"] if digest else []))

    def test_a_new_row_gets_authority_and_routed_cells(self) -> None:
        self.assertEqual(self._row("F-01")["authority"], "client_document")
        result = self._sync_meeting()
        row = self._row(result["source_id"])
        self.assertEqual(row["authority"], "minutes")
        cells = {(cell["document"], cell["section"]) for cell in row["impact"]}
        self.assertEqual(cells, {("brief", "business"), ("requirements", "functional"), ("gaps", "open")})
        self.assertTrue(all(cell["state"] == "pending" for cell in row["impact"]))
        self.assertEqual(_run(["status", "IMX"])["sources"]["impact_pending"][row["id"]], 3)
        # A second sync over the same content keeps the matrix, it does not duplicate it.
        self._sync_meeting()
        self.assertEqual(len(self._row(row["id"])["impact"]), 3)

    def test_digest_carries_the_impact_matrix(self) -> None:
        result = self._sync_meeting(digest=True)
        digest = Path(result["interaction_digest"]["digest_path"]).read_text(encoding="utf-8")
        self.assertIn("## (e) Impact Matrix", digest)
        self.assertIn(f"Source row: `{result['source_id']}` (authority `minutes`)", digest)
        self.assertIn("`gaps / open`: pending", digest)

    def test_cells_close_as_updated_or_reviewed_with_reason(self) -> None:
        source_id = self._sync_meeting()["source_id"]
        _run(["sources", "IMX", "--id", source_id, "--cell", "brief/business", "--mark", "updated"])
        with self.assertRaises(SourceRegistryError):
            update_source("IMX", source_id, cell="gaps/open", mark="reviewed")
        _run(["sources", "IMX", "--id", source_id, "--cell", "gaps/open", "--mark", "reviewed",
              "--reason", "No open gap mentions exports"])
        states = {cell["document"]: (cell["state"], cell["reason"]) for cell in self._row(source_id)["impact"]}
        self.assertEqual(states["brief"], ("updated", None))
        self.assertEqual(states["gaps"], ("reviewed", "No open gap mentions exports"))
        self.assertEqual(states["requirements"][0], "pending")
        # The reason went to the cell, not to the row.
        self.assertIsNone(self._row(source_id)["reason"])
        with self.assertRaises(SourceRegistryError):
            update_source("IMX", source_id, cell="nowhere/at-all", mark="updated")
        with self.assertRaises(SourceRegistryError):
            update_source("IMX", source_id, cell="brief/business")

    def test_retired_source_cascades_to_every_document(self) -> None:
        source_id = self._sync_meeting()["source_id"]
        update_source("IMX", source_id, retire=True, reason="Superseded agreement, meeting cancelled")
        documents = {cell["document"] for cell in self._row(source_id)["impact"]}
        self.assertEqual(documents, set(routing_data()["documents"]))
        cascade = [cell for cell in self._row(source_id)["impact"] if cell["cascade"]]
        self.assertTrue(cascade and all(cell["section"] == "*" for cell in cascade))

    def test_authority_change_reroutes_untouched_cells(self) -> None:
        source_id = self._sync_meeting()["source_id"]
        _run(["sources", "IMX", "--id", source_id, "--authority", "api_contract"])
        row = self._row(source_id)
        self.assertEqual(row["authority"], "api_contract")
        self.assertEqual({cell["document"] for cell in row["impact"]}, {"specs", "gaps"})
        # Once a person has closed a cell the matrix is theirs; authority no longer reroutes it.
        update_source("IMX", source_id, cell="specs/contracts", mark="updated")
        update_source("IMX", source_id, authority="minutes")
        self.assertEqual({cell["document"] for cell in self._row(source_id)["impact"]}, {"specs", "gaps"})
        with self.assertRaises(SourceRegistryError):
            update_source("IMX", source_id, authority="boss")

    def test_precedence_between_rows(self) -> None:
        meeting_id = self._sync_meeting()["source_id"]
        result = _run(["sources", "IMX", "--precedence", "business", "--between", f"F-01,{meeting_id}"])
        self.assertEqual(result["winner"], meeting_id)
        self.assertEqual(result["rules"], ["P01"])
        tie = _run(["sources", "IMX", "--precedence", "api", "--between", f"F-01,{meeting_id}"])
        self.assertEqual(tie["status"], "unresolved")
        self.assertNotEqual(main(["sources", "IMX", "--precedence", "business"]), 0)

    def test_closing_report_by_recipient_and_ready_to_delete(self) -> None:
        source_id = self._sync_meeting()["source_id"]
        report = _run(["sources", "IMX", "--report"])
        text = Path(report["closing_report"]).read_text(encoding="utf-8")
        self.assertIn("## For the BA", text)
        self.assertIn(f"| {source_id} | ADDED | brief / business | pending |", text)
        not_ready = {item["source_id"]: item["missing"] for item in report["not_ready"]}
        self.assertIn("3 cell(s) pending", not_ready[source_id])
        for cell in ("brief/business", "requirements/functional", "gaps/open"):
            update_source("IMX", source_id, cell=cell, mark="updated")
        report = _run(["sources", "IMX", "--report"])
        self.assertIn(source_id, [item["source_id"] for item in report["ready_to_delete"]])
        # The report never deletes: the original is still there.
        self.assertTrue((self.ws / "07_changes" / "01_meetings" / "weekly.md").exists())
        self.assertNotEqual(main(["sources", "IMX", "--report", "--id", source_id]), 0)

    def test_closing_report_follows_project_language(self) -> None:
        state_path = self.ws / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["project_language"] = "es"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        self._sync_meeting()
        text = Path(_run(["sources", "IMX", "--report"])["closing_report"]).read_text(encoding="utf-8")
        self.assertIn("# Reporte de cierre - IMX", text)
        self.assertIn("## Para el BA", text)
        self.assertIn("celda(s) pendiente(s)", text)

    def test_an_example_never_closes_a_gap(self) -> None:
        gaps = parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))
        gap_id = gaps[0]["id"]
        block = (
            f"### {gap_id}\n"
            "- Answer: The operations team exports the monthly billing report to CSV every first business day.\n"
            "- Owner / source: Product Owner\n"
            "- Evidence or reference: Workshop\n"
            "- Decision status: confirmed\n"
        )
        example = self.temp / "answers-example.md"
        example.write_text(block, encoding="utf-8")
        result = _run(["resolve-gaps", "IMX", "--source", str(example)])
        self.assertNotIn(gap_id, result["closed"])
        after = {gap["id"]: gap for gap in parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))}
        self.assertEqual(after[gap_id]["status"], "ANSWERED")
        # The same answer from a governing source closes it.
        real = self.temp / "answers.md"
        real.write_text(block + "\n", encoding="utf-8")
        self.assertIn(gap_id, _run(["resolve-gaps", "IMX", "--source", str(real)])["closed"])


if __name__ == "__main__":
    unittest.main()
