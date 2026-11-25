"""IMP-416: the vertical slices of a change, functionality x delta, split by SPIDR above the size threshold.

Pure: no workspace reads. Every unit lands in exactly one slice and no slice exceeds ``max_units``.
The slice key is the story-id key (``cid|fun_key|delta|axis|n``): it does not change when a unit leaves
a slice that was not split again.
"""
from __future__ import annotations

from .slicing import slicing_decision_for_spec_unit

SPIDR_AXES = (
    "workflow_happy_path",
    "interface_ux_state",
    "data_external_dependency",
    "rules_regression",
    "quality_evidence_traceability",
)
DELTA_ORDER = ("ADDED", "MODIFIED", "REMOVED")


def _pattern(slicing_model: dict, pattern_id: str) -> dict:
    return next((p for p in slicing_model.get("patterns", []) if p.get("id") == pattern_id), {})


def _axis_of(unit: dict, slicing_model: dict) -> str:
    axis = slicing_decision_for_spec_unit(unit, slicing_model)["slicing_pattern_id"]
    return axis if axis in SPIDR_AXES else "workflow_happy_path"


def _dominant_axis(axes: list[str], slicing_model: dict) -> str:
    """The most frequent pattern among the units; a tie goes to the pattern with the lowest model priority."""
    def order(axis: str) -> tuple:
        return (-axes.count(axis), int(_pattern(slicing_model, axis).get("priority", 100)), axis)
    return sorted(set(axes), key=order)[0]


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[start:start + size] for start in range(0, len(items), size)]


def plan_change_slices(
    change_id: str,
    units: list[dict],
    funs: list[dict],
    unit_of: dict[str, str],
    max_units: int,
    slicing_model: dict,
) -> list[dict]:
    """Slices in order: functionality, delta (ADDED, MODIFIED, REMOVED), SPIDR axis, row order."""
    max_units = max(1, int(max_units))
    by_id = {str(unit.get("id", "")): unit for unit in units}
    slices: list[dict] = []
    for fun in funs:
        ordered = [unit_of[row] for row in fun.get("rows", []) if unit_of.get(row) in by_id]
        for delta in DELTA_ORDER:
            group = [uid for uid in ordered if str(by_id[uid].get("delta", "")) == delta]
            if not group:
                continue
            axes = {uid: _axis_of(by_id[uid], slicing_model) for uid in group}
            if len(group) <= max_units:
                parts = [("all", group, _dominant_axis([axes[uid] for uid in group], slicing_model))]
            else:
                parts = []
                for axis in SPIDR_AXES:
                    members = [uid for uid in group if axes[uid] == axis]
                    for chunk in _chunks(members, max_units):
                        parts.append((axis, chunk, axis))
            counters: dict[str, int] = {}
            for axis, members, pattern_id in parts:
                counters[axis] = counters.get(axis, 0) + 1
                pattern = _pattern(slicing_model, pattern_id)
                surfaces: list[str] = []
                for uid in members:
                    for name in by_id[uid].get("surfaces") or []:
                        if name not in surfaces:
                            surfaces.append(name)
                slices.append({
                    "key": f"{change_id}|{fun['key']}|{delta}|{axis}|{counters[axis]}",
                    "functionality": str(fun["id"]),
                    "fun_key": str(fun["key"]),
                    "name": str(fun.get("name") or fun.get("place") or fun["key"]),
                    "type": str(fun.get("type", "")),
                    "delta": delta,
                    "axis": axis,
                    "slicing": str(pattern.get("slicing", "")),
                    "rationale": str(pattern.get("rationale", "")),
                    "units": list(members),
                    "surfaces": surfaces,
                })
    return slices
