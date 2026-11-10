"""IMP-256: counterpart by proximity, the counterpart rows as data, the 16
cross-cutting scenarios and the 8 screen states in the brief v2, vague wording,
and the no-regression metric floor of the discovery evals."""

import sys
import unittest
from pathlib import Path

from sentinel.brief_model import parse_brief
from sentinel.compilers.brief_v2 import cross_cutting_data, render_brief_v2
from sentinel.discovery.workflow import counterpart_present, detect_gaps, human_title_for_gap, question_for_gap
from sentinel.lens_registry import load_lens_checks

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from test_brief_v2_compiler import inputs  # noqa: E402

CTP = [check for check in load_lens_checks() if check["id"].startswith("GAP-CTP-")]


def fired(text: str) -> set[str]:
    return {gap["id"] for gap in detect_gaps(text)}


class ProximityTests(unittest.TestCase):
    check = {"triggers": ["feature flag"], "counterparts": ["default"]}

    def test_counterpart_must_sit_near_the_mention(self):
        near = "we add a feature flag. its default is off."
        far = "we add a feature flag. users log in. reports are weekly. exports are csv. the default theme is dark."
        self.assertTrue(counterpart_present(near, near, self.check))
        self.assertFalse(counterpart_present(far, far, self.check))

    def test_context_folder_and_no_mention_keep_the_document_wide_test(self):
        source = "we add a feature flag. users log in. reports are weekly. exports are csv."
        self.assertTrue(counterpart_present(source + " default off per environment", source, self.check))
        self.assertTrue(counterpart_present("nothing named here. default is fine.", "nothing named here. default is fine.", self.check))
        self.assertTrue(counterpart_present("a feature flag. x. y. z. default.", "a feature flag. x. y. z. default.",
                                            {**self.check, "counterpart_scope": "document"}))


class CounterpartRowTests(unittest.TestCase):
    def test_fifteen_rows_with_their_own_text(self):
        self.assertEqual(len(CTP), 15)
        for check in CTP:
            with self.subTest(check=check["id"]):
                self.assertEqual(check["rule"], "mention_requires_counterpart")
                self.assertEqual(check["severity"], "medium")  # never blocks by itself
                for language in ("en", "es"):
                    for key in ("title", "question", "expected_format", "why", "example", "description"):
                        self.assertTrue(check["text"][language][key])

    def test_each_row_fires_on_its_mention_and_stays_quiet_with_its_counterpart(self):
        for check in CTP:
            trigger, counterpart = check["triggers"][0], check["counterparts"][0]
            with self.subTest(check=check["id"]):
                self.assertIn(check["id"], fired(f"The project includes {trigger} for the team."))
                self.assertNotIn(check["id"], fired(f"The project includes {trigger} for the team, {counterpart} agreed."))

    def test_lookups_read_the_row_text(self):
        self.assertEqual(human_title_for_gap("GAP-CTP-FLAG", "es"), "Contracara de flag")
        self.assertIn("idempotente", question_for_gap("GAP-CTP-WRITE-ENDPOINT", "es"))
        self.assertIn("runbook", question_for_gap("GAP-CTP-ALERT", "en"))


class VagueWordingTests(unittest.TestCase):
    def test_contracted_enumerations_and_modal_vagueness_are_smells(self):
        for sentence in ("Refunds need approval from a lead, a manager, etc.", "El reembolso debería aprobarlo un líder.",
                         "In general the queue is reviewed daily."):
            with self.subTest(sentence=sentence):
                self.assertIn("GAP-BUSINESS-RULE-WEAK-WORD-SMELL", fired(sentence))


class BriefScenarioTests(unittest.TestCase):
    def test_cross_cutting_index_refers_to_where_each_scenario_lives(self):
        text, report = render_brief_v2(inputs(profiles=["BAT"]))
        rows = [line for line in text.splitlines() if line.startswith("| T")]
        self.assertEqual(len(rows), 16)
        self.assertEqual(len(cross_cutting_data()["scenarios"]), 16)
        empty = next(row for row in rows if row.startswith("| T3 Empty"))
        self.assertIn("§4.1 › Screen states", empty)
        self.assertTrue(empty.endswith("| N/A there |"))  # BAT has no screens
        self.assertTrue(any(row.endswith("| pending there |") for row in rows))
        self.assertIn({"id": "3.6/cross_cutting", "fill": "covered_by_reference", "section": "3"}, report["places"])

    def test_scenario_is_specified_when_its_place_carries_a_fact(self):
        answers = [{"gap": "GAP-GOVERNANCE-CONSTRAINTS", "statement": "Every access is audited for 5 years.", "source": "F-02"}]
        text, _ = render_brief_v2(inputs(gap_answers=answers))
        audit = next(line for line in text.splitlines() if line.startswith("| T7 Audit"))
        self.assertTrue(audit.endswith("| specified |"), audit)

    def test_screen_states_pending_lists_the_eight_states(self):
        text, _ = render_brief_v2(inputs(language="es"))
        model = parse_brief(text)
        body = "\n".join(text.splitlines()[model.sections["4.1"].start:model.sections["4.1"].end])
        self.assertIn("estados: ideal; vacío de primer uso; sin resultados; cargando; parcial; error; "
                      "401 (y qué pasa con lo tipeado); 403 (vacío no es sin permiso; primer uso no es sin resultados)", body)


class MetricFloorTests(unittest.TestCase):
    def test_a_metric_below_its_floor_is_a_regression(self):
        sys.path.insert(0, str(ROOT / "evals"))
        import run_discovery_evals as evals

        summary = {"avg_gap_precision": 1.0, "avg_gap_recall": 0.8, "avg_gap_f1": 0.9, "avg_target_recall": 0.75,
                   "splits": {evals.TUNING_SPLIT: {"avg_gap_f1": 0.97}, evals.HELD_OUT_SPLIT: {"avg_gap_f1": 0.7}}}
        original = evals.METRIC_BASELINE
        try:
            floor = Path(self.id().replace(".", "_") + "_floor.json")
            floor.write_text('{"floor": {"avg_gap_recall": 0.845, "avg_gap_f1": 0.858}}', encoding="utf-8")
            evals.METRIC_BASELINE = floor
            self.assertEqual(evals.metric_regressions(summary), ["avg_gap_recall 0.800 < floor 0.845"])
        finally:
            evals.METRIC_BASELINE = original
            floor.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
