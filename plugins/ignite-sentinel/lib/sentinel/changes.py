"""IMP-382: a change on an existing system (CHG-nnn) matures apart from the project.

A change opens with its own scope round (a subset of the lens checks, scoped to the
change work kind) and keeps its gaps under `01_discovery/<CHG-nnn>/`. The project's
requirement, gaps and artifacts are never touched by it.
"""
from __future__ import annotations

import re
from pathlib import Path

from .core.graph import add_node
from .core.io import write_text
from .core.time import utc_now
from .errors import GateRefusal, InputError
from .gaps import count_gaps, parse_gap_rows, render_gaps
from .injection import shield_source
from .core.text import unique_path
from .lens_registry import SURFACE_TYPES, load_lens_checks
from .secrets_scan import ingest_source, pii_report_enabled
from .source_formats import read_source, target_suffix
from .sources import mark_source_processed, open_source_row
from .workspace import ensure_workspace, load_config, read_state, update_state, workspace_path

SCOPE_ROUND_IDS: tuple[str, ...] = ("GAP-OBJECTIVE", "GAP-USERS", "GAP-SCOPE", "GAP-PRODUCT-ASIS-TOBE")


def change_gaps_path(base: Path, change_id: str) -> Path:
    return base / "01_discovery" / change_id / "gaps.md"


def list_changes(project_id: str) -> dict[str, dict]:
    return read_state(project_id).get("changes", {})


def get_change(project_id: str, change_id: str) -> dict:
    changes = list_changes(project_id)
    if change_id not in changes:
        known = ", ".join(sorted(changes))
        raise GateRefusal(
            f"{change_id} no es un cambio abierto de {project_id}",
            next_step=(
                f"Cambios conocidos: {known}."
                if known
                else f"Abrí uno con /ingest {project_id} --source NOTA --change."
            ),
        )
    return changes[change_id]


def _scope_gap() -> dict[str, str]:
    check = next(c for c in load_lens_checks() if c["id"] == "GAP-SCOPE")
    return {"id": check["id"], "lens": check["lens"], "severity": check["severity"], "description": check["description"]}


def change_language(project_id: str, change: dict, fallback_text: str = "") -> str:
    """The language the change's gaps are rendered in: fixed at ingest, never the project's."""
    from .discovery.intake import resolve_project_language

    stored = change.get("language")
    if stored:
        return str(stored)
    return resolve_project_language(load_config(project_id).get("project_language", "auto"), fallback_text)


def ingest_change(project_id: str, source: Path) -> dict:
    # Imported here: the discovery package imports this module's caller chain.
    from .discovery.detection import detect_gaps
    from .discovery.intake import load_domain_context, resolve_project_language

    ensure_workspace(project_id)
    base = workspace_path(project_id)
    natural = base / "00_raw" / f"{source.stem}{target_suffix(source)}"
    # The id comes from the source path (add_node dedups on it): a second --change with the
    # same file would overwrite the open change's answers, border and gaps. Refuse before writing.
    for open_id, entry in list_changes(project_id).items():
        if entry.get("source") == f"00_raw/{natural.name}" or entry.get("origin") == source.name:
            raise GateRefusal(
                f"{source.name} ya está abierto como {open_id} en {project_id}",
                next_step=f"Seguí ese cambio con /gaps {project_id} --change {open_id}; para un cambio nuevo usá otro archivo.",
            )
    # A raw copy that is not this change's own (the project's input, a baseline source) is never overwritten.
    raw_target = unique_path(natural)
    own_source = f"00_raw/{raw_target.name}"
    extracted = read_source(source, media_stem=raw_target.stem)
    source_id = open_source_row(project_id, source, "change_ingested")
    config = load_config(project_id)
    text, _sanitized = ingest_source(base, source, raw_target, pii_report_enabled(config), extracted)
    text, _injection_ids = shield_source(base, source.name, text)
    language = resolve_project_language(config.get("project_language", "auto"), text)
    context = load_domain_context(base)
    mark_source_processed(project_id, source, "change_ingested", source_id=source_id)
    mark_source_processed(project_id, raw_target, "raw_copy", source_id=source_id)
    change_id = add_node(project_id, "CHG", "change", raw_target, source.stem, status="open", domain="product")

    found = {g["id"]: g for g in detect_gaps(text, context, work="change")}
    # GAP-SCOPE carries the border: it is always asked, whether or not its token check fires.
    found.setdefault("GAP-SCOPE", _scope_gap())
    gaps = [found[gap_id] for gap_id in SCOPE_ROUND_IDS if gap_id in found]
    gaps_path = change_gaps_path(base, change_id)
    write_text(gaps_path, render_gaps(project_id, gaps, change_id, language, gaps_path.with_name("gap_elicitation.json")))

    changes = dict(list_changes(project_id))
    changes[change_id] = {
        "source": own_source,
        "origin": source.name,
        "language": language,
        "opened_at": utc_now(),
        "round": "scope",
        "border": [],
        "border_confirmed_at": None,
        "responses": [],
    }
    update_state(project_id, changes=changes)
    return {
        "project_id": project_id,
        "change_id": change_id,
        "gaps_path": str(gaps_path.as_posix()),
        "gap_counts": count_gaps(gaps),
        "round": "scope",
    }


BORDER_ZONES: tuple[str, ...] = ("nuevo", "adyacente", "preservado")
_BORDER_TYPE_ALIASES = {"integración": "integracion"}
_BORDER_FIELD = re.compile(r"^([ 	]*)-[ 	]*Borde[ 	]*:[ 	]*(.*)$", re.I | re.M)


