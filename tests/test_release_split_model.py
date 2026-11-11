"""IMP-264 (H17a): the release split model as data.

`sentinel/templates/release_split_model.json` holds the framework's release-split
knowledge (signals, cut criteria, patterns, flow, ordering, release types, release
INVEST and anti-patterns). The loader validates it with a stdlib validator
(IMP-103); `release_split_model.schema.json` is the documented contract and this
file is its drift guard. The model shares the enabler boundary with the backlog
slicing model by citing it, and activates the series fields of `brief_v2.json`.
"""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from sentinel import release_split_model as rsm
from sentinel.brief_schema import load_brief_schema
from sentinel.slicing_model import load_slicing_model

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "sentinel" / "schemas" / "release_split_model.schema.json"


def _model() -> dict:
    return copy.deepcopy(rsm.load_release_split_model())


class PackageModelTests(unittest.TestCase):
    def test_package_model_is_valid(self) -> None:
        self.assertEqual(rsm.validate_model(_model()), [])

    def test_counts_match_the_framework(self) -> None:
        model = _model()
        self.assertEqual(len(model["signals"]["split"]), 7)
        self.assertEqual(len(model["signals"]["no_split"]), 5)
        self.assertEqual([c["id"] for c in model["cut_criteria"]["items"]], [f"C{n}" for n in range(1, 15)])
        self.assertEqual([p["id"] for p in model["patterns"]["items"]], [f"P{n}" for n in range(1, 25)])
        self.assertEqual(len(model["flow"]["step_0"]["questions"]), 3)
        self.assertEqual([s["step"] for s in model["flow"]["steps"]], list(range(1, 13)))
        self.assertEqual([s["step"] for s in model["ordering"]["combination"]], [1, 2, 3, 4, 5])
        self.assertEqual(model["ordering"]["moscow"], {"must_max_share": 0.6, "could_target_share": 0.2})
        self.assertEqual({t["key"] for t in model["release_types"]["items"]}, rsm.RELEASE_TYPES)
        self.assertEqual(len(model["release_types"]["interleave_subtypes"]), 2)
        self.assertEqual([i["key"] for i in model["release_invest"]],
                         ["independent", "negotiable", "valuable", "estimable", "small", "testable"])

    def test_validated_anti_patterns_are_the_partition_checks(self) -> None:
        validated = {a["key"] for a in _model()["anti_patterns"] if a["validated"]}
        self.assertEqual(validated, rsm.VALIDATED_ANTI_PATTERNS)

    def test_relaxing_a_rule_is_never_for_legal_regulatory_or_must(self) -> None:
        p9 = next(p for p in _model()["patterns"]["items"] if p["id"] == "P9")
        self.assertTrue(p9["requires_restored_in"])
        self.assertTrue({"the rule is legal", "the rule is regulatory", "the rule is a Must"} <= set(p9["not_use_if"]))

    def test_spike_contract(self) -> None:
        spike = _model()["spike"]
        self.assertEqual((spike["questions_min"], spike["questions_max"]), (1, 3))
        self.assertTrue(spike["time_box_required"])
        self.assertEqual(spike["decision_record"], "DEC")


class EnablerBoundaryTests(unittest.TestCase):
    def test_boundary_is_cited_not_copied(self) -> None:
        model = _model()
        source = model["base_vs_enabler"]["boundary_source"]
        self.assertEqual((source["model"], source["field"]), ("slicing/backlog_slicing_model.json", "enabler_boundary"))
        text = json.dumps(model, ensure_ascii=False)
        for paragraph in load_slicing_model()["enabler_boundary"]["paragraphs"]:
            self.assertNotIn(paragraph[:60], text)

    def test_boundary_resolves_to_the_slicing_model(self) -> None:
        self.assertEqual(rsm.enabler_boundary(), load_slicing_model()["enabler_boundary"])

    def test_unknown_boundary_source_is_rejected(self) -> None:
        model = _model()
        model["base_vs_enabler"]["boundary_source"]["field"] = "nowhere"
        self.assertTrue(any("boundary" in p for p in rsm.validate_model(model)))


