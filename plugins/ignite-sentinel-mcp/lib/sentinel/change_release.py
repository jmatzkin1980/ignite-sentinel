"""IMP-429 (H27 inc 7d): the units of a change split by the release that builds them.

The confirmed series of a change (`02_requirements/CHG-nnn/series/`) says which §6.1 surfaces and build items each
release holds; the `SPEC-U` units of the change (`03_specs/CHG-nnn/units/`) say which surfaces they touch. A release
owns the units whose surfaces fall in its surfaces (or whose `trace_ids` name one of its `C-NN`). A unit owned by two
releases, or by none, stops the derivation before anything is written: the series is the truth and no release is
picked in silence.

Each derivation records which releases were closed when it was made: a release closed since makes it old (its
delivered units must read as preserved), and a release closes only while its own derivation is current. The folder
`04_backlog/CHG-nnn/rN/` holds `stories.md` (the ids of its stories, linked to their canonical `04_backlog/US-nnn.md`)
and `SLICE-PLAN.md`; never copies of the stories.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from .core.io import remove, write_text
from .errors import InputError
from .workspace import workspace_path

LAYERS = ("03_specs", "04_backlog")
STORIES_FILE = "stories.md"
_ITEM = re.compile(r"^C-\d+$", re.IGNORECASE)
_STORY_LINK = re.compile(r"\[(US-\d+)\]\(\.\./\.\./US-\d+\.md\)")

TEXT = {
    "es": {
        "twice": "{unit} tiene dueño en dos releases ({a} y {b}) en la serie de {cid}: no se eligió ninguna; nada se escribió.",
        "never": "{unit} no tiene dueño: ninguna release de la serie de {cid} contiene sus superficies; nada se escribió.",
        "not_release": "{rid} no es una release de la serie de {cid} (las releases son {releases}).",
        "closed": "{rid} está cerrada en la serie de {cid}: no se deriva de nuevo.",
        "next_move": "/split {pid} --change {cid} --move --unit <C-NN> --from <rA> --to <rB> --reason \"...\" --ba \"...\" --tech \"...\"",
        "next_pick": "Elegí una de las releases abiertas: {open}.",
        "next_specs": "Revisá {path}; después /backlog {pid} --change {cid} --release {rid} deriva las historias de {rid}.",
        "next_done": "/next {pid} --change {cid}",
        "close_specs": "{rid} no se puede cerrar: sus unidades no están al día ({why}); derivala de nuevo con /specs {pid} --change {cid} --release {rid} y /backlog {pid} --change {cid} --release {rid}",
        "close_backlog": "{rid} no se puede cerrar: sus historias no son las de sus unidades actuales; derivalas de nuevo con /backlog {pid} --change {cid} --release {rid}",
        "why_old": "cambió la serie o el cambio",
        "why_closed": "se cerró {closed} después de derivarla",
        "stories_title": "Historias de {rid} — {cid}",
        "stories_intro": "Índice de las historias de {rid} del cambio {cid}. Cada historia vive solo en `04_backlog/US-NNN.md`: su estado y sus criterios se leen ahí. El plan de cortes de {rid} está en `SLICE-PLAN.md`.",
        "stories_header": "| Historia | Título |",
    },
    "en": {
        "twice": "{unit} has an owner in two releases ({a} and {b}) in the series of {cid}: none was picked; nothing was written.",
        "never": "{unit} has no owner: no release of the series of {cid} holds its surfaces; nothing was written.",
        "not_release": "{rid} is not a release of the series of {cid} (the releases are {releases}).",
        "closed": "{rid} is already closed in the series of {cid}: it is not derived again.",
        "next_move": "/split {pid} --change {cid} --move --unit <C-NN> --from <rA> --to <rB> --reason \"...\" --ba \"...\" --tech \"...\"",
        "next_pick": "Pick one of the open releases: {open}.",
        "next_specs": "Review {path}; then /backlog {pid} --change {cid} --release {rid} derives the stories of {rid}.",
        "next_done": "/next {pid} --change {cid}",
        "close_specs": "{rid} cannot close: its units are not current ({why}); derive it again with /specs {pid} --change {cid} --release {rid} and /backlog {pid} --change {cid} --release {rid}",
        "close_backlog": "{rid} cannot close: its stories are not those of its current units; derive them again with /backlog {pid} --change {cid} --release {rid}",
        "why_old": "the series or the change moved",
        "why_closed": "{closed} closed after it was derived",
        "stories_title": "Stories of {rid} — {cid}",
        "stories_intro": "Index of the stories of {rid} of the change {cid}. Each story lives only in `04_backlog/US-NNN.md`: read its status and criteria there. The slice plan of {rid} is `SLICE-PLAN.md`.",
        "stories_header": "| Story | Title |",
    },
}


class ChangeReleaseError(InputError):
    """A unit of the change with two owners or none, a release the series does not have, a closed release."""


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


def _text(project_id: str, change_id: str) -> dict[str, str]:
    from .changes import change_language, get_change

    return TEXT.get(change_language(project_id, get_change(project_id, change_id)), TEXT["es"])


def _series(project_id: str, change_id: str) -> tuple[list[str], dict[str, dict[str, set[str]]], dict[str, Any]]:
    """(release ids in partition order, per release its folded surfaces and C-NN ids, the partition)."""
    from .release_guide import _series as read_series

    partition, payload = read_series(workspace_path(project_id), change_id)
    held: dict[str, dict[str, set[str]]] = {}
    for release in payload.get("releases") or []:
        if not isinstance(release, dict):
            continue
        rid = str(release.get("id", "")).strip()
        surfaces: set[str] = set()
        items: set[str] = set()
        for entry in release.get("contains") or []:
            if not isinstance(entry, dict):
                continue
            if entry.get("item"):
                items.add(str(entry["item"]).strip().upper())
            elif entry.get("quote"):
                surfaces.add(_fold(entry["quote"]))
        held[rid] = {"surfaces": surfaces, "items": items}
    releases = [str(rid) for rid in partition.get("releases") or []]
    return releases, held, partition


def _owners(unit: dict[str, Any], releases: list[str], held: dict[str, dict[str, set[str]]]) -> tuple[list[str], bool]:
    """(the releases that own the unit, True when only a containment of the surface found them)."""
    surfaces = [_fold(s) for s in unit.get("surfaces") or [] if str(s).strip()]
    items = {str(t).strip().upper() for t in unit.get("trace_ids") or [] if _ITEM.match(str(t).strip())}
    found: list[str] = []
    for rid in releases:
        mine = held.get(rid, {"surfaces": set(), "items": set()})
        if items & mine["items"] or any(s in mine["surfaces"] for s in surfaces):
            found.append(rid)
    if found:
        return found, False
    # no exact surface: a quote that contains the surface (or the other way round); the result reports it (M4)
    return [rid for rid in releases
            if any(s and q and (s in q or q in s) for s in surfaces for q in held.get(rid, {}).get("surfaces", set()))], True


ROUTES_FILE = "unit_routes.json"


def unit_routes(project_id: str, change_id: str) -> dict[str, str]:
    """B-04: the units the BA routed to another release than the one their surface says (`/split --move --unit SPEC-U-nnn`)."""
    from .core.io import read_json
    from .series_scope import series_dir

    stored = read_json(series_dir(workspace_path(project_id), change_id) / ROUTES_FILE, None)
    routes = stored.get("routes") if isinstance(stored, dict) else None
    return {str(unit): str(rid) for unit, rid in routes.items()} if isinstance(routes, dict) else {}


def _assign(project_id: str, change_id: str) -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    from .compilers.change_backlog import read_change_units

    text = _text(project_id, change_id)
    releases, held, _partition = _series(project_id, change_id)
    routes = unit_routes(project_id, change_id)
    result: dict[str, list[str]] = {rid: [] for rid in releases}
    contained: list[dict[str, str]] = []
    for unit in read_change_units(project_id, change_id):
        if routes.get(unit["id"]) in result:  # a unit the BA routed: that release owns it, whatever its surface says
            result[routes[unit["id"]]].append(unit["id"])
            continue
        owners, by_containment = _owners(unit, releases, held)
        if len(owners) > 1:
            raise ChangeReleaseError(
                text["twice"].format(unit=unit["id"], a=owners[0], b=owners[1], cid=change_id),
                next_step=text["next_move"].format(pid=project_id, cid=change_id))
        if not owners:
            raise ChangeReleaseError(
                text["never"].format(unit=unit["id"], cid=change_id),
                next_step=text["next_move"].format(pid=project_id, cid=change_id))
        result[owners[0]].append(unit["id"])
        if by_containment:
            contained.append({"unit": unit["id"], "surface": ", ".join(unit.get("surfaces") or []), "release": owners[0]})
    return result, contained


def release_units(project_id: str, change_id: str) -> dict[str, list[str]]:
    """rid -> the `SPEC-U` ids it builds, in the partition's order; refuses a unit with two owners or none."""
    return _assign(project_id, change_id)[0]


