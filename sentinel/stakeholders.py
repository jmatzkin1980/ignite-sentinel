"""IMP-192: governed stakeholder registry + elicitation routing.

A per-project registry (`01_discovery/stakeholders.md`) recording who owns which
domain/topic, mutated **only through the `/stakeholders` CLI command** — the
Markdown is a generated artifact, never hand-authored. Each owner carries a
`respondent_profile` (reused from IMP-142: `business` | `technical`) so the
elicitation surfaces can calibrate phrasing.

The registry's payoff is routing: the interview script (IMP-183) groups open gaps
by their assigned owner ("these questions go to Operations; these to Technology").
Routing is deterministic — a gap is matched to an owner by its lens/domain. A gap
whose lens has no owner is never assigned a fabricated one; it lands in an explicit
"unassigned" bucket. Power×Interest scoring and communication plans are out of
scope (that is delivery, not discovery).
"""
from __future__ import annotations

from typing import Any

from .core.graph import add_node
from .core.markdown import parse_table_rows
from .technique_registry import normalize_respondent_profile
from .workspace import read_json, workspace_path

REGISTRY_RELPATH = ("01_discovery", "stakeholders.md")
_HEADER_CELLS = ("ID", "Name", "Domain", "Topic", "Respondent Profile", "Notes")


def registry_path(project_id: str):
    return workspace_path(project_id).joinpath(*REGISTRY_RELPATH)


def _norm_domain(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def parse_stakeholders(text: str) -> list[dict[str, str]]:
    rows = parse_table_rows(text, skip_separator_rows=True)
    parsed: list[dict[str, str]] = []
    for cells in rows:
        if len(cells) < 6:
            continue
        if cells[0].strip().lower() in {"id", ""}:
            continue
        parsed.append(
            {
                "id": cells[0].strip(),
                "name": cells[1].strip(),
                "domain": _norm_domain(cells[2]),
                "topic": cells[3].strip(),
                "respondent_profile": cells[4].strip(),
                "notes": cells[5].strip(),
            }
        )
    return parsed


def load_stakeholders(project_id: str) -> list[dict[str, str]]:
    path = registry_path(project_id)
    if not path.exists():
        return []
    return parse_stakeholders(path.read_text(encoding="utf-8"))


def _display(value: str) -> str:
    return value if value.strip() else "—"


def render_stakeholders(project_id: str, rows: list[dict[str, str]], language: str = "en") -> str:
    es = language == "es"
    if es:
        header = (
            f"# Registro de stakeholders - {project_id}\n\n"
            "Artefacto GENERADO — mutar solo vía `/stakeholders` (nunca a mano). "
            "Cada dueño gobierna un dominio/tema; el guión de entrevista (IMP-183) rutea "
            "los gaps por dueño. `respondent_profile` reusa IMP-142 (`business`|`technical`).\n"
        )
        empty = "_Sin stakeholders registrados. Agregar con `/stakeholders PROJECT_ID --add ...`._\n"
    else:
        header = (
            f"# Stakeholder Registry - {project_id}\n\n"
            "GENERATED artifact — mutate only via `/stakeholders` (never by hand). "
            "Each owner governs a domain/topic; the interview script (IMP-183) routes "
            "gaps by owner. `respondent_profile` reuses IMP-142 (`business`|`technical`).\n"
        )
        empty = "_No stakeholders registered. Add one with `/stakeholders PROJECT_ID --add ...`._\n"
    if not rows:
        return header + "\n" + empty
    lines = [header, "\n", "| " + " | ".join(_HEADER_CELLS) + " |\n", "| " + " | ".join(["---"] * len(_HEADER_CELLS)) + " |\n"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                (
                    f"`{row['id']}`",
                    _display(row.get("name", "")),
                    f"`{row['domain']}`" if row.get("domain") else "—",
                    _display(row.get("topic", "")),
                    f"`{row['respondent_profile']}`" if row.get("respondent_profile") else "—",
                    _display(row.get("notes", "")),
                )
            )
            + " |\n"
        )
    return "".join(lines)


def _project_language(project_id: str) -> str:
    state = read_json(workspace_path(project_id) / "state.json", {})
    language = state.get("project_language", "en")
    return str(language if language in {"es", "en"} else "en")


def _write_registry(project_id: str, rows: list[dict[str, str]]) -> str:
    path = registry_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_stakeholders(project_id, rows, _project_language(project_id)), encoding="utf-8")
    add_node(project_id, "DISC", "stakeholder_registry", path, "Stakeholder registry", status="active")
    return path.as_posix()


def _next_id(rows: list[dict[str, str]]) -> str:
    used = 0
    for row in rows:
        ident = row.get("id", "")
        if ident.upper().startswith("STK-"):
            try:
                used = max(used, int(ident.split("-", 1)[1]))
            except (ValueError, IndexError):
                continue
    return f"STK-{used + 1:03d}"


def add_stakeholder(
    project_id: str,
    *,
    name: str,
    domain: str,
    stakeholder_id: str | None = None,
    profile: str | None = None,
    topic: str = "",
    notes: str = "",
) -> dict[str, Any]:
    base = workspace_path(project_id)
    if not base.exists():
        raise RuntimeError(f"Workspace not found: {project_id}")
    if not str(name).strip():
        raise RuntimeError("/stakeholders --add requires --name.")
    normalized_domain = _norm_domain(domain)
    if not normalized_domain:
        raise RuntimeError("/stakeholders --add requires --domain (the lens/domain this owner answers for).")
    rows = load_stakeholders(project_id)
    existing_ids = {row["id"].upper() for row in rows}
    if stakeholder_id:
        stakeholder_id = stakeholder_id.strip()
        if stakeholder_id.upper() in existing_ids:
            raise RuntimeError(f"Stakeholder id already registered: {stakeholder_id}")
    else:
        stakeholder_id = _next_id(rows)
    # respondent_profile is optional; when provided it must be a recognized
    # IMP-142 profile — an unrecognized value is dropped rather than invented.
    normalized_profile = normalize_respondent_profile(profile) if profile else None
    entry = {
        "id": stakeholder_id,
        "name": str(name).strip(),
        "domain": normalized_domain,
        "topic": str(topic or "").strip(),
        "respondent_profile": normalized_profile or "",
        "notes": str(notes or "").strip(),
    }
    rows.append(entry)
    path = _write_registry(project_id, rows)
    return {
        "project_id": project_id,
        "added": entry,
        "registry_path": path,
        "count": len(rows),
        "profile_ignored": bool(profile) and not normalized_profile,
    }


def list_stakeholders(project_id: str) -> dict[str, Any]:
    base = workspace_path(project_id)
    if not base.exists():
        raise RuntimeError(f"Workspace not found: {project_id}")
    rows = load_stakeholders(project_id)
    # Re-render so the generated artifact exists and stays canonical even on a read.
    path = _write_registry(project_id, rows)
    return {"project_id": project_id, "stakeholders": rows, "registry_path": path, "count": len(rows)}


def owner_for_lens(lens: str, stakeholders: list[dict[str, str]]) -> dict[str, str] | None:
    """First stakeholder (stable by id) whose domain matches this lens.

    Deterministic and never fabricated: no match returns None so the caller can
    mark the gap unassigned rather than invent an owner.
    """
    target = _norm_domain(lens)
    if not target:
        return None
    matches = [row for row in stakeholders if row.get("domain") == target]
    return sorted(matches, key=lambda r: r.get("id", ""))[0] if matches else None