class SeriesFieldsTests(unittest.TestCase):
    def test_brief_v2_series_fields_are_active(self) -> None:
        block = load_brief_schema()["series_fields"]
        self.assertNotIn("series_reserved_fields", load_brief_schema())
        self.assertNotIn("reserved_until", block)
        self.assertEqual(block["active_since"], "H17a")
        self.assertEqual(block["model"], "release_split_model.json")

    def test_every_series_field_maps_to_a_model_section(self) -> None:
        model = _model()
        self.assertEqual(list(model["series_fields"]), load_brief_schema()["series_fields"]["fields"])
        for field, section in model["series_fields"].items():
            self.assertIn(section, model, field)


class RejectionTests(unittest.TestCase):
    def assertRejected(self, model: dict, needle: str) -> None:
        problems = rsm.validate_model(model)
        self.assertTrue(any(needle in p for p in problems), problems)
        with self.assertRaises(ValueError):
            rsm.load_release_split_model(override=model)

    def test_missing_pattern(self) -> None:
        model = _model()
        model["patterns"]["items"].pop()
        self.assertRejected(model, "patterns")

    def test_pattern_without_question(self) -> None:
        model = _model()
        model["patterns"]["items"][0]["question"] = ""
        self.assertRejected(model, "P1")

    def test_unknown_shape(self) -> None:
        model = _model()
        model["patterns"]["items"][1]["shape"] = "sideways"
        self.assertRejected(model, "shape")

    def test_flow_step_cites_unknown_pattern(self) -> None:
        model = _model()
        model["flow"]["steps"][0]["patterns"] = ["P99"]
        self.assertRejected(model, "P99")

    def test_missing_signal(self) -> None:
        model = _model()
        model["signals"]["no_split"].pop()
        self.assertRejected(model, "no_split")

    def test_moscow_above_sixty_percent(self) -> None:
        model = _model()
        model["ordering"]["moscow"]["must_max_share"] = 0.8
        self.assertRejected(model, "MoSCoW")

    def test_spike_with_four_questions(self) -> None:
        model = _model()
        model["spike"]["questions_max"] = 4
        self.assertRejected(model, "spike")

    def test_session_size_alone(self) -> None:
        model = _model()
        model["cut_criteria"]["items"][13].pop("never_alone")
        self.assertRejected(model, "C14")

    def test_relaxed_rule_allowed_for_legal(self) -> None:
        model = _model()
        next(p for p in model["patterns"]["items"] if p["id"] == "P9")["not_use_if"] = []
        self.assertRejected(model, "P9")

    def test_validated_anti_pattern_dropped(self) -> None:
        model = _model()
        model["anti_patterns"] = [a for a in model["anti_patterns"] if a["key"] != "layer_cut"]
        self.assertRejected(model, "layer_cut")

    def test_series_field_maps_to_unknown_section(self) -> None:
        model = _model()
        model["series_fields"]["depends_on"] = "nowhere"
        self.assertRejected(model, "depends_on")


class SchemaDriftGuard(unittest.TestCase):
    """release_split_model.schema.json against the validator."""

    def setUp(self) -> None:
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_required_sections(self) -> None:
        self.assertEqual(set(self.schema["required"]), rsm.REQUIRED_SECTIONS)

    def test_enums(self) -> None:
        props = self.schema["properties"]
        pattern = props["patterns"]["properties"]["items"]["items"]["properties"]
        self.assertEqual(set(pattern["shape"]["enum"]), rsm.VALID_SHAPES)
        types = props["release_types"]["properties"]["items"]["items"]["properties"]["key"]["enum"]
        self.assertEqual(set(types), rsm.RELEASE_TYPES)

    def test_pattern_required_fields(self) -> None:
        pattern = self.schema["properties"]["patterns"]["properties"]["items"]["items"]
        self.assertEqual(set(pattern["required"]), rsm.PATTERN_FIELDS)


if __name__ == "__main__":
    unittest.main()