def closed_releases(project_id: str, change_id: str) -> list[str]:
    """The releases of the change's series that are closed, in the partition's order."""
    releases, _held, partition = _series(project_id, change_id)
    closed = partition.get("closed") or {}
    return [rid for rid in releases if rid in closed]


def closed_owner_units(project_id: str, change_id: str) -> dict[str, list[str]]:
    """B-04: closed release -> the units of the change it owns by surface that it did not deliver (they arrived after its close).

    `_assign` owns by surface and does not look at the close; the units a release delivered are frozen in `partition.json`.
    A close made before 7d froze none: nothing is said about it."""
    releases, _held, partition = _series(project_id, change_id)
    closed = partition.get("closed") or {}
    if not closed:
        return {}
    try:
        owned = release_units(project_id, change_id)
    except (ChangeReleaseError, OSError):
        return {}  # a unit with two owners or none is reported on its own
    found: dict[str, list[str]] = {}
    for rid in releases:
        frozen = (closed.get(rid) or {}).get("units") if rid in closed else None
        if not isinstance(frozen, list):
            continue
        late = [u for u in owned.get(rid, []) if u not in {str(f) for f in frozen}]
        if late:
            found[rid] = late
    return found


def route_unit(project_id: str, change_id: str, unit_id: str, target: str) -> None:
    """Route one unit of the change to `target` (an open release of the series): `unit_routes.json` of the series."""
    import json

    from .core.io import write_text
    from .series_scope import series_dir

    routes = unit_routes(project_id, change_id)
    routes[unit_id] = target
    write_text(series_dir(workspace_path(project_id), change_id) / ROUTES_FILE,
               json.dumps({"routes": dict(sorted(routes.items()))}, ensure_ascii=False, indent=2) + "\n")


