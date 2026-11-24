"""IMP-382: a change on an existing system (CHG-nnn) matures apart from the project.

A change opens with its own scope round (a subset of the lens checks, scoped to the
change work kind) and keeps its gaps under `01_discovery/<CHG-nnn>/`. The project's
requirement, gaps and artifacts are never touched by it.
"""
from __future__ import annotations

import re
import unicodedata
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
from .source_registry import ROLE_FOLDERS
from .sources import declare_source_role, mark_source_processed, open_source_row
from .workspace import ensure_workspace, load_config, read_state, update_state, workspace_path

SCOPE_ROUND_IDS: tuple[str, ...] = ("GAP-OBJECTIVE", "GAP-USERS", "GAP-SCOPE", "GAP-PRODUCT-ASIS-TOBE")


def change_gaps_path(base: Path, change_id: str) -> Path:
    return base / "01_discovery" / change_id / "gaps.md"


def list_changes(project_id: str) -> dict[str, dict]:
    return read_state(project_id).get("changes", {})


CHANGE_DELIVERABLES: tuple[str, ...] = ("brief", "gaps", "borde", "decisiones")  # IMP-386: what /view and /export take with --change
REVIEW_DELIVERABLES: tuple[str, ...] = ("borde", "decisiones")  # IMP-412: review views of a change (only md; only with --change)
CHANGE_FORMATS: dict[str, tuple[str, ...]] = {"gaps": ("md", "interview", "faq"), "brief": ("md", "interview"),
                                              "borde": ("md",), "decisiones": ("md",)}


def check_change_deliverable(project_id: str, command: str, artifact: str, change_id: str, fmt: str | None = None) -> None:
    """`/view` and `/export` with --change: the change's own artifacts, and only of an open change.

    IMP-412: `fmt` (an export) must be one the artifact takes: the review views are Markdown only."""
    if artifact.lower() not in CHANGE_DELIVERABLES:
        raise InputError(
            f"/{command} --change sólo admite {' o '.join(CHANGE_DELIVERABLES)}, no {artifact}: el resto es del proyecto.",
            next_step=f"Quitá --change para {artifact}, o usá --artifact {'|'.join(CHANGE_DELIVERABLES)} --change {change_id}.",
        )
    get_change(project_id, change_id)
    allowed = CHANGE_FORMATS.get(artifact.lower(), ())
    if fmt is not None and artifact.lower() in REVIEW_DELIVERABLES and fmt not in allowed:
        raise InputError(
            f"/{command} --artifact {artifact} --change sólo admite el formato {' o '.join(allowed)}, no {fmt}.",
            next_step=f"/{command} {project_id} --artifact {artifact} --change {change_id}",
        )


def is_change_only(project_id: str) -> bool:
    """IMP-406: the workspace holds at least one change and no project requirements."""
    if (workspace_path(project_id) / "02_requirements" / "requirements.md").exists():
        return False
    return bool(list_changes(project_id))


def refuse_change_only_deliverable(project_id: str, command: str, artifact: str) -> None:
    """IMP-386: a workspace that only holds changes has no project brief or gaps to view or export."""
    if artifact.lower() in REVIEW_DELIVERABLES:  # IMP-412: a review view is always of one change
        raise InputError(f"/{command} --artifact {artifact} goes with --change CHG-NNN",
                         next_step=f"/{command} {project_id} --artifact {artifact} --change CHG-NNN")
    if artifact.lower() not in CHANGE_DELIVERABLES:
        return
    if not is_change_only(project_id):
        return
    open_changes = sorted(list_changes(project_id))
    if open_changes:
        raise GateRefusal(
            f"{project_id} sólo tiene cambios: no hay {artifact} del proyecto para /{command}",
            next_step=f"/{command} {project_id} --artifact {artifact} --change {open_changes[0]}",
        )


