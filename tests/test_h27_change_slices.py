"""IMP-416 (H27 inc 5b): vertical slices of a change (functionality x delta, SPIDR above the size threshold)."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from sentinel.compilers import slicing
from sentinel.compilers.change_slices import SPIDR_AXES, plan_change_slices
from sentinel.compilers.slicing import (
    acceptance_criteria_for_slice_story,
    acceptance_criteria_for_spec_unit_story,
    build_slice_story_specs,
)
from sentinel.slicing_model import load_slicing_model

CID = "CHG-001"
SURFACE = "Tabla de proveedores"


def make_units(spec: list[tuple[str, str]]) -> list[dict]:
    """spec: (delta, text) per unit; ids SPEC-U-001..., one EARS row each."""
    units = []
    for n, (delta, text) in enumerate(spec, 1):
        units.append({
            "id": f"SPEC-U-{n:03d}", "change": CID, "delta": delta,
            "statement": f"Cuando el comprador {text}, el sistema debe guardar el cambio {n}.",
            "ears": [f"REQ-EARS-{n:03d}"], "surfaces": [SURFACE],
        })
    return units


def make_fun(units: list[dict]) -> dict:
    return {"id": "FUN-01", "key": "tabla:tabla de proveedores", "type": "tabla", "name": SURFACE,
            "rows": [u["ears"][0] for u in units]}


def plan(units: list[dict], max_units: int = 5) -> list[dict]:
    unit_of = {u["ears"][0]: u["id"] for u in units}
    return plan_change_slices(CID, units, [make_fun(units)], unit_of, max_units, load_slicing_model())


NEUTRAL = "registra el proveedor"
SCREEN = "abre la pantalla del proveedor"


class Planning(unittest.TestCase):
    def test_small_group_is_one_slice(self):
        units = make_units([("ADDED", NEUTRAL)] * 4)
        slices = plan(units)
        self.assertEqual(len(slices), 1)
        self.assertEqual(slices[0]["axis"], "all")
        self.assertEqual(slices[0]["units"], [u["id"] for u in units])
        self.assertEqual(slices[0]["functionality"], "FUN-01")
        self.assertEqual(slices[0]["delta"], "ADDED")
        self.assertEqual(slices[0]["surfaces"], [SURFACE])

    def test_splits_by_delta(self):
        units = make_units([("MODIFIED", NEUTRAL), ("ADDED", NEUTRAL), ("ADDED", NEUTRAL)])
        slices = plan(units)
        self.assertEqual([s["delta"] for s in slices], ["ADDED", "MODIFIED"])
        self.assertEqual(slices[0]["units"], ["SPEC-U-002", "SPEC-U-003"])
        self.assertEqual(slices[1]["units"], ["SPEC-U-001"])

    def test_spidr_split_above_threshold(self):
        units = make_units([("ADDED", NEUTRAL), ("ADDED", SCREEN), ("ADDED", NEUTRAL), ("ADDED", SCREEN),
                            ("ADDED", NEUTRAL), ("ADDED", SCREEN), ("ADDED", NEUTRAL)])
        slices = plan(units)
        self.assertEqual([s["axis"] for s in slices], ["workflow_happy_path", "interface_ux_state"])
        self.assertEqual([len(s["units"]) for s in slices], [4, 3])
        self.assertEqual(slices[1]["slicing"], "Interface / UX State")
        self.assertIn(slices[0]["axis"], SPIDR_AXES)
        many = make_units([("ADDED", NEUTRAL)] * 12)
        parts = plan(many)
        self.assertEqual([len(s["units"]) for s in parts], [5, 5, 2])
        self.assertEqual({s["axis"] for s in parts}, {"workflow_happy_path"})
        self.assertEqual([u for s in parts for u in s["units"]], [u["id"] for u in many])
        self.assertEqual(len({s["key"] for s in parts}), 3)

    def test_slices_cover_each_unit_once(self):
        cases = [
            make_units([("ADDED", NEUTRAL)] * 4),
            make_units([("ADDED", NEUTRAL), ("ADDED", SCREEN)] * 3 + [("ADDED", NEUTRAL)]),
            make_units([("ADDED", NEUTRAL)] * 12),
            make_units([("ADDED", NEUTRAL), ("MODIFIED", SCREEN), ("REMOVED", NEUTRAL)] * 3),
        ]
        for units in cases:
            for size in (2, 5):
                slices = plan(units, size)
                flat = [u for s in slices for u in s["units"]]
                self.assertEqual(sorted(flat), sorted(u["id"] for u in units))
                self.assertEqual(len(flat), len(set(flat)))
                self.assertTrue(all(0 < len(s["units"]) <= size for s in slices))

    def test_slice_keys_stable(self):
        units = make_units([("ADDED", NEUTRAL)] * 4)
        first = plan(units)
        self.assertEqual([s["key"] for s in first], [s["key"] for s in plan(units)])
        del units[1]
        after = plan(units)
        self.assertEqual(first[0]["key"], after[0]["key"])
        self.assertEqual(after[0]["units"], ["SPEC-U-001", "SPEC-U-003", "SPEC-U-004"])


class Criteria(unittest.TestCase):
    PRESERVED = [{"id": "REQ-EARS-009", "statement": "Cuando el comprador consulta el alta, el sistema debe mostrarla."}]

    def test_slice_story_criteria(self):
        units = make_units([("ADDED", NEUTRAL)] * 3)
        criteria = acceptance_criteria_for_slice_story("US-050", units, CID, self.PRESERVED, "es")
        self.assertEqual([c["id"] for c in criteria], [f"AC-050-{n:02d}" for n in range(1, 9)])
        self.assertEqual([c["name"] for c in criteria], [
            "Spec Unit Happy Path", "Spec Unit Happy Path", "Spec Unit Happy Path",
            "Spec Unit Validation Path", "Failure And Recovery Path", "Regression Path",
            "Quality Evidence Path", "Preserved Behavior"])
        self.assertEqual([c["classification"] for c in criteria], [
            "fail-to-pass", "fail-to-pass", "fail-to-pass", "fail-to-pass", "fail-to-pass",
            "pass-to-pass", "evidence", "pass-to-pass"])
        self.assertIn("SPEC-U-002", criteria[1]["given"])
        self.assertIn("SPEC-U-001, SPEC-U-002, SPEC-U-003", criteria[3]["given"])
        self.assertIn(CID, criteria[6]["then"])
        self.assertNotIn("REQ-001", criteria[6]["then"])
        self.assertIn("REQ-EARS-009", criteria[7]["then"])

    def test_project_criteria_unchanged(self):
        unit = {"id": "SPEC-U-001", "change": CID, "ears": ["REQ-EARS-001"], "preserved": self.PRESERVED}
        criteria = acceptance_criteria_for_spec_unit_story(
            "US-001", unit, "Cuando el comprador registra el proveedor, el sistema debe guardarlo.", "es")
        self.assertEqual([c["id"] for c in criteria], [f"AC-001-{n:02d}" for n in range(1, 7)])
        self.assertEqual(criteria[4]["classification"], "evidence")
        self.assertIn(f", {CID}", criteria[4]["then"])
        self.assertEqual(criteria[5]["name"], "Preserved Behavior")
        self.assertEqual(criteria[5]["classification"], "pass-to-pass")
        self.assertEqual(criteria[5]["given"], f"el cambio {CID} está aplicado")
        self.assertEqual(
            criteria[5]["then"],
            "el comportamiento preservado sigue igual: Cuando el comprador consulta el alta, "
            "el sistema debe mostrarla (REQ-EARS-009)")
        project = acceptance_criteria_for_spec_unit_story(
            "US-001", {"id": "SPEC-U-001", "ears": ["REQ-001"]}, "Cuando X, el sistema debe Y.", "es")
        self.assertEqual(len(project), 5)
        self.assertIn("REQ-001, PRD-001, SPEC-001", project[4]["then"])


class SliceStories(unittest.TestCase):
    def test_slice_story_fields(self):
        units = make_units([("ADDED", NEUTRAL), ("ADDED", NEUTRAL)])
        slices = plan(units)
        key = slices[0]["key"]
        calls: list[str] = []

        def fake_context(project_id, story_id, unit, backlog_context):
            calls.append(story_id)
            return {"story_id": story_id, "sections": {}}

        with patch.object(slicing, "build_story_backlog_context", fake_context):
            specs = build_slice_story_specs(
                "PRJ", {"sections": {}}, "es", slices, {u["id"]: u for u in units}, {key: "US-007"}, [])
        self.assertEqual(calls, ["US-007"])
        self.assertEqual(len(specs), 1)
        story = specs[0]
        self.assertEqual(story["id"], "US-007")
        self.assertEqual(story["type"], "value_story")
        self.assertEqual(story["source_units"], ["SPEC-U-001", "SPEC-U-002"])
        self.assertEqual(story["source_unit"], "SPEC-U-001")
        self.assertEqual(story["fr"], "FUN-01")
        self.assertTrue(story["title"].startswith("Tabla de proveedores: "))
        self.assertTrue(story["title"].endswith(" (+1)"))
        self.assertEqual(story["jtbd"], "REQ-EARS-001, REQ-EARS-002")
        for expected in ("SPEC-U-001", "SPEC-U-002", "REQ-EARS-001", "REQ-EARS-002", CID):
            self.assertIn(expected, story["trace"])
        self.assertEqual(story["trace"], sorted(story["trace"]))
        self.assertEqual(story["change"], CID)
        self.assertEqual(story["delta"], "ADDED")
        self.assertEqual(story["surfaces"], [SURFACE])
        self.assertEqual(story["context_pack_section"], "per_story.US-007")
        self.assertEqual((story["dependencies"], story["enables"]), ([], []))
        self.assertIn("execution_contract", story)
        self.assertTrue(story["slicing_rationale"].startswith("FUN-01: 2 unidad(es) de Tabla de proveedores; "))
        self.assertEqual(len(story["acceptance"]), 2 + 4)


if __name__ == "__main__":
    unittest.main()
