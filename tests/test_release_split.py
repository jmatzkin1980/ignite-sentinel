"""IMP-266 (H17a): deterministic validation of the partition, and /split --confirm.

The graph with contracts as nodes, symmetric edges, cycles as a missing contract,
waves, n-of-n coverage, single owner, frozen contracts with audited deltas, relaxed
rules, the validated anti-patterns, pending with tentacles (two signals) and the
integrator's premise. `/split --confirm` requires all of it green and records who
confirms; the client's confirmation opens a gap.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.release_split import (
    CLIENT_GAP_ID, CONTRACT_KINDS, PARTITION_CODES, UMBRAL_TRANSVERSAL, contract_hash, validate_partition,
)
from sentinel.split_proposal import FINDING_CODES

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "evals"))
FIXTURES = ROOT / "fixtures" / "evals" / "partition"
SCHEMA = ROOT.parent / "sentinel" / "schemas" / "release_split_proposal.schema.json"
SKILL = ROOT.parent / ".codex" / "skills" / "sentinel-release-split" / "SKILL.md"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


VALID = fixture("valid-partition")


def check(payload: dict, frozen: dict | None = None) -> dict:
    return validate_partition(VALID["brief"], payload, set(VALID["open_gaps"]), frozen or {})


def codes(payload: dict, frozen: dict | None = None) -> set[str]:
    return {f["code"] for f in check(payload, frozen)["findings"]}


def release(payload: dict, rid: str) -> dict:
    return next(r for r in payload["releases"] if r["id"] == rid)


class EvalTests(unittest.TestCase):
    def test_every_seeded_case_matches(self) -> None:
        import run_partition_evals

        result = run_partition_evals.run()
        self.assertGreaterEqual(len(result["cases"]), 12)
        self.assertEqual({c["split"] for c in result["cases"]}, {"tuning", "held_out"})
        for case in result["cases"]:
            with self.subTest(case=case["case"]):
                self.assertTrue(case["ok"], case)

    def test_fixtures_are_labelled_synthetic(self) -> None:
        for path in FIXTURES.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(data.get("synthetic"), path.name)
            self.assertIn("synthetic fixture", data["brief"])

    def test_every_code_is_declared(self) -> None:
        for path in FIXTURES.glob("*.json"):
            for code in json.loads(path.read_text(encoding="utf-8"))["expected"]:
                self.assertIn(code, set(PARTITION_CODES) | set(FINDING_CODES))


class PartitionTests(unittest.TestCase):
    def test_valid_partition_reports_waves_and_coverage(self) -> None:
        result = check(VALID["payload"])
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["waves"], {"0": ["r0"], "1": ["r1"], "2": ["r2"], "3": ["r3"]})
        self.assertEqual(result["coverage"], {"scope_6_1": {"covered": 3, "total": 3},
                                              "build_items": {"covered": 4, "total": 4},
                                              "screens": {"covered": 1, "total": 1}})
        self.assertEqual(set(result["contracts"]), {"K1", "K2", "K3"})

    def test_cycle_is_a_missing_contract_with_its_path(self) -> None:
        result = check(fixture("cycle")["payload"])
        finding = next(f for f in result["findings"] if f["code"] == "missing_contract")
        self.assertEqual(finding["where"], "r1 → r2 → r1")
        self.assertEqual(result["waves"], {})

    def test_proposal_findings_are_included(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        release(payload, "r2")["contains"] = []
        self.assertIn("empty_release", codes(payload))

    def test_transversal_readiness_is_a_signal_not_a_finding(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        release(payload, "r1")["needs"] = ["GAP-PAY-01"]
        release(payload, "r2")["needs"] = ["GAP-PAY-01"]
        release(payload, "r3")["needs"] = ["GAP-BRIEF-S5", "GAP-PAY-01"]
        result = check(payload)
        self.assertEqual(result["findings"], [])
        self.assertEqual([s["gap"] for s in result["signals"]], ["GAP-PAY-01"])
        self.assertGreaterEqual(result["signals"][0]["share"], UMBRAL_TRANSVERSAL)

    def test_anti_patterns_are_reported_by_key(self) -> None:
        result = check(fixture("held-enabler-demo-and-outcome")["payload"])
        self.assertEqual(set(result["anti_patterns"]), {"enabler_without_demo", "release_without_outcome_metric"})

    def test_operation_without_consumer(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        payload["contracts"][0]["operations"].append({"name": "audit", "consumers": []})
        self.assertIn("operation_without_consumer", codes(payload))

    def test_extension_with_cross_note_and_merge_order_passes(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        payload["contracts"][1].update(extended_by=["r2", "r3"], cross_note="r2 adds the decision, r3 the payment",
                                       merge_order=["r2", "r3"])
        self.assertEqual(codes(payload), set())

    def test_relaxed_rule_restored_later_passes(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        payload["relaxed_rules"] = [{"rule": "attachments are optional in the first cut",
                                     "anchor": {"place": "3.2", "quote": "files a claim with attachments"},
                                     "release": "r1", "restored_in": "r2"}]
        self.assertEqual(codes(payload), set())
        payload["relaxed_rules"][0]["kind"] = "regulatory"
        self.assertEqual(codes(payload), {"relaxed_forbidden"})

    def test_contract_hash_ignores_consumers(self) -> None:
        contract = copy.deepcopy(VALID["payload"]["contracts"][0])
        before = contract_hash(contract)
        contract["operations"][0]["consumers"] = ["r1"]
        self.assertEqual(contract_hash(contract), before)
        contract["definition"] = "changed"
        self.assertNotEqual(contract_hash(contract), before)

    def test_audited_delta_is_returned(self) -> None:
        data = fixture("held-frozen-with-delta")
        result = check(data["payload"], data["frozen"])
        self.assertEqual(result["findings"], [])
        self.assertEqual([d["contract"] for d in result["deltas"]], ["K2"])


class SchemaDriftGuard(unittest.TestCase):
    def test_partition_fields(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        contract = schema["properties"]["contracts"]["items"]
        self.assertEqual(set(contract["properties"]["kind"]["enum"]), set(CONTRACT_KINDS))
        self.assertEqual(set(contract["required"]), {"id", "name", "kind", "created_by", "definition"})
        self.assertEqual(set(schema["properties"]["relaxed_rules"]["items"]["required"]),
                         {"rule", "anchor", "release", "restored_in"})
        self.assertIn("consumes", schema["$defs"]["edge"]["properties"])
        self.assertIn("contains", schema["properties"]["sketches"]["items"]["properties"])


class SurfaceTests(unittest.TestCase):
    def test_mcp_modes_and_skill(self) -> None:
        from sentinel.mcp import SPLIT_MODES

        self.assertEqual(SPLIT_MODES, ("assess", "propose", "confirm"))
        text = SKILL.read_text(encoding="utf-8-sig")
        for anchor in ("/split PROJECT_ID --confirm", "contracts", "restored_in", "UMBRAL_TRANSVERSAL"):
            self.assertIn(anchor, text)


class ConfirmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["init", "P"]), 0)
        self.base = Path("workspaces") / "P"
        self.brief = self.base / "02_requirements" / "project-brief.md"
        self.brief.parent.mkdir(parents=True, exist_ok=True)
        self.brief.write_text(VALID["brief"], encoding="utf-8")
        from sentinel.discovery import render_gaps

        rows = [{"id": g, "lens": "business", "severity": "high", "status": "OPEN", "description": "synthetic gap",
                 "question": "Which?", "evidence_mention": "§6.1", "origin": "agent", "resolution_note": ""}
                for g in VALID["open_gaps"]]
        self.gaps = self.base / "01_discovery" / "gaps.md"
        self.gaps.parent.mkdir(parents=True, exist_ok=True)
        self.gaps.write_text(render_gaps("P", rows, "REQ-001", "en"), encoding="utf-8")
        self.partition = self.base / "02_requirements" / "series" / "partition.json"

    def tearDown(self) -> None:
        os.chdir(self.old)
        self.tmp.cleanup()

    def cli(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = main(["split", "P", *args])
        return code, out.getvalue()

    def propose(self, payload: dict) -> tuple[int, str]:
        Path("proposal.json").write_text(json.dumps(payload), encoding="utf-8")
        return self.cli("--propose", "--source", "proposal.json")

    def test_confirm_needs_a_proposal_and_both_confirmers(self) -> None:
        code, out = self.cli("--confirm", "--ba", "Ana", "--tech", "Core team")
        self.assertNotEqual(code, 0)
        self.assertIn("--propose first", out)
        self.assertEqual(self.propose(VALID["payload"])[0], 0)
        code, out = self.cli("--confirm", "--ba", "Ana")
        self.assertNotEqual(code, 0)
        self.assertIn("--tech", out)
        self.assertFalse(self.partition.exists())

    def test_propose_previews_the_partition(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        release(payload, "r1").pop("enables")
        code, out = self.propose(payload)
        self.assertEqual(code, 0, out)
        self.assertIn('"asymmetric_edge"', out)

    def test_confirm_refuses_a_partition_that_is_not_green(self) -> None:
        payload = copy.deepcopy(VALID["payload"])
        release(payload, "r1").pop("enables")
        self.assertEqual(self.propose(payload)[0], 0)
        code, out = self.cli("--confirm", "--ba", "Ana", "--tech", "Core team")
        self.assertNotEqual(code, 0)
        self.assertIn("asymmetric_edge", out)
        self.assertFalse(self.partition.exists())

    def test_confirm_records_who_freezes_contracts_and_opens_the_client_gap(self) -> None:
        self.assertEqual(self.propose(VALID["payload"])[0], 0)
        code, out = self.cli("--confirm", "--ba", "Ana", "--tech", "Core team")
        self.assertEqual(code, 0, out)
        stored = json.loads(self.partition.read_text(encoding="utf-8"))
        self.assertEqual(stored["status"], "confirmed")
        self.assertEqual(stored["confirmed_by"], {"ba": "Ana", "technical_team": "Core team"})
        self.assertEqual(stored["client_confirmation"], {"status": "pending", "gap": CLIENT_GAP_ID})
        self.assertEqual(set(stored["contracts_frozen"]), {"K1", "K2", "K3"})
        self.assertIn(CLIENT_GAP_ID, self.gaps.read_text(encoding="utf-8"))
        first = self.partition.read_bytes()
        self.assertEqual(self.cli("--confirm", "--ba", "Ana", "--tech", "Core team")[0], 0)
        self.assertEqual(self.partition.read_bytes(), first)  # two runs, identical
        from sentinel.discovery import parse_gap_rows

        rows = parse_gap_rows(self.gaps.read_text(encoding="utf-8"))
        self.assertEqual(sum(1 for r in rows if r.get("id", "").strip("`") == CLIENT_GAP_ID), 1)  # opened once

    def test_a_frozen_contract_changes_only_with_an_audited_delta(self) -> None:
        self.assertEqual(self.propose(VALID["payload"])[0], 0)
        self.assertEqual(self.cli("--confirm", "--ba", "Ana", "--tech", "Core team")[0], 0)
        payload = copy.deepcopy(VALID["payload"])
        payload["contracts"][1]["definition"] = "claim id, policy, incident data, status, channel"
        self.assertEqual(self.propose(payload)[0], 0)
        code, out = self.cli("--confirm", "--ba", "Ana", "--tech", "Core team")
        self.assertNotEqual(code, 0)
        self.assertIn("contract_changed_without_delta", out)
        payload["contract_deltas"] = [{"contract": "K2", "why": "the integrator needs the channel", "finding": "F-02"}]
        self.assertEqual(self.propose(payload)[0], 0)
        code, out = self.cli("--confirm", "--ba", "Ana", "--tech", "Core team")
        self.assertEqual(code, 0, out)
        stored = json.loads(self.partition.read_text(encoding="utf-8"))
        self.assertEqual([d["contract"] for d in stored["contract_deltas"]], ["K2"])

    def test_confirm_refuses_when_the_brief_changed(self) -> None:
        self.assertEqual(self.propose(VALID["payload"])[0], 0)
        self.brief.write_text(VALID["brief"] + "\n", encoding="utf-8")
        code, out = self.cli("--confirm", "--ba", "Ana", "--tech", "Core team")
        self.assertNotEqual(code, 0)
        self.assertIn("--propose again", out)


if __name__ == "__main__":
    unittest.main()
