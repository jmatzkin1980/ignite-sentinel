from __future__ import annotations

from ..errors import InputError  # IMP-302: typed errors

import shutil
from pathlib import Path
from typing import Any

from ..core.markdown import parse_frontmatter, table_cell
from ..core.graph import add_edge, add_node, nodes_by_type
from ..core.io import read_json, write_json, write_text
from ..core.text import unique_path
from ..memory import ContextBroker
from ..payload_hygiene import archive_payload, sanitize_payload, shield_quote
from ..workspace import state_path, update_state, workspace_path


class BacklogRefinementError(InputError):
    """Raised when no backlog refinement proposal can be accepted."""


VALID_KINDS = {"reslice", "split-story", "merge-stories", "missing-story", "enabler-candidate"}
LOOSE_ENABLER_MARKERS = (
    "internal tool accessible",
    "herramienta interna accesible",
    "environment available",
    "ambiente disponible",
    "generic setup",
    "setup generico",
)


CHANGE_TEXT = {
    "es": {"no_backlog": "{cid} todavía no tiene backlog para refinar"},
    "en": {"no_backlog": "{cid} has no backlog to refine yet"},
}


def _refinement_dir(base: Path, change_id: str | None) -> Path:
    return base / "04_backlog" / change_id / "refinements" if change_id else base / "04_backlog" / "refinements"


def apply_backlog_refinement(project_id: str, source: Path, change_id: str | None = None) -> dict[str, object]:
    """The project's refinement, or (IMP-433) the one of a change: its epic, stories and units, its folder and its state."""
    base = workspace_path(project_id)
    if change_id:
        from ..changes import change_language, get_change
        from ..compilers.change_backlog import change_unit_texts, epic_id_for
        from ..errors import GateRefusal

        change = get_change(project_id, change_id)
        epic_path = base / "04_backlog" / f"{epic_id_for(change_id)}.md"
        if not epic_path.exists():
            language = "en" if change_language(project_id, change) == "en" else "es"
            raise GateRefusal(CHANGE_TEXT[language]["no_backlog"].format(cid=change_id),
                              next_step=f"/backlog {project_id} --change {change_id}")
        # IMP-433 review I1: the change's own gate stands in for the project's DIRTY one: a backlog behind its units (specs
        # regenerated since) is refused like `/quality --change`, before anything is written.
        from ..quality import refuse_change_backlog_behind

        refuse_change_backlog_behind(project_id, change_id)
    else:
        epic_path = base / "04_backlog" / "EPIC-001.md"
        if not epic_path.exists():
            raise BacklogRefinementError("Cannot refine backlog before /backlog creates 04_backlog/EPIC-001.md.", gate=True)
    if not source.exists():
        raise BacklogRefinementError(f"Backlog refinement source not found: {source}")

    data = read_json(source, {})
    if not isinstance(data, dict):
        raise BacklogRefinementError("Backlog refinement source must be a JSON object with a non-empty proposals array.")
    if change_id:
        evidence_text = change_refinement_evidence_text(project_id, change_id)
        story_index = load_story_index(base, change_id)
        spec_units = change_unit_texts(project_id, change_id)
    else:
        evidence_text = backlog_refinement_evidence_text(base)
        story_index = load_story_index(base)
        spec_units = load_spec_unit_index(base)
    accepted, rejected = validate_refinement_proposals(data, evidence_text, story_index, spec_units)
    # IMP-342: validated as written; stored and rendered redacted and neutralized
    accepted = sanitize_payload(base, accepted)
    rejected = sanitize_payload(base, rejected, verbatim_keys=("reason",))  # runtime prose: redacted only
    if not accepted:
        # IMP-323: refuse before touching the backlog, the payload archive, state or the graph;
        # only the report of why each proposal was refused is written.
        from ..prd import rejection_summary

        write_refinement_report(project_id, accepted, rejected, source, change_id)
        raise BacklogRefinementError(
            "No backlog refinement proposals were accepted: " + rejection_summary(rejected)
            + " Details in " + _refinement_dir(base, change_id).relative_to(base).as_posix() + "/refinement_report.md."
        )

    refinement_dir = _refinement_dir(base, change_id)
    refinement_dir.mkdir(parents=True, exist_ok=True)
    archived = unique_path(refinement_dir / source.name)
    archive_payload(base, source, archived)

    accepted_path = refinement_dir / "accepted_refinements.json"
    existing = read_json(accepted_path, [])
    existing_refinements = existing if isinstance(existing, list) else []
    merged, unchanged = merge_refinements(existing_refinements, accepted)
    write_json(accepted_path, merged)
    render_backlog_refinements(base, merged, epic_path if change_id else None, set(story_index))
    report_path = write_refinement_report(project_id, accepted, rejected, archived, change_id)

    refinement_id = add_node(
        project_id,
        "CHG",
        "backlog_refinement",
        report_path,
        f"Backlog refinement from {source.name}",
        domain="product",
    )
    for epic in nodes_by_type(project_id, "epic"):
        if Path(str(epic.get("path", ""))).name == epic_path.name:  # IMP-433: from the epic of the scope, not from every epic
            add_edge(project_id, epic["id"], refinement_id, "refined_by")
    for proposal in accepted:
        for story_id in proposal.get("target_stories", []):
            add_edge(project_id, refinement_id, str(story_id), "proposes_refinement_for")
        for unit_id in proposal.get("source_units", []):
            add_edge(project_id, str(unit_id), refinement_id, "grounds_refinement")
    ContextBroker(project_id).index_artifact(
        refinement_id,
        "backlog_refinement",
        report_path,
        report_path.read_text(encoding="utf-8"),
        domain="product",
        trace_ids=[refinement_id, *[item["id"] for item in accepted]],
    )
    if change_id:
        changes = read_json(state_path(project_id), {}).get("changes", {})
        changes[change_id]["refinements"] = {"count": len(merged), "last_id": refinement_id, "last_source": str(archived.as_posix())}
        update_state(project_id, changes=changes)
    else:
        update_state(
            project_id,
            backlog_refinement_count=len(merged),
            last_backlog_refinement_id=refinement_id,
            last_backlog_refinement_source=str(archived.as_posix()),
        )

    return {
        **({"change_id": change_id} if change_id else {}),
        "refinement_id": refinement_id,
        "accepted": [item["id"] for item in accepted],
        "unchanged": unchanged,
        "rejected": rejected,
        "source": str(archived.as_posix()),
        "report": str(report_path.as_posix()),
        "backlog": str(epic_path.as_posix()),
    }


