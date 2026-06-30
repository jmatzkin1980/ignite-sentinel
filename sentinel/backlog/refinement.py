from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..core.graph import add_edge, add_node, nodes_by_type
from ..core.io import read_json, write_json
from ..memory import ContextBroker
from ..workspace import update_state, workspace_path


class BacklogRefinementError(RuntimeError):
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


def apply_backlog_refinement(project_id: str, source: Path) -> dict[str, object]:
    base = workspace_path(project_id)
    epic_path = base / "04_backlog" / "EPIC-001.md"
    if not epic_path.exists():
        raise BacklogRefinementError("Cannot refine backlog before /backlog creates 04_backlog/EPIC-001.md.")
    if not source.exists():
        raise BacklogRefinementError(f"Backlog refinement source not found: {source}")

    data = read_json(source, {})
    evidence_text = backlog_refinement_evidence_text(base)
    story_index = load_story_index(base)
    spec_units = load_spec_unit_index(base)
    accepted, rejected = validate_refinement_proposals(data, evidence_text, story_index, spec_units)

    refinement_dir = base / "04_backlog" / "refinements"
    refinement_dir.mkdir(parents=True, exist_ok=True)
    archived = unique_path(refinement_dir / source.name)
    shutil.copyfile(source, archived)

    accepted_path = refinement_dir / "accepted_refinements.json"
    existing = read_json(accepted_path, [])
    existing_refinements = existing if isinstance(existing, list) else []
    merged = [*existing_refinements, *accepted]
    write_json(accepted_path, merged)
    render_backlog_refinements(base, merged)
    report_path = write_refinement_report(project_id, accepted, rejected, archived)

    refinement_id = add_node(
        project_id,
        "CHG",
        "backlog_refinement",
        report_path,
        f"Backlog refinement from {source.name}",
        domain="product",
    )
    for epic in nodes_by_type(project_id, "epic"):
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
    update_state(
        project_id,
        backlog_refinement_count=len(merged),
        last_backlog_refinement_id=refinement_id,
        last_backlog_refinement_source=str(archived.as_posix()),
    )

    if not accepted:
        raise BacklogRefinementError(
            "No backlog refinement proposals were accepted. See 04_backlog/refinements/refinement_report.md."
        )
    return {
        "refinement_id": refinement_id,
        "accepted": [item["id"] for item in accepted],
        "rejected": rejected,
        "source": str(archived.as_posix()),
        "report": str(report_path.as_posix()),
        "backlog": str(epic_path.as_posix()),
    }


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
        proposal_id = str(proposal.get("id") or f"BREF-{index:03d}")
        reason = validate_proposal_shape(proposal, evidence_text, story_index, spec_units)
        if reason:
            rejected.append({"id": proposal_id, "kind": str(proposal.get("kind", "?")), "reason": reason})
            continue
        accepted.append(normalize_proposal(proposal, proposal_id))
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
            return f"citation not found verbatim in source of truth: {quote}"
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
    return normalized


def normalized_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def load_story_index(base: Path) -> dict[str, dict[str, Any]]:
    stories: dict[str, dict[str, Any]] = {}
    for path in sorted((base / "04_backlog").glob("US-*.md")):
        text = path.read_text(encoding="utf-8")
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


def render_backlog_refinements(base: Path, refinements: list[dict[str, Any]]) -> None:
    epic_path = base / "04_backlog" / "EPIC-001.md"
    epic_path.write_text(
        append_refinement_section(strip_refinement_section(epic_path.read_text(encoding="utf-8")), refinements, "epic"),
        encoding="utf-8",
    )
    by_story: dict[str, list[dict[str, Any]]] = {}
    for refinement in refinements:
        for story_id in refinement.get("target_stories", []):
            by_story.setdefault(str(story_id), []).append(refinement)
    for story_id, story_refinements in by_story.items():
        story_path = base / "04_backlog" / f"{story_id}.md"
        if not story_path.exists():
            continue
        story_path.write_text(
            append_refinement_section(
                strip_refinement_section(story_path.read_text(encoding="utf-8")),
                story_refinements,
                "story",
            ),
            encoding="utf-8",
        )


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
    citations = "; ".join(f"`{safe_cell(quote, 80)}`" for quote in item.get("citations", []))
    recommendation_parts = [safe_cell(item.get("recommendation", ""), 180)]
    if item.get("kind") == "enabler-candidate":
        enabled_capability = safe_cell(item.get("enabled_capability", ""), 120)
        verification_method = safe_cell(item.get("verification_method", ""), 120)
        if enabled_capability:
            recommendation_parts.append(f"Enabled capability / Capacidad habilitada: {enabled_capability}")
        if verification_method:
            recommendation_parts.append(f"Verification / Verificacion: {verification_method}")
    recommendation = "<br>".join(recommendation_parts)
    return f"| `{item.get('id', '?')}` | {item.get('kind', '?')} | {target} | {units} | {recommendation} | {citations} |"


def write_refinement_report(
    project_id: str,
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, str]],
    source: Path,
) -> Path:
    path = workspace_path(project_id) / "04_backlog" / "refinements" / "refinement_report.md"
    accepted_rows = "\n".join(
        f"| {item['id']} | {item['kind']} | {', '.join(item.get('target_stories', [])) or 'N/A'} | agent |"
        for item in accepted
    ) or "| N/A | N/A | N/A | N/A |"
    rejected_rows = "\n".join(
        f"| {item['id']} | {item.get('kind', '?')} | {item['reason']} |" for item in rejected
    ) or "| N/A | N/A | N/A |"
    path.write_text(
        f"""# Backlog Refinement Report - {project_id}

Source: `{source.as_posix()}`

## Accepted Proposals

| Proposal | Kind | Target | Origin |
| --- | --- | --- | --- |
{accepted_rows}

## Rejected Proposals

| Proposal | Kind | Reason |
| --- | --- | --- |
{rejected_rows}
""",
        encoding="utf-8",
    )
    return path


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise BacklogRefinementError(f"Could not allocate unique path for {path}")


def safe_cell(value: Any, limit: int) -> str:
    text = str(value).replace("\n", " ").replace("|", "/").strip()
    return text[:limit]