def refuse_change_only_specs(project_id: str, command: str = "specs") -> None:
    """IMP-388/393: a workspace that only holds changes has no project requirements to derive specs or a backlog from."""
    if (workspace_path(project_id) / "02_requirements" / "requirements.md").exists():
        return
    open_changes = sorted(list_changes(project_id))
    if open_changes:
        raise GateRefusal(
            f"{project_id} sólo tiene cambios: no hay 02_requirements/requirements.md del proyecto para /{command}",
            next_step=f"/{command} {project_id} --change {open_changes[0]}",
        )


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
    natural = base / ROLE_FOLDERS["pedido"] / f"{source.stem}{target_suffix(source)}"
    natural.parent.mkdir(parents=True, exist_ok=True)
    # The id comes from the source path (add_node dedups on it): a second --change with the
    # same file would overwrite the open change's answers, border and gaps. Refuse before writing.
    for open_id, entry in list_changes(project_id).items():
        if (entry.get("source") in (f"00_raw/{natural.name}", f"00_raw/09_request/{natural.name}")
                or entry.get("origin") == source.name):
            raise GateRefusal(
                f"{source.name} ya está abierto como {open_id} en {project_id}",
                next_step=f"Seguí ese cambio con /gaps {project_id} --change {open_id}; para un cambio nuevo usá otro archivo.",
            )
    # A raw copy that is not this change's own (the project's input, a baseline source) is never overwritten.
    raw_target = unique_path(natural)
    own_source = raw_target.relative_to(base).as_posix()
    extracted = read_source(source, media_stem=raw_target.stem)
    source_id = open_source_row(project_id, source, "change_ingested")
    declare_source_role(project_id, source_id, "pedido")  # IMP-400: the note is the request
    config = load_config(project_id)
    text, _sanitized = ingest_source(base, source, raw_target, pii_report_enabled(config), extracted)
    text, _injection_ids = shield_source(base, source.name, text)
    language = resolve_project_language(config.get("project_language", "auto"), text)
    context = load_domain_context(base)
    mark_source_processed(project_id, source, "change_ingested", source_id=source_id)
    mark_source_processed(project_id, raw_target, "raw_copy", source_id=source_id)
    change_id = add_node(project_id, "CHG", "change", raw_target, source.stem, status="open", domain="product")
    # IMP-406: the request is indexed now, so /health does not flag the change as missing from memory.
    from .memory import ContextBroker

    ContextBroker(project_id).index_artifact(change_id, "change", raw_target, text, domain="product",
                                             trace_ids=[change_id], client_source=True)

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
        "gap_counts": count_gaps(gaps),
        "sources": [source_id],
    }
    update_state(project_id, changes=changes)
    from .source_versions import check_change_versions

    from .readiness_verdict import change_next_step  # IMP-408

    check_change_versions(project_id, change_id)  # IMP-400: a request that cites another version of a loaded source
    return {
        "project_id": project_id,
        "change_id": change_id,
        "gaps_path": str(gaps_path.as_posix()),
        "gap_counts": list_changes(project_id)[change_id]["gap_counts"],
        "round": "scope",
        "next_step": change_next_step(project_id, change_id),
    }


BORDER_ZONES: tuple[str, ...] = ("nuevo", "adyacente", "preservado")
_BORDER_TYPE_ALIASES = {"integración": "integracion"}
_BORDER_FIELD = re.compile(r"^([ 	]*)-[ 	]*Borde[ 	]*:[ 	]*(.*)$", re.I | re.M)


ALIAS_MAX = 40


def _alias_error(alias: str, name: str, problem: str, language: str) -> InputError:
    es = language == "es"
    return InputError(
        (f"El alias «{alias}» de la superficie «{name}» {problem}." if es
         else f"The alias «{alias}» of the surface «{name}» {problem}."),
        next_step=("Corregí el alias (corto, sin `;` ni `|`, sin tildes, único) y volvé a correr /resolve-gaps con el mismo archivo." if es
                   else "Fix the alias (short, no `;` or `|`, no accents, unique) and run /resolve-gaps again with the same file."),
    )


