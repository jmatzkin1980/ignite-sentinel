"""IMP-269 (H17a′): the series guide, closing a release, and NOT READY by inheritance.

* `/split --close rN --evidence PATH --ba NAME --tech TEAM` closes a release of the
  confirmed series. It requires every story of the release in Done (its own
  lifecycle, in its mirror) and the evidence of its closing check (a local file,
  fingerprinted). The close is recorded in `partition.json` and survives later
  confirmations and moves while the release exists.
* **NOT READY by inheritance** [A38]: a release that depends hard on a release that
  is not closed is NOT READY, whatever its own state, with the dependency named.
* **The guide** `02_requirements/series/release-guide.md` (and `/view --artifact
  release-guide`): the waves, each release with its type, goal, edges with their
  why, status (closed, waiting on a dependency, open), the frozen contracts, the
  coverage matrix (each §6.1 line, `C-NN` and `P-N` with its owner) and what has no
  source, counted against what is declared absent (sketches and §6.2).

The guide reads the partition, the proposal, the series map and each release's
mirror state; it keeps nothing of its own and recompiles with the series.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .release_split import PARTITION_FILE, ReleaseSplitError, _dicts, _s
from .split_proposal import PROPOSAL_DIR, PROPOSAL_FILE, release_order

GUIDE_FILE = "release-guide.md"
WORK_DIR = ".series_work"

COPY = {
    "en": {
        "title": "Series guide — {project}", "intro": "Read-only guide of the confirmed release series. It recompiles with the series.",
        "waves": "Waves", "wave": "Wave {n}", "releases": "Releases",
        "header": "| Release | Type | Wave | Goal | Depends on | Status |",
        "closed": "closed {date} (evidence `{evidence}`)", "waiting": "NOT READY by inheritance: depends hard on {deps}, not closed",
        "open": "open", "stage": "open; its own verdict: `/status --release {rid}` (stage {stage})", "not_derived": "open; not derived yet (`/specs --release {rid}`)",
        "edges": "Edges and why", "edge": "- {rid} → {target} ({strength}{contract}): {why}",
        "contracts": "Frozen contracts", "contracts_header": "| Contract | Name | Kind | Created by |",
        "coverage": "Coverage matrix", "coverage_header": "| Family | Unit | Owner |",
        "no_source": "[NO SOURCE]", "sources": "Without source and declared absent",
        "no_source_count": "- Without source (not routed or no longer in the brief): {n}",
        "absent_count": "- Declared absent (sketches outside the horizon and §6.2 out of scope): {n}",
        "nothing": "nothing",
    },
    "es": {
        "title": "Guía de la serie — {project}", "intro": "Guía de solo lectura de la serie confirmada. Se recompila con la serie.",
        "waves": "Olas", "wave": "Ola {n}", "releases": "Releases",
        "header": "| Release | Tipo | Ola | Objetivo | Depende de | Estado |",
        "closed": "cerrado {date} (evidencia `{evidence}`)", "waiting": "NOT READY por herencia: depende en duro de {deps}, sin cerrar",
        "open": "abierto", "stage": "abierto; su veredicto: `/status --release {rid}` (etapa {stage})", "not_derived": "abierto; todavía sin derivar (`/specs --release {rid}`)",
        "edges": "Aristas y porqué", "edge": "- {rid} → {target} ({strength}{contract}): {why}",
        "contracts": "Contratos congelados", "contracts_header": "| Contrato | Nombre | Tipo | Lo crea |",
        "coverage": "Matriz de cobertura", "coverage_header": "| Familia | Unidad | Dueño |",
        "no_source": "[SIN FUENTE]", "sources": "Sin fuente y ausentes declarados",
        "no_source_count": "- Sin fuente (sin release asignado o que ya no está en el brief): {n}",
        "absent_count": "- Ausentes declarados (esbozos fuera del horizonte y §6.2 fuera de alcance): {n}",
        "nothing": "nada",
    },
}
FAMILY_LABELS = {"scope_6_1": "§6.1", "build_items": "§9 C-NN", "screens": "P-N"}


def _series(base: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    from .core.io import read_json

    series = base.joinpath(*PROPOSAL_DIR)
    partition = read_json(series / PARTITION_FILE, None)
    if not isinstance(partition, dict) or partition.get("status") != "confirmed":
        raise ReleaseSplitError("this needs a confirmed release series; run /split --confirm first")
    stored = read_json(series / PROPOSAL_FILE, None)
    payload = stored.get("proposal") if isinstance(stored, dict) else None
    return partition, payload if isinstance(payload, dict) else {}


def hard_dependencies(payload: dict[str, Any], rid: str) -> list[str]:
    release = next((r for r in _dicts(payload.get("releases")) if _s(r.get("id")) == rid), {})
    return [_s(e.get("release")) for e in _dicts(release.get("depends_on")) if (_s(e.get("strength")) or "hard") == "hard"]


def inherited_blockers(main_base: Path, rid: str) -> list[str]:
    """[A38] The hard dependencies of `rid` that are not closed, as verdict blockers. No series, none."""
    try:
        partition, payload = _series(Path(main_base))
    except ReleaseSplitError:
        return []
    closed = partition.get("closed") or {}
    waiting = [dep for dep in hard_dependencies(payload, rid) if dep not in closed]
    return [f"NOT READY by inheritance: {rid} depends hard on {dep}, which is not closed (/split --close {dep})." for dep in waiting]


def _mirror(base: Path, project_id: str, rid: str) -> Path:
    return base / WORK_DIR / rid / "workspaces" / project_id


def release_stories(base: Path, project_id: str, rid: str) -> dict[str, str]:
    """Story id → lifecycle status of a release, from its mirror."""
    from .core.io import read_json

    mirror = _mirror(base, project_id, rid)
    state = read_json(mirror / "state.json", {}) if (mirror / "state.json").exists() else {}
    lifecycle = state.get("story_lifecycle") or {}
    stories = sorted(p.stem for p in (mirror / "04_backlog").glob("US-*.md")) if (mirror / "04_backlog").is_dir() else []
    return {sid: str((lifecycle.get(sid) or {}).get("status", "Draft")) for sid in stories}


def close_release(project_id: str, rid: str, evidence: str, ba: str, tech: str, today: str | None = None) -> dict[str, Any]:
    """Close a release: every story Done and the evidence of its closing check. Nothing changes on a refusal."""
    from .core.io import write_text
    from .core.paths import workspace_path
    from .core.time import utc_now

    if not _s(ba) or not _s(tech):
        raise ReleaseSplitError("/split --close records who closes: --ba NAME and --tech NAME are both required")
    base = workspace_path(project_id)
    partition, payload = _series(base)
    if rid not in (partition.get("releases") or []):
        raise ReleaseSplitError(f"{rid} is not a release of the confirmed series")
    closed = dict(partition.get("closed") or {})
    if rid in closed:
        raise ReleaseSplitError(f"{rid} is already closed ({closed[rid].get('date')})")
    proof = Path(evidence) if evidence else None
    if proof is None or not proof.is_file():
        raise ReleaseSplitError("/split --close needs --evidence PATH: a local file with the result of the release's closing check")
    stories = release_stories(base, project_id, rid)
    if not stories:
        raise ReleaseSplitError(f"{rid} has no stories yet: derive it (/specs, /backlog --release {rid}) and build it before closing")
    pending = sorted(sid for sid, status in stories.items() if status != "Done")
    if pending:
        raise ReleaseSplitError(f"{rid} cannot close: stories not Done: {', '.join(pending)} (/story-status --release {rid})")
    closed[rid] = {"date": today or utc_now()[:10], "evidence": proof.as_posix(),
                   "evidence_sha256": hashlib.sha256(proof.read_bytes()).hexdigest(),
                   "closed_by": {"ba": _s(ba), "technical_team": _s(tech)}, "stories": sorted(stories)}
    partition["closed"] = dict(sorted(closed.items(), key=lambda kv: release_order(kv[0])))
    target = base.joinpath(*PROPOSAL_DIR, PARTITION_FILE)
    write_text(target, json.dumps(partition, ensure_ascii=False, indent=2) + "\n")
    write_release_guide(project_id)
    unblocked = sorted((_s(r.get("id")) for r in _dicts(payload.get("releases"))
                        if rid in hard_dependencies(payload, _s(r.get("id")))
                        and not inherited_blockers(base, _s(r.get("id")))), key=release_order)
    return {"status": "closed", "release": rid, "closed": closed[rid], "unblocked": unblocked,
            "guide": base.joinpath(*PROPOSAL_DIR, GUIDE_FILE).as_posix()}


def release_status(base: Path, project_id: str, payload: dict[str, Any], partition: dict[str, Any], rid: str) -> dict[str, Any]:
    from .core.io import read_json

    closed = (partition.get("closed") or {}).get(rid)
    waiting = [d for d in hard_dependencies(payload, rid) if d not in (partition.get("closed") or {})]
    mirror_state = _mirror(base, project_id, rid) / "state.json"
    stage = (read_json(mirror_state, {}) or {}).get("readiness_stage") if mirror_state.exists() else None
    if closed:
        status = "closed"
    elif waiting:
        status = "waiting"
    else:
        status = "open"
    return {"id": rid, "status": status, "closed": closed, "waiting_on": waiting, "stage": stage,
            "derived": (base / "03_specs" / rid).is_dir()}


def render_release_guide(project_id: str, partition: dict[str, Any], payload: dict[str, Any], statuses: dict[str, dict[str, Any]],
                         families: dict[str, list[dict[str, Any]]], absent: int, language: str = "en") -> str:
    copy = COPY.get(language, COPY["en"])
    releases = sorted(_dicts(payload.get("releases")), key=lambda r: release_order(_s(r.get("id"))))
    out = [f"# {copy['title'].format(project=project_id)}", "", copy["intro"], "", f"## {copy['waves']}", ""]
    for wave, ids in (partition.get("waves") or {}).items():
        out.append(f"- {copy['wave'].format(n=wave)}: {', '.join(ids)}")
    out += ["", f"## {copy['releases']}", "", copy["header"], "|---|---|---|---|---|---|"]
    for release in releases:
        rid = _s(release.get("id"))
        st = statuses[rid]
        if st["status"] == "closed":
            status = copy["closed"].format(date=st["closed"].get("date", ""), evidence=Path(str(st["closed"].get("evidence", ""))).name)
        elif st["status"] == "waiting":
            status = copy["waiting"].format(deps=", ".join(st["waiting_on"]))
        elif st["derived"]:
            status = copy["stage"].format(rid=rid, stage=st["stage"] or "?")
        else:
            status = copy["not_derived"].format(rid=rid)
        deps = ", ".join(_s(e.get("release")) for e in _dicts(release.get("depends_on"))) or copy["nothing"]
        out.append(f"| {rid} {_s(release.get('name'))} | {_s(release.get('type'))} | {int(release.get('wave', 0) or 0)} | "
                   f"{_s(release.get('goal'))} | {deps} | {status} |")
    out += ["", f"## {copy['edges']}", ""]
    edges = [copy["edge"].format(rid=_s(r.get("id")), target=_s(e.get("release")), strength=_s(e.get("strength")) or "hard",
                                 contract=f", {_s(e.get('consumes'))}" if _s(e.get("consumes")) else "", why=_s(e.get("why")))
             for r in releases for e in _dicts(r.get("depends_on"))]
    out += edges or [f"- {copy['nothing']}"]
    out += ["", f"## {copy['contracts']}", "", copy["contracts_header"], "|---|---|---|---|"]
    for k in sorted(_dicts(payload.get("contracts")), key=lambda k: int(_s(k.get("id"))[1:] or 0)):
        out.append(f"| {_s(k.get('id'))} | {_s(k.get('name'))} | {_s(k.get('kind'))} | {_s(k.get('created_by'))} |")
    out += ["", f"## {copy['coverage']}", "", copy["coverage_header"], "|---|---|---|"]
    no_source = 0
    for family, members in families.items():
        for member in members:
            owners = ", ".join(member["owners"]) if member["owners"] else copy["no_source"]
            no_source += 0 if member["owners"] else 1
            out.append(f"| {FAMILY_LABELS.get(family, family)} | {member['unit'].replace('|', '/')} | {owners} |")
    out += ["", f"## {copy['sources']}", "", copy["no_source_count"].format(n=no_source + int(partition.get("unresolved", 0) or 0)),
            copy["absent_count"].format(n=absent)]
    return "\n".join(out).rstrip() + "\n"


def write_release_guide(project_id: str) -> Path:
    from .brief_model import parse_brief
    from .core.io import write_text
    from .core.paths import workspace_path
    from .gap_resolution import project_language
    from .release_series import _plain, assign_owners

    base = workspace_path(project_id)
    partition, payload = _series(base)
    text = (base / "02_requirements" / "project-brief.md").read_text(encoding="utf-8")
    assignment = assign_owners(text, payload)
    lines = text.splitlines()
    families: dict[str, list[dict[str, Any]]] = {}
    for family, rows in assignment["families"].items():
        families[family] = [{"unit": _plain(lines[i])[:90], "owners": sorted(assignment["owners"].get(i, []), key=release_order)}
                            for i in rows]
    model = parse_brief(text)
    out_of_scope = 0
    section = model.sections.get("6.2")
    if section is not None:
        out_of_scope = sum(1 for line in lines[section.start + 1:section.end] if line.lstrip().startswith("- ") and "[[" in line)
    absent = out_of_scope + sum(len(_dicts(s.get("contains"))) for s in _dicts(payload.get("sketches")))
    statuses = {rid: release_status(base, project_id, payload, partition, rid) for rid in partition.get("releases") or []}
    partition = {**partition, "unresolved": len(assignment["unresolved"])}
    target = base.joinpath(*PROPOSAL_DIR, GUIDE_FILE)
    write_text(target, render_release_guide(project_id, partition, payload, statuses, families, absent, project_language(project_id)))
    return target


def release_items(project_id: str) -> list[dict[str, Any]]:
    """IMP-247's release axis: one item per release with its verdict (inherited, closed or its own)."""
    from .core.paths import workspace_path
    from .release_scope import release_verdict

    base = workspace_path(project_id)
    try:
        partition, payload = _series(base)
    except ReleaseSplitError:
        return []
    items = []
    for release in sorted(_dicts(payload.get("releases")), key=lambda r: release_order(_s(r.get("id")))):
        rid = _s(release.get("id"))
        st = release_status(base, project_id, payload, partition, rid)
        if st["status"] == "closed":
            verdict, note = "READY", "closed"
        elif st["status"] == "waiting":
            verdict, note = "NOT_READY", f"depends hard on {', '.join(st['waiting_on'])}, not closed"
        else:
            own = release_verdict(project_id, rid)
            verdict, note = (own["verdict"], "own verdict") if own else ("NOT_READY", "not derived yet")
        items.append({"id": rid, "kind": "release", "label": f"{rid} {_s(release.get('name'))}", "verdict": verdict,
                      "note": note, "empty": False, "stories": []})
    return items