def _same_proposal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return {k: v for k, v in left.items() if k != "id"} == {k: v for k, v in right.items() if k != "id"}


def merge_refinements(
    existing: list[dict[str, Any]], accepted: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """IMP-370: accepting the same proposals again changes nothing.

    A proposal already on record (same content) is not added a second time. A new
    proposal whose default id (`BREF-NNN`, from its position in the file) is taken
    gets the next free number. An explicit id already on record replaces that proposal.
    Returns the merged list and the ids that were already on record unchanged.
    """
    merged = [dict(item) for item in existing if isinstance(item, dict)]
    unchanged: list[str] = []
    for proposal in accepted:
        defaulted = bool(proposal.pop("_default_id", False))
        twin = next((item for item in merged if _same_proposal(item, proposal)), None)
        if twin is not None:
            proposal["id"] = twin.get("id", proposal["id"])
            unchanged.append(str(proposal["id"]))
            continue
        index = next((i for i, item in enumerate(merged) if item.get("id") == proposal["id"]), None)
        if index is None:
            merged.append(proposal)
        elif defaulted:
            used = {str(item.get("id")) for item in merged}
            number = 1
            while f"BREF-{number:03d}" in used:
                number += 1
            proposal["id"] = f"BREF-{number:03d}"
            merged.append(proposal)
        else:
            merged[index] = proposal
    return merged, unchanged


def validate_refinement_proposals(
    data: dict[str, Any],
    evidence_text: str,
    story_index: dict[str, dict[str, Any]],
    spec_units: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    proposals = data.get("proposals")
    if not isinstance(proposals, list) or not proposals:
        raise BacklogRefinementError("Backlog refinement source must contain a non-empty proposals array.")
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for index, proposal in enumerate(proposals, start=1):
        if not isinstance(proposal, dict):
            rejected.append({"id": f"BREF-{index:03d}", "kind": "?", "reason": "proposal must be an object"})
            continue
        proposal_id = str(proposal.get("id") or f"BREF-{index:03d}")
        reason = validate_proposal_shape(proposal, evidence_text, story_index, spec_units)
        if reason:
            rejected.append({"id": proposal_id, "kind": str(proposal.get("kind", "?")), "reason": reason})
            continue
        normalized = normalize_proposal(proposal, proposal_id)
        if not proposal.get("id"):
            normalized["_default_id"] = True  # IMP-370: renumbered at merge time if the id is taken
        accepted.append(normalized)
    return accepted, rejected


def validate_proposal_shape(
    proposal: Any,
    evidence_text: str,
    story_index: dict[str, dict[str, Any]],
    spec_units: dict[str, str],
) -> str:
    if not isinstance(proposal, dict):
        return "proposal must be an object"
    kind = str(proposal.get("kind", "")).strip()
    if kind not in VALID_KINDS:
        return f"kind must be one of {', '.join(sorted(VALID_KINDS))}"
    recommendation = str(proposal.get("recommendation", "")).strip()
    rationale = str(proposal.get("rationale", "")).strip()
    if not recommendation or not rationale:
        return "recommendation and rationale are required"
    citations = proposal.get("citations")
    if not isinstance(citations, list) or not citations:
        return "citations must be a non-empty array"
    for citation in citations:
        quote = str(citation).strip()
        if not quote:
            return "empty citation"
        if quote not in evidence_text:
            return f"citation not found verbatim in source of truth: {shield_quote(quote)}"
    discarded_reason = validate_discarded_alternative(proposal.get("discarded_alternative"))
    if discarded_reason:
        return discarded_reason
    target_stories = normalized_list(proposal.get("target_stories", proposal.get("target_story", [])))
    source_units = normalized_list(proposal.get("source_units", proposal.get("source_unit", [])))
    if kind != "missing-story" and not target_stories:
        return "target_stories is required unless kind is missing-story"
    for story_id in target_stories:
        story = story_index.get(story_id)
        if not story:
            return f"target story does not exist: {story_id}"
        if story.get("pending"):
            return f"target story is pending and cannot be refined: {story_id}"
    if not source_units and kind in {"reslice", "split-story", "missing-story", "enabler-candidate"}:
        return "source_units is required for this refinement kind"
    for unit_id in source_units:
        text = spec_units.get(unit_id)
        if text is None:
            return f"source unit does not exist: {unit_id}"
        if is_pending_spec_unit(text):
            return f"source unit is pending and cannot ground refinement: {unit_id}"
    if kind == "enabler-candidate":
        reason = validate_enabler_candidate(proposal, story_index)
        if reason:
            return reason
    return ""


def validate_discarded_alternative(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, dict):
        return "discarded_alternative must be an object"
    for field in ("option", "reason"):
        if not str(value.get(field, "")).strip():
            return f"discarded_alternative requires {field}"
    return ""


def validate_enabler_candidate(proposal: dict[str, Any], story_index: dict[str, dict[str, Any]]) -> str:
    enables = normalized_list(proposal.get("enables_stories", []))
    if not enables:
        return "enabler-candidate requires enables_stories"
    for story_id in enables:
        if story_id not in story_index:
            return f"enabler-candidate enables unknown story: {story_id}"
    required = (
        "supports_boundary",
        "enabled_capability",
        "verification_method",
        "risk_reduced",
        "objective_evidence",
    )
    for field in required:
        if not str(proposal.get(field, "")).strip():
            return f"enabler-candidate requires {field}"
    combined = " ".join(str(proposal.get(field, "")) for field in (*required, "recommendation", "rationale")).lower()
    if any(marker in combined for marker in LOOSE_ENABLER_MARKERS):
        return "enabler-candidate is a loose precondition, not a concrete cross-cutting enabler"
    return ""


def normalize_proposal(proposal: dict[str, Any], proposal_id: str) -> dict[str, Any]:
    kind = str(proposal["kind"]).strip()
    normalized = {
        "id": proposal_id,
        "kind": kind,
        "origin": "agent",
        "target_stories": normalized_list(proposal.get("target_stories", proposal.get("target_story", []))),
        "source_units": normalized_list(proposal.get("source_units", proposal.get("source_unit", []))),
        "recommendation": str(proposal.get("recommendation", "")).strip(),
        "rationale": str(proposal.get("rationale", "")).strip(),
        "citations": [str(item).strip() for item in proposal.get("citations", [])],
    }
    for optional in (
        "slicing_pattern",
        "supports_boundary",
        "enabled_capability",
        "verification_method",
        "risk_reduced",
        "objective_evidence",
    ):
        if str(proposal.get(optional, "")).strip():
            normalized[optional] = str(proposal.get(optional)).strip()
    enables = normalized_list(proposal.get("enables_stories", []))
    if enables:
        normalized["enables_stories"] = enables
    discarded = proposal.get("discarded_alternative")
    if isinstance(discarded, dict):
        option = str(discarded.get("option", "")).strip()
        reason = str(discarded.get("reason", "")).strip()
        if option and reason:
            normalized["discarded_alternative"] = {"option": option, "reason": reason}
    return normalized


def normalized_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def load_story_index(base: Path, change_id: str | None = None) -> dict[str, dict[str, Any]]:
    """The stories a refinement may target: those of the change `change_id`, or (project) those no change wrote."""
    stories: dict[str, dict[str, Any]] = {}
    for path in sorted((base / "04_backlog").glob("US-*.md")):
        text = path.read_text(encoding="utf-8")
        if str(parse_frontmatter(text).get("change", "")).strip() != (change_id or ""):
            continue
        stories[path.stem] = {"path": path, "pending": is_pending_story_stub(text), "text": text}
    return stories


def is_pending_story_stub(text: str) -> bool:
    return (
        "type: pending_input_stub" in text
        or "# US-001 - [PENDING INPUT] Confirm evidence-backed Spec Units before slicing backlog" in text
    )


def is_pending_spec_unit(text: str) -> bool:
    lowered = text.lower()
    return "status: pending" in lowered or "# [pending input]" in lowered


def load_spec_unit_index(base: Path) -> dict[str, str]:
    units: dict[str, str] = {}
    units_dir = base / "03_specs" / "units"
    if not units_dir.exists():
        return units
    for path in sorted(units_dir.glob("SPEC-U-*.md")):
        units[path.stem] = path.read_text(encoding="utf-8")
    return units


def backlog_refinement_evidence_text(base: Path) -> str:
    roots = [
        base / "00_raw",
        base / "01_discovery",
        base / "02_requirements",
        base / "03_specs",
        base / "04_backlog",
        base / "07_changes",
        base / "08_context_packs",
    ]
    parts: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".md", ".txt", ".json"}:
                parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n\n".join(parts)


def change_refinement_evidence_text(project_id: str, change_id: str) -> str:
    """IMP-433: what a refinement of the change may quote: the change's grounding text (request, answers, brief, baseline), its specs,
    its epic and stories and its context packs; never the project's raw or the project's own backlog."""
    from ..compilers.change_backlog import _change_story_ids, epic_id_for
    from ..discovery.change_scope import change_grounding_text

    base = workspace_path(project_id)
    parts = [change_grounding_text(project_id, change_id)]
    files = [base / "04_backlog" / f"{epic_id_for(change_id)}.md",
             *(base / "04_backlog" / f"{sid}.md" for sid in _change_story_ids(base, change_id))]
    refinements = _refinement_dir(base, change_id)
    for root in (base / "03_specs" / change_id, base / "04_backlog" / change_id, base / "08_context_packs" / change_id):
        if root.exists():
            # IMP-433 review M4: the agent's earlier refinements (payloads, accepted records, report) never ground a new one
            files += [path for path in sorted(root.rglob("*")) if path.is_file() and refinements not in path.parents]
    for path in files:
        if path.is_file() and path.suffix.lower() in {".md", ".txt", ".json"}:
            # ...nor does the "Agent Backlog Refinements" section they wrote into the epic and the stories
            parts.append(strip_refinement_section(path.read_text(encoding="utf-8", errors="ignore")))
    return "\n\n".join(parts)


def render_backlog_refinements(base: Path, refinements: list[dict[str, Any]], epic_path: Path | None = None,
                               story_ids: set[str] | None = None) -> None:
    """The epic's section and each target story's; with `story_ids`, only the stories of the scope (IMP-433 review M5: a 0.39
    project record that targeted a change story no longer rewrites it, and a change run leaves the project's alone)."""
    epic_path = epic_path or base / "04_backlog" / "EPIC-001.md"
    write_text(epic_path, append_refinement_section(strip_refinement_section(epic_path.read_text(encoding="utf-8")), refinements, "epic"))
    by_story: dict[str, list[dict[str, Any]]] = {}
    for refinement in refinements:
        for story_id in refinement.get("target_stories", []):
            if story_ids is not None and str(story_id) not in story_ids:
                continue
            by_story.setdefault(str(story_id), []).append(refinement)
    for story_id, story_refinements in by_story.items():
        story_path = base / "04_backlog" / f"{story_id}.md"
        if not story_path.exists():
            continue
        write_text(story_path, append_refinement_section(
                strip_refinement_section(story_path.read_text(encoding="utf-8")),
                story_refinements,
                "story",
            ))


def rerender_refinements(project_id: str, change_id: str | None = None) -> dict[str, list[str]]:
    """IMP-435 (A-02): `/backlog` writes the epic and the stories again, so what the BA accepted through `/refine-backlog` is rendered
    again from `accepted_refinements.json` (as `/specs` does with the PRD compositions). A proposal whose target story no longer exists
    is not rendered: it is named in `refinements/rerender_report.md` and in `dropped`."""
    from ..core.io import remove

    base = workspace_path(project_id)
    folder = _refinement_dir(base, change_id)
    recorded = read_json(folder / "accepted_refinements.json", [])
    report_path = folder / "rerender_report.md"
    result: dict[str, list[str]] = {"rendered": [], "dropped": []}
    if not isinstance(recorded, list) or not recorded:
        return result
    if change_id:
        from ..compilers.change_backlog import epic_id_for

        epic_path = base / "04_backlog" / f"{epic_id_for(change_id)}.md"
    else:
        epic_path = base / "04_backlog" / "EPIC-001.md"
    if not epic_path.exists():
        return result
    stories = {sid for sid, row in load_story_index(base, change_id).items() if not row.get("pending")}
    kept: list[dict[str, Any]] = []
    gone: list[tuple[str, list[str]]] = []
    for item in recorded:
        if not isinstance(item, dict):
            continue
        missing = [str(sid) for sid in item.get("target_stories", []) if str(sid) not in stories]
        if missing:
            gone.append((str(item.get("id", "?")), missing))
        else:
            kept.append(item)
    render_backlog_refinements(base, kept, epic_path, stories)
    result["rendered"] = [str(item.get("id", "?")) for item in kept]
    result["dropped"] = [pid for pid, _missing in gone]
    if gone:
        rows = "\n".join(f"| `{pid}` | {', '.join(f'`{sid}`' for sid in missing)} |" for pid, missing in gone)
        write_text(report_path, "# Backlog refinements not rendered again\n\n"
                   "`/backlog` wrote the stories again and these accepted proposals point at a story that no longer exists, so they were not "
                   "rendered. They stay in `accepted_refinements.json`; refine again with `/refine-backlog` against the current stories.\n\n"
                   "| Proposal | Story that is gone |\n| --- | --- |\n" + rows + "\n")
    elif report_path.exists():
        remove(report_path)
    return result


def strip_refinement_section(text: str) -> str:
    marker = "## Agent Backlog Refinements"
    if marker not in text:
        return text.rstrip() + "\n"
    return text.split(marker, 1)[0].rstrip() + "\n"


def append_refinement_section(text: str, refinements: list[dict[str, Any]], scope: str) -> str:
    if not refinements:
        return text.rstrip() + "\n"
    rows = "\n".join(render_refinement_row(item) for item in refinements)
    return (
        text.rstrip()
        + "\n\n## Agent Backlog Refinements\n\n"
        + "_Origin: agent. Validated by `/refine-backlog` against local source-of-truth citations. These are governed proposals for BA review; they do not replace the slicing model or rewrite scope automatically._\n\n"
        + "| ID | Kind | Target | Source Units | Recommendation | Citations |\n"
        + "| --- | --- | --- | --- | --- | --- |\n"
        + rows
        + f"\n\nScope: `{scope}`.\n"
    )


def render_refinement_row(item: dict[str, Any]) -> str:
    target = ", ".join(item.get("target_stories", [])) or "N/A"
    units = ", ".join(item.get("source_units", [])) or "N/A"
    citations = "; ".join(f"`{table_cell(quote, 80)}`" for quote in item.get("citations", []))
    recommendation_parts = [table_cell(item.get("recommendation", ""), 180)]
    if item.get("kind") == "enabler-candidate":
        enabled_capability = table_cell(item.get("enabled_capability", ""), 120)
        verification_method = table_cell(item.get("verification_method", ""), 120)
        if enabled_capability:
            recommendation_parts.append(f"Enabled capability / Capacidad habilitada: {enabled_capability}")
        if verification_method:
            recommendation_parts.append(f"Verification / Verificacion: {verification_method}")
    discarded = item.get("discarded_alternative")
    if isinstance(discarded, dict):
        option = table_cell(discarded.get("option", ""), 100)
        reason = table_cell(discarded.get("reason", ""), 120)
        if option and reason:
            recommendation_parts.append(f"Discarded alternative / Alternativa descartada: {option} - {reason}")
    recommendation = "<br>".join(recommendation_parts)
    return f"| `{item.get('id', '?')}` | {item.get('kind', '?')} | {target} | {units} | {recommendation} | {citations} |"


def discarded_alternative_note(item: dict[str, Any]) -> str:
    discarded = item.get("discarded_alternative")
    if not isinstance(discarded, dict):
        return "N/A"
    option = table_cell(discarded.get("option", ""), 80)
    reason = table_cell(discarded.get("reason", ""), 120)
    if not option or not reason:
        return "N/A"
    return f"Discarded alternative: {option} - {reason}"


def write_refinement_report(
    project_id: str,
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, str]],
    source: Path,
    change_id: str | None = None,
) -> Path:
    path = _refinement_dir(workspace_path(project_id), change_id) / "refinement_report.md"
    title = f"{project_id} / {change_id}" if change_id else project_id
    accepted_rows = "\n".join(
        f"| {item['id']} | {item['kind']} | {', '.join(item.get('target_stories', [])) or 'N/A'} | agent | {discarded_alternative_note(item)} |"
        for item in accepted
    ) or "| N/A | N/A | N/A | N/A | N/A |"
    rejected_rows = "\n".join(
        f"| {item['id']} | {item.get('kind', '?')} | {item['reason']} |" for item in rejected
    ) or "| N/A | N/A | N/A |"
    write_text(path, f"""# Backlog Refinement Report - {title}

Source: `{source.as_posix()}`

## Accepted Proposals

| Proposal | Kind | Target | Origin | Notes |
| --- | --- | --- | --- | --- |
{accepted_rows}

## Rejected Proposals

| Proposal | Kind | Reason |
| --- | --- | --- |
{rejected_rows}
""")
    return path