def _check_alias(alias: str, name: str, language: str) -> str:
    """IMP-398: a short alias: no `;` or `|`, at most 40 characters, no accents (uniqueness is checked over the whole border)."""
    es = language == "es"
    problem = None
    if not alias:
        problem = "está vacío" if es else "is empty"
    elif ";" in alias or "|" in alias:
        problem = "no puede llevar `;` ni `|`" if es else "cannot contain `;` or `|`"
    elif len(alias) > ALIAS_MAX:
        problem = f"tiene más de {ALIAS_MAX} caracteres" if es else f"is longer than {ALIAS_MAX} characters"
    elif unicodedata.normalize("NFD", alias) != alias:
        problem = "no puede llevar tildes" if es else "cannot contain accents"
    if problem:
        raise _alias_error(alias, name, problem, language)
    return alias


def _check_alias_collisions(border: list[dict[str, str]], language: str) -> None:
    """IMP-398: with the same fold `Superficie` uses, no alias may equal another surface's alias or name (its own name is fine)."""
    from .change_requirements import _fold_name

    for i, item in enumerate(border):
        alias = item.get("alias")
        if not alias:
            continue
        key = _fold_name(alias)
        for j, other in enumerate(border):
            if i == j:
                continue
            if key in (_fold_name(other["name"]), _fold_name(other.get("alias", "")) if other.get("alias") else None):
                raise _alias_error(alias, item["name"], (
                    "ya lo usa otra superficie del borde" if language == "es" else "is already used by another border surface"), language)


