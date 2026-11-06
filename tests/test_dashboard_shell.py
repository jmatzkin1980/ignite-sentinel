"""IMP-239: /dashboard on the model -> validate -> render pipeline, common shell.

The model is reproducible (no clock, no absolute paths) and declares its
provenance: the cut-off date is the newest mtime among the sources read and
every state.json is fingerprinted with a 12-char sha256.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import unittest
from datetime import datetime, timezone

from sentinel.dashboard import DashboardModelError, collect_dashboard_model, validate_dashboard_model
from tests.test_dashboard import DashboardFixtureMixin

FIXED_EPOCH = 1_781_481_600  # 2026-06-15T00:00:00Z


def pin_mtimes(root, epoch: int = FIXED_EPOCH) -> None:
    for folder, _dirs, files in os.walk(root / "workspaces"):
        for name in files:
            os.utime(os.path.join(folder, name), (epoch, epoch))


class DashboardProvenanceTests(DashboardFixtureMixin, unittest.TestCase):
    def test_model_has_no_clock_or_absolute_root(self) -> None:
        model = collect_dashboard_model(self.temp)
        self.assertNotIn("generated_at", model)
        self.assertNotIn("root", model)
        self.assertNotIn(str(self.temp), json.dumps(model, ensure_ascii=False))

    def test_cutoff_is_newest_source_mtime(self) -> None:
        pin_mtimes(self.temp)
        newer = FIXED_EPOCH + 3600
        gaps = self.temp / "workspaces" / "DASH_CLIENT_WAIT" / "01_discovery" / "gaps.md"
        os.utime(gaps, (newer, newer))
        model = collect_dashboard_model(self.temp)
        expected = datetime.fromtimestamp(newer, timezone.utc).isoformat()
        self.assertEqual(model["provenance"]["cutoff"], expected)

    def test_every_state_json_is_fingerprinted(self) -> None:
        model = collect_dashboard_model(self.temp)
        sources = {item["path"]: item["sha256"] for item in model["provenance"]["sources"]}
        for project_id in ("DASH_BACKLOG_READY", "DASH_CLIENT_WAIT"):
            path = f"workspaces/{project_id}/state.json"
            digest = hashlib.sha256((self.temp / path).read_bytes()).hexdigest()[:12]
            self.assertEqual(sources[path], digest)

    def test_two_collections_are_identical(self) -> None:
        pin_mtimes(self.temp)
        first = json.dumps(collect_dashboard_model(self.temp), sort_keys=True)
        second = json.dumps(collect_dashboard_model(self.temp), sort_keys=True)
        self.assertEqual(first, second)

    def test_empty_portfolio_has_empty_provenance(self) -> None:
        model = collect_dashboard_model(self.temp / "nowhere")
        self.assertEqual(model["provenance"], {"cutoff": "", "sources": []})


class DashboardValidationTests(DashboardFixtureMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.model = collect_dashboard_model(self.temp)

    def test_collected_model_is_valid(self) -> None:
        self.assertEqual(validate_dashboard_model(self.model), [])

    def _errors(self, mutate) -> list[str]:
        model = copy.deepcopy(self.model)
        mutate(model)
        return validate_dashboard_model(model)

    def test_duplicate_workspace_ids(self) -> None:
        errors = self._errors(lambda m: m["workspaces"].append(copy.deepcopy(m["workspaces"][0])))
        self.assertTrue(any("duplicate workspace" in e for e in errors), errors)

    def test_duplicate_gap_ids(self) -> None:
        def mutate(m):
            ws = next(w for w in m["workspaces"] if w["gaps_detail"])
            ws["gaps_detail"].append(copy.deepcopy(ws["gaps_detail"][0]))

        errors = self._errors(mutate)
        self.assertTrue(any("duplicate gap" in e for e in errors), errors)

    def test_hand_written_kpi_is_rejected(self) -> None:
        errors = self._errors(lambda m: m["kpis"].__setitem__("blocking_gaps", 99))
        self.assertTrue(any("kpis.blocking_gaps" in e for e in errors), errors)

    def test_summary_open_gaps_must_match_counts(self) -> None:
        errors = self._errors(lambda m: m["workspaces"][0]["summary"].__setitem__("Gaps abiertos", 42))
        self.assertTrue(any("Gaps abiertos" in e for e in errors), errors)

    def test_missing_fingerprint_is_rejected(self) -> None:
        errors = self._errors(lambda m: m["provenance"]["sources"].pop())
        self.assertTrue(any("provenance" in e for e in errors), errors)

    def test_error_type_is_value_error(self) -> None:
        self.assertTrue(issubclass(DashboardModelError, ValueError))


if __name__ == "__main__":
    unittest.main()