def parse_border(response_block: str, cite: str) -> list[dict[str, str]]:
    """The structured border in a confirmed answer to GAP-SCOPE: one `zona | tipo | nombre` line per surface.

    The border comes only from what the BA wrote; an invalid line rejects the whole block.
    """
    match = _BORDER_FIELD.search(response_block)
    if not match:
        raise InputError(
            "La respuesta a GAP-SCOPE no trae el bloque `Borde:` "
            f"(una línea `zona | tipo | nombre` por superficie; zonas: {', '.join(BORDER_ZONES)}; tipos: {', '.join(SURFACE_TYPES)}).",
            next_step="Agregá `- Borde:` debajo de la respuesta de GAP-SCOPE y volvé a correr /resolve-gaps.",
        )
    indent = len(match.group(1).expandtabs(4))
    lines = [match.group(2).strip()] if match.group(2).strip() else []
    for line in response_block[match.end():].splitlines()[1:]:
        if not line.strip() or len(line) - len(line.lstrip(" 	")) <= indent:
            break
        lines.append(line.strip())
    border: list[dict[str, str]] = []
    for raw in lines:
        text = raw.lstrip("-*").strip()
        parts = [part.strip() for part in text.split("|", 2)]
        if len(parts) != 3 or not all(parts):
            raise InputError(
                f"Línea de borde inválida: «{text}». El formato es `zona | tipo | nombre` "
                f"(zonas válidas: {', '.join(BORDER_ZONES)}; tipos válidos: {', '.join(SURFACE_TYPES)}).",
                next_step="Corregí la línea y volvé a correr /resolve-gaps con el mismo archivo.",
            )
        zone, kind, name = parts[0].lower(), parts[1].lower(), parts[2]
        kind = _BORDER_TYPE_ALIASES.get(kind, kind)
        if zone not in BORDER_ZONES:
            raise InputError(
                f"Zona de borde inválida «{parts[0]}» en la línea «{text}». Zonas válidas: {', '.join(BORDER_ZONES)}.",
                next_step="Corregí la línea y volvé a correr /resolve-gaps con el mismo archivo.",
            )
        if kind not in SURFACE_TYPES:
            raise InputError(
                f"Tipo de borde inválido «{parts[1]}» en la línea «{text}». "
                f"Tipos válidos: {', '.join(SURFACE_TYPES)} (integración se acepta con tilde).",
                next_step="Corregí la línea y volvé a correr /resolve-gaps con el mismo archivo.",
            )
        border.append({"zone": zone, "type": kind, "name": name, "cite": cite})
    if not border:
        raise InputError(
            "El bloque `Borde:` de GAP-SCOPE no tiene ninguna línea "
            f"(`zona | tipo | nombre`; zonas: {', '.join(BORDER_ZONES)}; tipos: {', '.join(SURFACE_TYPES)}).",
            next_step="Agregá al menos una superficie y volvé a correr /resolve-gaps.",
        )
    return border


def without_border_block(text: str) -> str:
    """The answer text minus its `Borde:` blocks: surface names are not claims about the source's validity."""
    kept: list[str] = []
    indent: int | None = None
    for line in text.splitlines():
        field = _BORDER_FIELD.match(line)
        if field:
            indent = len(field.group(1).expandtabs(4))
            continue
        if indent is not None:
            if line.strip() and len(line) - len(line.lstrip(" 	")) > indent:
                continue
            indent = None
        kept.append(line)
    return "\n".join(kept)


def confirm_border(project_id: str, change_id: str, border: list[dict[str, str]]) -> None:
    """Fix the confirmed border on the change and open its lens round."""
    get_change(project_id, change_id)
    changes = {key: dict(value) for key, value in list_changes(project_id).items()}
    changes[change_id].update({"border": list(border), "border_confirmed_at": utc_now(), "round": "lenses"})
    update_state(project_id, changes=changes)


def border_types(change: dict) -> frozenset[str]:
    """The surface types the BA confirmed (or proposed) in the change's border."""
    return frozenset(str(item.get("type")) for item in change.get("border", []) if item.get("type"))


def _read_evidence(base: Path, change: dict) -> str:
    parts = []
    for rel in [change["source"], *change.get("responses", [])]:
        path = Path(rel)
        path = path if path.is_absolute() else base / path
        parts.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def regenerate_change_gaps(project_id: str, change_id: str) -> dict:
    """Re-render the change's gaps.md; in the lens round add the checks not yet there, once."""
    from .discovery.detection import detect_gaps
    from .discovery.intake import load_domain_context

    change = get_change(project_id, change_id)
    base = workspace_path(project_id)
    gaps_path = change_gaps_path(base, change_id)
    existing = parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if gaps_path.exists() else []
    evidence = _read_evidence(base, change)
    language = change_language(project_id, change, evidence)
    rows = list(existing)
    if change.get("round") == "lenses":
        have = {row["id"] for row in existing}
        found = detect_gaps(evidence, load_domain_context(base), work="change", border_types=border_types(change))
        rows += [g for g in found if g["id"] not in SCOPE_ROUND_IDS and g["id"] not in have]
    write_text(gaps_path, render_gaps(project_id, rows, change_id, language, gaps_path.with_name("gap_elicitation.json")))
    counts = count_gaps(rows)
    changes = {key: dict(value) for key, value in list_changes(project_id).items()}
    changes[change_id]["gap_counts"] = counts
    update_state(project_id, changes=changes)
    return {
        "project_id": project_id,
        "change_id": change_id,
        "path": str(gaps_path.as_posix()),
        "gap_counts": counts,
        "round": change.get("round"),
    }