def parse_border(response_block: str, cite: str, language: str = "es") -> list[dict[str, str]]:
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
        parts = [part.strip() for part in text.split("|", 3)]
        if len(parts) not in (3, 4) or not all(parts[:3]):
            raise InputError(
                f"Línea de borde inválida: «{text}». El formato es `zona | tipo | nombre [| alias]` (alias opcional) "
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
        if ";" in name:
            raise InputError(
                (f"El nombre de superficie «{name}» no puede llevar `;` (separa las superficies en Superficie)." if language == "es"
                 else f"The surface name «{name}» cannot contain `;` (it separates surfaces in Surface)."),
                next_step=("Sacá el `;` del nombre y volvé a correr /resolve-gaps con el mismo archivo." if language == "es"
                           else "Remove the `;` from the name and run /resolve-gaps again with the same file."),
            )
        item = {"zone": zone, "type": kind, "name": name, "cite": cite}
        if len(parts) == 4:
            item["alias"] = _check_alias(parts[3], name, language)
        border.append(item)
    _check_alias_collisions(border, language)
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
    # IMP-404: a surface the BA accepted from a cross-read survives a re-confirmed border.
    from .change_requirements import _fold_name

    taken = {_fold_name(n) for item in border for n in (item.get("name"), item.get("alias")) if n}
    kept = [dict(item) for item in changes[change_id].get("border") or []
            if item.get("origin") == "cross" and _fold_name(item.get("name", "")) not in taken]
    changes[change_id].update({"border": [*border, *kept], "border_confirmed_at": utc_now(), "round": "lenses"})
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


def _lens_evidence(base: Path, change: dict) -> str:
    """The change note plus only the answer text of each response file.

    The form labels ("Owner / fuente", "Evidencia o referencia", ...) are not content: read as
    evidence they would suppress checks that look for an owner, a source or a decision.
    """
    from .gaps import parse_gap_responses

    parts = []
    for i, rel in enumerate([change["source"], *change.get("responses", [])]):
        path = Path(rel)
        path = path if path.is_absolute() else base / path
        text = path.read_text(encoding="utf-8")
        if i:
            text = "\n".join(r.get("answer", "") for r in parse_gap_responses(text).values())
        parts.append(text)
    return "\n\n".join(parts)


_ACCEPTANCE_HEADINGS = ("criterios de aceptacion", "acceptance criteria")


def _request_states_acceptance(base: Path, change: dict) -> bool:
    """IMP-402 (change path only): the request itemizes its acceptance criteria.

    The lens checks read sentences and skip headings, so a request whose criteria sit under a
    "Criterios de aceptación" heading, or carry CA-/AC- ids, would still be asked for them."""
    from .extraction.inventory import _heading_keyword, parse_request_elements

    path = Path(change["source"])
    path = path if path.is_absolute() else base / path
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    for element in parse_request_elements(text, "", ""):
        if element["kind"] != "criterion":
            continue
        if element["id"].startswith(("CA-", "AC-")) or _heading_keyword(element["section"]).startswith(_ACCEPTANCE_HEADINGS):
            return True
    return False


GAP_IMPACTS = ("construccion", "operativo")


def deferred_gaps(project_id: str, change_id: str) -> list[dict]:
    """IMP-406: the change's open questions that do not block, each with the class the BA gave it (build by default)."""
    from .gaps import BLOCKING_GAP_STATUSES, blocking_severities

    change = get_change(project_id, change_id)
    path = change_gaps_path(workspace_path(project_id), change_id)
    rows = parse_gap_rows(path.read_text(encoding="utf-8-sig")) if path.exists() else []
    severities = blocking_severities(load_config(project_id))
    classed = change.get("gap_impact") or {}
    found = []
    for row in rows:
        if row.get("id") == "NONE":
            continue
        status = str(row.get("status", "OPEN")).strip("`").upper()
        severity = str(row.get("severity", "")).strip("`").lower()
        if status not in BLOCKING_GAP_STATUSES or severity in severities:
            continue
        mark = classed.get(row["id"]) or {}
        found.append({"id": row["id"], "lens": row.get("lens", ""), "severity": severity,
                      "impact": mark.get("impact", "construccion"), "reason": mark.get("reason", ""),
                      "classed": bool(mark)})
    return found


def set_gap_impact(project_id: str, change_id: str, gap_id: str, impact: str, reason: str) -> dict:
    """IMP-406: class an open, non-blocking question of the change as a build or an operational deferred item."""
    from .gaps import BLOCKING_GAP_STATUSES, blocking_severities
    from .readiness_verdict import build_change_verdict

    change = get_change(project_id, change_id)
    es = change_language(project_id, change) == "es"
    if impact not in GAP_IMPACTS:
        raise InputError(f"--impact es {' o '.join(GAP_IMPACTS)}" if es else f"--impact is {' or '.join(GAP_IMPACTS)}")
    if not reason.strip():
        raise InputError("--impact necesita --reason con el porqué" if es else "--impact needs --reason with the why")
    path = change_gaps_path(workspace_path(project_id), change_id)
    rows = parse_gap_rows(path.read_text(encoding="utf-8-sig")) if path.exists() else []
    row = next((r for r in rows if r.get("id") == gap_id), None)
    if row is None:
        raise InputError(f"{gap_id} no es una pregunta de {change_id}" if es else f"{gap_id} is not a question of {change_id}")
    status = str(row.get("status", "OPEN")).strip("`").upper()
    if status not in BLOCKING_GAP_STATUSES:
        raise InputError(
            f"{gap_id} ya está cerrada: la clase sólo aplica a pendientes abiertos" if es
            else f"{gap_id} is already closed: the class only applies to open deferred items")
    if str(row.get("severity", "")).strip("`").lower() in blocking_severities(load_config(project_id)):
        raise InputError(
            f"{gap_id} es bloqueante: se responde, no se difiere" if es
            else f"{gap_id} is blocking: it is answered, not deferred")
    changes = {key: dict(value) for key, value in list_changes(project_id).items()}
    marks = dict(changes[change_id].get("gap_impact") or {})
    marks[gap_id] = {"impact": impact, "reason": reason.strip(), "at": utc_now()}
    changes[change_id]["gap_impact"] = marks
    update_state(project_id, changes=changes)
    return {
        "project_id": project_id, "change_id": change_id, "action": "impact", "gap_id": gap_id,
        "impact": impact, "reason": reason.strip(), "verdict": build_change_verdict(project_id, change_id),
        "message": (f"{change_id}: {gap_id} queda como pendiente {impact}: {reason.strip()}" if es
                    else f"{change_id}: {gap_id} is now a {impact} deferred item: {reason.strip()}"),
    }


def regenerate_change_gaps(project_id: str, change_id: str, prune: bool = False) -> dict:
    """Re-render the change's gaps.md; in the lens round add the checks not yet there, once.

    `prune` also drops the unanswered lens checks of a surface type the border no longer has."""
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
        found = detect_gaps(_lens_evidence(base, change), load_domain_context(base), work="change", border_types=border_types(change))
        if _request_states_acceptance(base, change):
            found = [g for g in found if g["id"] != "GAP-ACCEPTANCE"]
        fresh = [g for g in found if g["id"] not in SCOPE_ROUND_IDS and g["id"] not in have]
        if fresh:  # IMP-410: a check the change already decided is not asked again
            from .extraction.inventory import pedido_rows
            from .prior_decisions import apply_prior_decisions, candidate_from_gap

            sources = [str(r["id"]) for r in pedido_rows(project_id, change_id)]
            apply_prior_decisions(project_id, change_id, fresh, {g["id"]: candidate_from_gap(g, sources) for g in fresh})
        rows += fresh
        if prune:
            context = load_domain_context(base)
            every = {g["id"] for g in detect_gaps(_lens_evidence(base, change), context, work="change", border_types=None)}
            moot = every - {g["id"] for g in found}
            rows = [r for r in rows if not (
                r["id"] in moot and str(r.get("origin", "")).strip("`") != "cross"
                and str(r.get("status", "OPEN")).strip("`").upper() == "OPEN")]
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


# --- IMP-384: closing a change gap by citing the baseline --------------------------------------

_CITE_PATH = re.compile(r"`([^`]+)`")
_CITE_QUOTE = re.compile(r'"([^"]*)"|\u201c([^\u201d]*)\u201d')
MIN_BASELINE_QUOTE = 20


def _squash(text: str) -> str:
    return " ".join(text.split())


def _resolved_keys(row: dict) -> set[Path]:
    found: set[Path] = set()
    for key in list(row.get("paths") or []) + list(row.get("copies") or []):
        try:
            found.add(Path(str(key)).resolve())
        except (OSError, ValueError):
            continue
    return found


def _baseline_row_finding(project_id: str, change_id: str, rel: str, target: Path, es: bool) -> str | None:
    """IMP-400: only a registered source with the baseline role proves that something already exists."""
    from .source_registry import is_harvested, row_role
    from .sources import load_source_manifest

    def msg(spanish: str, english: str) -> str:
        return spanish if es else english

    manifest = load_source_manifest(project_id)
    rows = [row for row in manifest.get("registry", []) if target in _resolved_keys(row)]
    if not rows:
        return msg(
            f"by_baseline: `{rel}` no está registrada como fuente. Registrala con /sources {project_id} --load {rel} --role linea_de_base --change {change_id}",
            f"by_baseline: `{rel}` is not registered as a source. Register it with /sources {project_id} --load {rel} --role linea_de_base --change {change_id}",
        )
    current = [row for row in rows if row.get("validity", "current") == "current"]
    usable = current or rows
    # Prefer a row that is a baseline; otherwise report the first row's problem.
    row = next((r for r in usable if row_role(r) == "linea_de_base"), usable[0])
    role = row_role(row)
    sid = row.get("id", "")
    if role is None:
        harvested = is_harvested(row)
        if harvested:
            return msg(
                f"by_baseline: `{rel}` es la lectura de Sentinel (harvest), no la línea de base: citá el documento que la respalda.",
                f"by_baseline: `{rel}` is Sentinel's reading (harvest), not the baseline: cite the document that backs it.",
            )
    if role is None:
        return msg(
            f"by_baseline: `{rel}` ({sid}) no está registrada como línea de base (tipo {row.get('kind')}). Registrala con /sources {project_id} --load {rel} --role linea_de_base --change {change_id}",
            f"by_baseline: `{rel}` ({sid}) is not registered as the baseline (kind {row.get('kind')}). Register it with /sources {project_id} --load {rel} --role linea_de_base --change {change_id}",
        )
    if role != "linea_de_base":
        return msg(
            f"by_baseline: `{rel}` ({sid}) está registrada como {role}: sólo la línea de base prueba que algo ya existe.",
            f"by_baseline: `{rel}` ({sid}) is registered as {role}: only the baseline proves that something already exists.",
        )
    validity = row.get("validity", "current")
    if validity != "current":
        newer = row.get("superseded_by") or row.get("replacement")
        if newer:
            return msg(
                f"by_baseline: `{rel}` ({sid}) fue reemplazada por {newer}: citá la vigente.",
                f"by_baseline: `{rel}` ({sid}) was replaced by {newer}: cite the current one.",
            )
        if validity == "retired":
            return msg(
                f"by_baseline: `{rel}` ({sid}) fue retirada: citá la vigente.",
                f"by_baseline: `{rel}` ({sid}) was retired: cite the current one.",
            )
        return msg(
            f"by_baseline: `{rel}` ({sid}) no está vigente ({validity}): citá la vigente.",
            f"by_baseline: `{rel}` ({sid}) is not current ({validity}): cite the current one.",
        )
    return None


def validate_baseline_citation(base: Path, project_id: str, change_id: str, evidence: str) -> str | None:
    """None when the evidence cites a baseline file and quotes it literally; else the finding, in the change's language.

    The baseline is what sits under `00_raw/`; the notes of any change are not baseline. Nothing outside
    the workspace is read, and an unreadable file is a finding, never an exception.
    """
    changes = list_changes(project_id)
    change = changes.get(change_id)
    es = change_language(project_id, change) == "es" if change else True

    def msg(spanish: str, english: str) -> str:
        return spanish if es else english

    path_match = _CITE_PATH.search(evidence or "")
    quote_match = _CITE_QUOTE.search(evidence or "")
    if not path_match or not quote_match:
        return msg(
            "by_baseline pide en la evidencia una ruta bajo 00_raw/ entre acentos graves y una frase literal entre comillas.",
            "by_baseline needs, in the evidence, a path under 00_raw/ in backticks and a literal quote in quotation marks.",
        )
    rel = path_match.group(1).strip()
    quote = _squash(quote_match.group(1) if quote_match.group(1) is not None else quote_match.group(2))
    try:
        raw_root = (base / "00_raw").resolve()
        target = (base / rel).resolve()
        inside = target.is_relative_to(raw_root) and target != raw_root
    except (OSError, ValueError):
        inside = False
    if not inside:
        return msg(
            f"by_baseline: la ruta {rel!r} no está bajo 00_raw/ del workspace.",
            f"by_baseline: the path {rel!r} is not under the workspace 00_raw/.",
        )
    notes = set()
    for entry in changes.values():
        try:
            notes.add((base / str(entry.get("source", ""))).resolve())
        except (OSError, ValueError):
            continue
    if target in notes:
        return msg(
            f"by_baseline: {rel!r} es la nota de un cambio, no la línea de base.",
            f"by_baseline: {rel!r} is the note of a change, not the baseline.",
        )
    row_finding = _baseline_row_finding(project_id, change_id, rel, target, es)
    if row_finding:
        return row_finding
    if len(quote) < MIN_BASELINE_QUOTE:
        return msg(
            f"by_baseline: la frase citada tiene menos de {MIN_BASELINE_QUOTE} caracteres.",
            f"by_baseline: the quoted text is shorter than {MIN_BASELINE_QUOTE} characters.",
        )
    try:
        content = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return msg(
            f"by_baseline: {rel!r} no se puede leer como texto UTF-8.",
            f"by_baseline: {rel!r} cannot be read as UTF-8 text.",
        )
    if "\x00" in content:
        return msg(f"by_baseline: {rel!r} es binario, no texto.", f"by_baseline: {rel!r} is binary, not text.")
    if quote not in _squash(content):
        return msg(
            f"by_baseline: la frase no aparece literal en {rel!r} (se compara sin diferencias de espacios, respetando mayúsculas).",
            f"by_baseline: the quote is not literal (verbatim) in {rel!r} (compared with whitespace collapsed, case kept).",
        )
    return None


# --- IMP-410: confirming a question an earlier decision already answers ------------------------

def accept_prior_decision(project_id: str, change_id: str, gap_id: str) -> dict:
    """`/gaps --change --id --accept-prior`: the question closes with what was already decided, and says so."""
    from .crosses.record import _save_change_gaps
    from .decision_memory import index_change_decisions
    from .prior_decisions import load_priors, save_priors
    from .readiness_verdict import change_next_step

    change = get_change(project_id, change_id)
    es = change_language(project_id, change) == "es"
    base = workspace_path(project_id)
    path = change_gaps_path(base, change_id)
    rows = [g for g in parse_gap_rows(path.read_text(encoding="utf-8-sig")) if g.get("id") != "NONE"] if path.exists() else []
    row = next((g for g in rows if g.get("id") == gap_id), None)
    priors = load_priors(base, change_id)
    entry = priors.get(gap_id)
    if row is None or not entry:
        raise InputError(f"{gap_id} no tiene una decisión previa para aceptar" if es else f"{gap_id} has no earlier decision to accept")
    if str(row.get("status", "")).strip("`").upper() == "CLOSED":
        raise InputError(f"{gap_id} ya está cerrada" if es else f"{gap_id} is already closed")
    if entry.get("match") != "linked":
        raise InputError(
            f"{gap_id}: la sugerencia de memoria o el pedido a Diseño no se aceptan solos: respondela con /resolve-gaps" if es
            else f"{gap_id}: a memory suggestion or a request to Design is not accepted as is: answer it with /resolve-gaps")
    from .prior_decisions import live_prior_answer, prior_note

    answer = live_prior_answer(project_id, change_id, entry)
    if answer is None:
        raise InputError(
            f"{gap_id}: la decisión previa ya no está vigente (se reabrió o se retiró): respondela de nuevo" if es
            else f"{gap_id}: the earlier decision no longer stands (reopened or withdrawn): answer it again")
    warnings: list[str] = []
    if " ".join(answer.split()) != " ".join(str(entry.get("answer", "")).split()):
        entry = {**entry, "answer": answer, "changed": True}
        warnings.append(f"la decisión previa cambió: se cierra con la respuesta vigente de {entry.get('prior')}" if es
                        else f"the earlier decision changed: it closes with the current answer of {entry.get('prior')}")
    from .compilers.change_brief import _answers

    if gap_id in _answers(base, change):
        warnings.append("ya hay una respuesta escrita para esta pregunta: el brief toma esa y no la decisión previa" if es
                        else "an answer file already exists for this question: the brief takes it, not the earlier decision")
    prior = str(entry.get("prior", ""))
    row["status"] = "CLOSED"
    row["resolution_note"] = f"confirmado por el BA: rige lo decidido en {prior}" if es else f"confirmed by the BA: what {prior} decided governs"
    priors[gap_id] = {**entry, "accepted_at": utc_now()}
    save_priors(base, change_id, priors)  # first: the render reads it to drop the prefill
    _save_change_gaps(project_id, change_id, path, rows)
    index_change_decisions(project_id, change_id)
    from . import decision_conflicts

    conflicts = decision_conflicts.refresh_decision_conflicts(project_id, change_id)  # IMP-414
    return {
        "project_id": project_id, "change_id": change_id, "action": "accept_prior", "gap_id": gap_id, "prior": prior,
        "match": entry.get("match"), "basis": entry.get("basis"), "option": entry.get("option", ""),
        **({"warnings": warnings} if warnings else {}),
        **({"decision_conflicts": conflicts["opened"]} if conflicts["opened"] else {}),
        **({"conflicts_retired": conflicts["retired"]} if conflicts["retired"] else {}),
        "gap_counts": get_change(project_id, change_id).get("gap_counts"),
        "next_step": change_next_step(project_id, change_id),
        "message": f"{change_id}: {gap_id} cerrada con lo decidido en {prior}" if es else f"{change_id}: {gap_id} closed with what {prior} decided",
    }
