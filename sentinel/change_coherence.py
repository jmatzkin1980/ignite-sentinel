"""IMP-410 (H27 inc 3): the lens view of a change and the deterministic checks of IMP-260 over it.

The project applies IMP-260 to `02_requirements/project-brief.md`; a change has no such brief of its
own, so its request, border and baseline facts are placed at the v2 places (`coherence_brief_inputs`),
rendered with the project's compiler and read by the same rules (`run_cross_checks(only=...)`).

Everything lives under `01_discovery/CHG-NNN/coherence/`: `view.md` and `checks.json` (this module),
`coherence.json` and `coherence.md` (the BA's confirmed reading, recorded in the registry).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .core.io import read_json, write_json, write_text
from .workspace import workspace_path

CHANGE_CROSS_CHECKS = ("roles_named_alike", "error_codes_have_text", "excluded_transitions_have_codes",
                       "rules_have_steps", "flags_in_parameters", "events_feed_metrics", "training_has_item")


def coherence_dir(base: Path, change_id: str) -> Path:
    return base / "01_discovery" / change_id / "coherence"


def coherence_ready(project_id: str, change_id: str) -> bool:
    """The lens view is worth reading once the border is settled and the cross-reads and new surfaces are decided."""
    from .changes import get_change
    from .crosses.state import cross_status
    from .crosses.surfaces import new_surface_candidates

    if get_change(project_id, change_id).get("round") == "scope":
        return False
    if cross_status(project_id, change_id)["missing"]:
        return False
    return all(item["decision"] is not None for item in new_surface_candidates(project_id, change_id))


def coherence_view(project_id: str, change_id: str) -> dict[str, Any]:
    """{text, fingerprint, unplaced}: the change seen by lenses and the hash of what it is made of."""
    from .compilers.brief_v2 import render_brief_v2
    from .compilers.change_deliverable import coherence_brief_inputs
    from .crosses.state import crosses_fingerprint

    inputs, unplaced = coherence_brief_inputs(project_id, change_id)
    text = render_brief_v2(inputs)[0]
    payload = json.dumps({"facts": inputs.place_facts, "crosses": crosses_fingerprint(project_id, change_id)},
                         sort_keys=True, ensure_ascii=False)
    return {"text": text, "fingerprint": hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16], "unplaced": unplaced}


def _checks_file(base: Path, change_id: str) -> dict[str, Any]:
    found = read_json(coherence_dir(base, change_id) / "checks.json", {})
    return found if isinstance(found, dict) else {}


def refresh_coherence(project_id: str, change_id: str) -> dict[str, Any] | None:
    """Write `view.md` and `checks.json` when what they come from changed; None while the change is not ready."""
    from .cross_checks import run_cross_checks

    if not coherence_ready(project_id, change_id):
        return None
    base = workspace_path(project_id)
    folder = coherence_dir(base, change_id)
    view = coherence_view(project_id, change_id)
    recorded = _checks_file(base, change_id)
    if recorded.get("fingerprint") != view["fingerprint"] or not (folder / "view.md").is_file():
        checks = run_cross_checks(view["text"], only=CHANGE_CROSS_CHECKS)
        write_text(folder / "view.md", view["text"])
        write_json(folder / "checks.json", {"fingerprint": view["fingerprint"], "checks": checks,
                                            "unplaced": view["unplaced"]})
        recorded = _checks_file(base, change_id)
    return {"view_path": (folder / "view.md").as_posix(), "fingerprint": view["fingerprint"],
            "checks": recorded.get("checks", []), "unplaced": recorded.get("unplaced", [])}


def coherence_state(project_id: str, change_id: str) -> dict[str, Any]:
    """missing (nothing recorded), stale (the change moved after it), done or waived."""
    base = workspace_path(project_id)
    folder = coherence_dir(base, change_id)
    current = coherence_view(project_id, change_id)["fingerprint"]
    checks_file = _checks_file(base, change_id)
    record = read_json(folder / "coherence.json", None)
    record = record if isinstance(record, dict) else None
    recorded = str((record or {}).get("fingerprint") or "")
    if record is None:
        state = "missing"
    elif recorded != current:
        state = "stale"
    else:
        state = "waived" if record.get("status") == "waived" else "done"
    results = checks_file.get("checks") or []
    counts = {"pass": 0, "warn": 0, "skip": 0}
    issues: list[str] = []
    for result in results:
        counts[str(result.get("status", "")).lower()] = counts.get(str(result.get("status", "")).lower(), 0) + 1
        issues.extend(str(i) for i in result.get("issues") or [])
    return {
        "state": state,
        "view_current": (folder / "view.md").is_file() and checks_file.get("fingerprint") == current,
        "fingerprint": current,
        "recorded_fingerprint": recorded,
        "checks": {**counts, "issues": issues},
    }