def closed_others(project_id: str, change_id: str, rid: str) -> list[str]:
    """The closed releases of the series other than `rid`, in the partition's order: what a derivation of `rid` preserves."""
    return [r for r in closed_releases(project_id, change_id) if r != rid]


def delivered_units(project_id: str, change_id: str, rid: str, owned: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    """Closed release -> the units it delivered (frozen at its close; the current owners for a close made before 7d)."""
    _releases, _held, partition = _series(project_id, change_id)
    closed = partition.get("closed") or {}
    found: dict[str, list[str]] = {}
    for r in closed_others(project_id, change_id, rid):
        frozen = (closed.get(r) or {}).get("units")
        if not isinstance(frozen, list):
            if owned is None:
                owned = release_units(project_id, change_id)
            frozen = owned.get(r, [])
        if frozen:
            found[r] = [str(u) for u in frozen]
    return found


def check_release(project_id: str, change_id: str, rid: str) -> list[str]:
    """Refuse a release the series does not have, or a closed one; returns the releases of the series."""
    text = _text(project_id, change_id)
    releases, _held, _partition = _series(project_id, change_id)
    if rid not in releases:
        raise ChangeReleaseError(text["not_release"].format(rid=rid, cid=change_id, releases=", ".join(releases)),
                                 next_step=text["next_pick"].format(open=", ".join(releases)))
    closed = closed_releases(project_id, change_id)
    if rid in closed:
        open_ones = [r for r in releases if r not in closed]
        raise ChangeReleaseError(text["closed"].format(rid=rid, cid=change_id),
                                 next_step=text["next_pick"].format(open=", ".join(open_ones))
                                 if open_ones else text["next_done"].format(pid=project_id, cid=change_id))
    return releases


def release_story_ids(base: Path, change_id: str, rid: str) -> list[str]:
    """The stories a release of the change lists in `04_backlog/CHG-nnn/rN/stories.md`, in its order."""
    index = base / "04_backlog" / change_id / rid / STORIES_FILE
    if not index.is_file():
        return []
    return list(dict.fromkeys(_STORY_LINK.findall(index.read_text(encoding="utf-8"))))


def write_release_stories(project_id: str, change_id: str, rid: str, stories: list[dict[str, Any]]) -> Path:
    """`04_backlog/CHG-nnn/rN/stories.md`: the ids of the release's stories, each linked to its canonical file."""
    from .core.markdown import table_cell

    text = _text(project_id, change_id)
    folder = release_dir(project_id, change_id, rid, "04_backlog")
    for legacy in folder.glob("US-*.md"):  # copies written before the index (never read: the index is the membership)
        remove(legacy)
    rows = [f"| [{s['id']}](../../{s['id']}.md) | {table_cell(str(s.get('title', '')), 160)} |" for s in stories]
    body = [f"# {text['stories_title'].format(rid=rid, cid=change_id)}", "",
            text["stories_intro"].format(rid=rid, cid=change_id), "", text["stories_header"], "|---|---|", *rows, ""]
    path = folder / STORIES_FILE
    write_text(path, "\n".join(body))
    return path


def release_dir(project_id: str, change_id: str, rid: str, layer: str) -> Path:
    if layer not in LAYERS:
        raise ValueError(f"layer must be one of {LAYERS}: {layer}")
    return workspace_path(project_id) / layer / change_id / rid


def derive_release_specs(project_id: str, change_id: str, rid: str, whole: dict[str, Any]) -> dict[str, Any]:
    """Write `03_specs/CHG/rid/{specs.md,units/}` from the change's compiled units (`whole` is that compile's result)."""
    from .compilers.change_spec_doc import change_spec_context, render_change_spec_doc
    from .compilers.change_functionalities import change_functionalities
    from .compilers.change_backlog import read_change_units
    from .workspace import read_state, update_state

    check_release(project_id, change_id, rid)
    every, contained = _assign(project_id, change_id)  # refuses before anything is written
    mine = every[rid]
    base = workspace_path(project_id)
    folder = release_dir(project_id, change_id, rid, "03_specs")
    units_dir = folder / "units"
    units_dir.mkdir(parents=True, exist_ok=True)
    source = base / "03_specs" / change_id / "units"
    for uid in mine:
        write_text(units_dir / f"{uid}.md", (source / f"{uid}.md").read_text(encoding="utf-8"))
    for stale in units_dir.glob("SPEC-U-*.md"):
        if stale.stem not in mine:
            remove(stale)
    units = [u for u in read_change_units(project_id, change_id) if u["id"] in mine]
    ears = {u["ears"][0] for u in units if u["ears"]}
    funs = [f for f in change_functionalities(project_id, change_id) if any(r in ears for r in f["rows"])]
    # what a closed release already delivered reads as preserved behavior, never as new units (M3: closed in any order)
    delivered = delivered_units(project_id, change_id, rid, every)
    write_text(folder / "specs.md",
               render_change_spec_doc(change_spec_context(project_id, change_id, units, funs, delivered), change_id))
    # I1: the closed releases this derivation preserves; one closed later makes it old
    changes = read_state(project_id).get("changes", {})
    changes[change_id].setdefault("specs_releases", {})[rid] = {"closed": closed_others(project_id, change_id, rid)}
    update_state(project_id, changes=changes)
    return {
        "project_id": project_id, "change_id": change_id, "status": "derived", "release": rid, "units": mine,
        "path": (folder / "specs.md").relative_to(base).as_posix(),
        "functionalities": [f["id"] for f in funs],
        "containment": [c for c in contained if c["release"] == rid],
        "next_step": _text(project_id, change_id)["next_specs"].format(  # B-30: about this release, not the whole change
            path=(folder / "specs.md").relative_to(base).as_posix(), pid=project_id, cid=change_id, rid=rid),
    }


def specs_sha256(project_id: str, change_id: str, rid: str) -> str:
    import hashlib

    path = release_dir(project_id, change_id, rid, "03_specs") / "specs.md"
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def closed_since(project_id: str, change_id: str, change: dict[str, Any], rid: str) -> list[str]:
    """The releases closed after `rid`'s specs were derived (I1): their delivered units are missing as preserved."""
    stamp = ((change.get("specs_releases") or {}).get(rid) or {}).get("closed") or []
    return [r for r in closed_others(project_id, change_id, rid) if r not in stamp]


def _specs_why(project_id: str, change_id: str, change: dict[str, Any], rid: str, owned: dict[str, list[str]] | None) -> str:
    """"" when the units of `rid` are derived and current, "new" when never derived, "old" when the series or the change moved,
    "closed" when a release closed after the derivation (its delivered units are not preserved in it yet)."""
    from .compilers.change_backlog import specs_currency

    base = workspace_path(project_id)
    folder = release_dir(project_id, change_id, rid, "03_specs")
    if not (folder / "specs.md").is_file():
        return "new"
    if (not change.get("specs") or not (base / "03_specs" / change_id / "specs.md").is_file()
            or specs_currency(project_id, change_id) != "current" or owned is None):
        return "old"
    held = sorted(p.stem for p in (folder / "units").glob("SPEC-U-*.md"))
    if held != sorted(owned.get(rid, [])):
        return "old"
    whole = base / "03_specs" / change_id / "units"
    for uid in held:
        if (folder / "units" / f"{uid}.md").read_bytes() != (whole / f"{uid}.md").read_bytes():
            return "old"
    return "closed" if closed_since(project_id, change_id, change, rid) else ""


def _backlog_why(project_id: str, change_id: str, change: dict[str, Any], rid: str, owned: dict[str, list[str]] | None) -> str:
    """"" when the stories of `rid` come from exactly its units, "new" when it has none, "old" when they do not."""
    from .core.markdown import parse_frontmatter

    base = workspace_path(project_id)
    record = (change.get("backlog_releases") or {}).get(rid)
    folder = release_dir(project_id, change_id, rid, "04_backlog")
    if not isinstance(record, dict) or not (folder / "SLICE-PLAN.md").is_file():
        return "new"
    if record.get("specs_sha256") and record["specs_sha256"] != specs_sha256(project_id, change_id, rid):
        return "old"  # the specs of the release were derived again after its stories
    sources: set[str] = set()
    for sid in record.get("stories") or []:
        path = base / "04_backlog" / f"{sid}.md"
        if not path.is_file():
            return "old"
        front = parse_frontmatter(path.read_text(encoding="utf-8"))
        grouped = front.get("source_units")
        if isinstance(grouped, list) and grouped:
            sources.update(str(u).strip() for u in grouped)
        elif isinstance(front.get("source_unit"), str):
            sources.add(front["source_unit"].strip())
    sources.discard("")
    wanted = set((owned or {}).get(rid, [])) - set(record.get("dropped_units") or [])
    return "" if owned is not None and sources == wanted else "old"


def series_step(project_id: str, change_id: str, change: dict[str, Any]) -> dict[str, Any] | None:
    """H27 inc 7d: where a change with a confirmed series stands, walking its open releases in order.

    None: the change has no confirmed series (the plain `specs`/`backlog` steps apply). Else the first open release
    that is missing its specs (`key` "specs"), its backlog ("backlog") or its closing ("done"); `key` "" when every release
    is closed. A closed release is never asked for again."""
    from .release_split import ReleaseSplitError

    try:
        releases, _held, partition = _series(project_id, change_id)
    except ReleaseSplitError:
        return None
    closed = partition.get("closed") or {}
    try:
        owned: dict[str, list[str]] | None = release_units(project_id, change_id)
    except (ChangeReleaseError, OSError):
        owned = None
    late = closed_owner_units(project_id, change_id)
    first_open = next((rid for rid in releases if rid not in closed), "")
    if late and first_open:  # B-04: a unit that landed on a closed release is moved to an open one before that one is built
        return {"key": "series_closed_units", "release": first_open, "units": late}
    for rid in releases:
        if rid in closed:
            continue
        why = _specs_why(project_id, change_id, change, rid, owned)
        if why:
            step = {"key": "specs", "release": rid, "why": why}
            if why == "closed":
                step["closed_since"] = closed_since(project_id, change_id, change, rid)
            return step
        why = _backlog_why(project_id, change_id, change, rid, owned)
        if why:
            return {"key": "backlog", "release": rid, "why": why}
        stories = _statuses(project_id, change_id, rid)
        pending = [sid for sid, status in stories.items() if status != "Done"]
        return {"key": "done", "release": rid, "total": len(stories), "done": len(stories) - len(pending),
                "pending": pending}
    return {"key": ""}


def _statuses(project_id: str, change_id: str, rid: str) -> dict[str, str]:
    from .release_guide import release_stories

    return release_stories(workspace_path(project_id), project_id, rid, change_id)


def stale_derivations(project_id: str, change_id: str) -> list[dict[str, str]]:
    """The open releases already derived whose specs or stories are old (what /validate --change reports)."""
    from .changes import get_change

    change = get_change(project_id, change_id)
    releases, _held, partition = _series(project_id, change_id)
    closed = partition.get("closed") or {}
    try:
        owned: dict[str, list[str]] | None = release_units(project_id, change_id)
    except (ChangeReleaseError, OSError):
        return []  # a unit with two owners or none: /validate reports that, not every release
    found: list[dict[str, str]] = []
    for rid in releases:
        if rid in closed:
            continue
        why = _specs_why(project_id, change_id, change, rid, owned)
        if why in ("old", "closed"):
            found.append({"release": rid, "layer": "specs", "why": why,
                          "closed_since": ", ".join(closed_since(project_id, change_id, change, rid))})
        elif not why and _backlog_why(project_id, change_id, change, rid, owned) == "old":
            found.append({"release": rid, "layer": "backlog", "why": "old", "closed_since": ""})
    return found


def close_gate(project_id: str, change_id: str, rid: str) -> list[str]:
    """I4: a release of a change closes only while its specs and its stories are current. Returns its units (frozen at close)."""
    from .changes import get_change
    from .release_split import ReleaseSplitError

    text = _text(project_id, change_id)
    change = get_change(project_id, change_id)
    try:
        owned: dict[str, list[str]] | None = release_units(project_id, change_id)
    except ChangeReleaseError as exc:
        raise ReleaseSplitError(str(exc), next_step=exc.next_step, gate=True) from exc
    why = _specs_why(project_id, change_id, change, rid, owned)
    if why:
        reason = (text["why_closed"].format(closed=", ".join(closed_since(project_id, change_id, change, rid)))
                  if why == "closed" else text["why_old"])
        raise ReleaseSplitError(text["close_specs"].format(rid=rid, pid=project_id, cid=change_id, why=reason),
                                next_step=f"/specs {project_id} --change {change_id} --release {rid}", gate=True)
    if _backlog_why(project_id, change_id, change, rid, owned):
        raise ReleaseSplitError(text["close_backlog"].format(rid=rid, pid=project_id, cid=change_id),
                                next_step=f"/backlog {project_id} --change {change_id} --release {rid}", gate=True)
    return list((owned or {}).get(rid, []))
