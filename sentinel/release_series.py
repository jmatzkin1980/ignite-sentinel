"""IMP-267a (H17a): compiling the release series, the index and one brief per release.

The whole brief v2 stays the source. After `/split --confirm` the series is compiled
from it and from the confirmed partition:

* `02_requirements/series/index.md`: the project in one page, the series table, the
  waves, the frozen contracts, the id map, the sketches outside the horizon and the
  sync findings.
* `02_requirements/r<N>/project-brief.md`: one self-contained brief per release. It is
  the whole brief, where every unit another release owns becomes a tombstone
  ("➡ lives in rN" / "➡ vive en rN"), in every section where it appears. Shared lines
  (no release owns them) stay in every release. §0.1 declares the release in the
  series (type, goal, closing check, edges, inherited gaps, contracts built and used…).
* The build items `C-NN` become local to each release (`C-01`…), mapped in the index.
* A unit whose owner changed since the previous compilation is REATRIBUIDO
  (reattributed) in the tombstone and in the index.
* A unit of a family (§6.1, `C-NN`, `P-N`) that no release owns any more (the brief
  grew since the confirmation) is "not routed" everywhere until the series is
  proposed again.

The SAD and the prototype are not split: each release reads them whole. Releases
sort in natural order (`r2` < `r2.1` < `r10`). A series does not mix v1 and v2
[A43]. Integrity (IMP-255: marks and forbidden values) and anchors (IMP-258) run on
each release brief, and their findings go to the index and `series_report.json`.

Recompiling is the synchronization: any mutating command that changes the brief
recompiles an existing series (`refresh_series_if_stale`). A workspace without a
confirmed partition is never touched.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .brief_model import parse_brief
from .release_split import CLIENT_GAP_ID, PARTITION_FILE, ReleaseSplitError, _dicts, _s
from .split_proposal import PROPOSAL_DIR, PROPOSAL_FILE, _norm, release_order

INDEX_FILE = "index.md"
MAP_FILE = "series_map.json"
REPORT_FILE = "series_report.json"
TOMBSTONE = "➡"
_CITE_RE = re.compile(r"\[\[[^\]]+\]\]")
_C_RE = re.compile(r"`(C-\d{2,})`")

COPY = {
    "en": {
        "lives": "lives in {rid}", "reattributed": "REATRIBUIDO (reattributed) to {rid}", "outside": "outside the horizon: {name}",
        "not_routed": "not routed to any release: propose the series again",
        "block": "Release in the series", "nothing": "nothing", "yes": "yes", "no": "no",
        "tombstones": "{n} units live in other releases; see `02_requirements/series/index.md`",
        "not_split": "the SAD and the prototype are not split: this release reads them whole",
        "not_split_index": "The SAD and the prototype are not split: every release reads them whole.",
        "index_title": "Release series — {project}",
        "status": "Confirmed by the BA {ba} and the technical team {tech}. The client's confirmation is pending (`{gap}`).",
        "source": "Compiled from `02_requirements/project-brief.md` (sha256 `{sha}`) and the confirmed partition.",
        "stale": "The brief changed since the confirmation: the series was recompiled from it; check the sync findings.",
        "one_page": "The project in one page", "core": "Core", "variations": "Variations", "criteria": "Cut criteria",
        "base": "Cross-cutting base", "series": "The series",
        "series_header": "| Release | Name | Type | Wave | Goal | Depends on | Brief |",
        "waves": "Waves", "wave": "Wave {n}", "contracts": "Frozen contracts",
        "contracts_header": "| Contract | Name | Kind | Created by | sha256 |",
        "id_map": "Id map", "id_header": "| Release | Local id | Brief id |",
        "sketches": "Outside the horizon (sketches)", "reattributions": "Reattributed units",
        "reattr_row": "- {unit}: {old} → {new}", "not_split_title": "Not split",
        "findings": "Sync findings", "no_findings": "No findings: every unit resolves and every release brief passes integrity and anchors.",
        "unresolved": "- {where}: the unit no longer resolves in the brief ({quote}).",
        "unrouted": "- {family}: {unit} is not routed to any release.",
        "release_finding": "- {rid}: {finding}",
        "retired": "- {rid}: no longer in the confirmed partition; its old brief `02_requirements/{rid}/project-brief.md` is kept and no longer compiled.",
    },
    "es": {
        "lives": "vive en {rid}", "reattributed": "REATRIBUIDO a {rid}", "outside": "fuera del horizonte: {name}",
        "not_routed": "sin release asignado: volver a proponer la serie",
        "block": "Release en la serie", "nothing": "nada", "yes": "sí", "no": "no",
        "tombstones": "{n} unidades viven en otros releases; ver `02_requirements/series/index.md`",
        "not_split": "el SAD y el prototipo no se parten: este release los lee enteros",
        "not_split_index": "El SAD y el prototipo no se parten: cada release los lee enteros.",
        "index_title": "Serie de releases — {project}",
        "status": "Confirmada por el BA {ba} y el equipo técnico {tech}. La confirmación del cliente está pendiente (`{gap}`).",
        "source": "Compilada desde `02_requirements/project-brief.md` (sha256 `{sha}`) y la partición confirmada.",
        "stale": "El brief cambió desde la confirmación: la serie se recompiló desde él; revisar los hallazgos de sincronización.",
        "one_page": "El proyecto en una página", "core": "Núcleo", "variations": "Variaciones", "criteria": "Criterios de corte",
        "base": "Base transversal", "series": "La serie",
        "series_header": "| Release | Nombre | Tipo | Ola | Objetivo | Depende de | Brief |",
        "waves": "Olas", "wave": "Ola {n}", "contracts": "Contratos congelados",
        "contracts_header": "| Contrato | Nombre | Tipo | Lo crea | sha256 |",
        "id_map": "Mapa de ids", "id_header": "| Release | Id local | Id del brief |",
        "sketches": "Fuera del horizonte (esbozos)", "reattributions": "Unidades reatribuidas",
        "reattr_row": "- {unit}: {old} → {new}", "not_split_title": "No se parte",
        "findings": "Hallazgos de sincronización", "no_findings": "Sin hallazgos: cada unidad resuelve y cada brief de release pasa integridad y anclas.",
        "unresolved": "- {where}: la unidad ya no resuelve en el brief ({quote}).",
        "unrouted": "- {family}: {unit} no está asignada a ningún release.",
        "release_finding": "- {rid}: {finding}",
        "retired": "- {rid}: ya no está en la partición confirmada; su brief anterior `02_requirements/{rid}/project-brief.md` se conserva y ya no se compila.",
    },
}


def _plain(line: str) -> str:
    return " ".join(_CITE_RE.sub("", line).strip().lstrip("-").split())


def _key(line: str) -> str:
    return _norm(_plain(line))


def _span(model, place: str) -> list[int]:
    """0-based body line indexes of a place, sub-places included (headings excluded)."""
    rows: set[int] = set()
    for sid, section in model.sections.items():
        if sid == place or sid.startswith(place + "."):
            rows.update(range(section.start + 1, section.end))
    return sorted(rows)


def assign_owners(brief_text: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Which release (or sketch) owns each unit line of the brief. Pure."""
    model = parse_brief(brief_text)
    lines = brief_text.splitlines()
    owners: dict[int, list[str]] = {}
    unresolved: list[dict[str, str]] = []
    holders = [(_s(r.get("id")), _dicts(r.get("contains"))) for r in _dicts(payload.get("releases"))]
    holders += [(f"sketch:{_s(s.get('name'))}", _dicts(s.get("contains"))) for s in _dicts(payload.get("sketches"))]
    item_lines = {m: i for i, line in enumerate(lines) for m in _C_RE.findall(line) if model.section_id_at_line(i + 1).startswith("9")}
    for holder, units in holders:
        for index, unit in enumerate(units, start=1):
            item = _s(unit.get("item"))
            found: list[int] = []
            if item.startswith("C-"):
                found = [item_lines[item]] if item in item_lines else []
            elif item.startswith("P-"):
                found = [i for i in _span(model, "4") if re.search(rf"\b{re.escape(item)}\b", lines[i])]
            else:
                quote = _norm(unit.get("quote", ""))
                found = [i for i in _span(model, _s(unit.get("place")))
                         if quote and not lines[i].lstrip().startswith("#") and quote in _norm(_plain(lines[i]))]
            if not found:
                unresolved.append({"where": f"{holder} contains[{index}]", "quote": item or _s(unit.get("quote"))[:80]})
            for i in found:
                if holder not in owners.setdefault(i, []):
                    owners[i].append(holder)
    families: dict[str, list[int]] = {
        "scope_6_1": [i for i in _span(model, "6.1") if lines[i].lstrip().startswith("- ") and "[[" in lines[i]],
        "build_items": sorted(item_lines.values()),
        "screens": [i for i in _span(model, "4") if re.search(r"\bP-\d+\b", lines[i])],
    }
    unrouted = [{"family": fam, "line": i, "unit": _plain(lines[i])[:80]} for fam, rows in families.items()
                for i in rows if i not in owners]
    return {"owners": owners, "unresolved": unresolved, "unrouted": unrouted}


def _local_items(lines: list[str], owners: dict[int, list[str]], rid: str) -> dict[str, str]:
    owned = sorted({m for i, holder in owners.items() if rid in holder for m in _C_RE.findall(lines[i])},
                   key=lambda c: int(c.split("-")[1]))
    return {orig: f"C-{n:02d}" for n, orig in enumerate(owned, start=1)}


def _edge_text(edge: dict[str, Any]) -> str:
    consumes = f", {_s(edge.get('consumes'))}" if _s(edge.get("consumes")) else ""
    return f"{_s(edge.get('release'))} ({_s(edge.get('strength')) or 'hard'}{consumes}: {_s(edge.get('why'))})"


def _series_block(payload: dict[str, Any], release: dict[str, Any], tombstones: int, copy: dict[str, str]) -> list[str]:
    rid = _s(release.get("id"))
    nothing = copy["nothing"]
    contracts = _dicts(payload.get("contracts"))
    built = [f"{_s(k.get('id'))} {_s(k.get('name'))} ({_s(k.get('kind'))})" for k in contracts if _s(k.get("created_by")) == rid]
    extended = [f"{_s(k.get('id'))} {_s(k.get('name'))}" for k in contracts if rid in [_s(x) for x in k.get("extended_by") or []]]
    used = sorted({_s(e.get("consumes")) for e in _dicts(release.get("depends_on")) if _s(e.get("consumes"))})
    inherits = sorted({_s(row.get("gap")) for row in _dicts(payload.get("inheritance")) if _s(row.get("release")) == rid}
                      | {_s(g) for g in release.get("needs") or []})
    relaxed = [f"{_s(r.get('rule'))} → {_s(r.get('restored_in'))}" for r in _dicts(payload.get("relaxed_rules")) if _s(r.get("release")) == rid]
    restores = [f"{_s(r.get('rule'))} ({_s(r.get('release'))})" for r in _dicts(payload.get("relaxed_rules")) if _s(r.get("restored_in")) == rid]
    rows = [
        ("release", f"{rid} — {_s(release.get('name'))}"),
        ("release_type", _s(release.get("type"))),
        ("wave", str(int(release.get("wave", 0) or 0))),
        ("release_goal", _s(release.get("goal"))),
        ("closing_check", _s(release.get("closing_check")) or nothing),
        ("depends_on", "; ".join(_edge_text(e) for e in _dicts(release.get("depends_on"))) or nothing),
        ("enables", "; ".join(_edge_text(e) for e in _dicts(release.get("enables"))) or nothing),
        ("inherits", ", ".join(f"`{g}`" for g in inherits) or nothing),
        ("builds", "; ".join(built + [f"{x} (extends)" for x in extended]) or nothing),
        ("uses_contracts", ", ".join(used) or nothing),
    ]
    if _s(release.get("condition")):
        rows.append(("condition", f"`{_s(release.get('condition'))}`"))
    spike = release.get("spike") if isinstance(release.get("spike"), dict) else None
    if spike:
        rows.append(("spike", f"{' / '.join(_s(q) for q in spike.get('questions') or [])} — time-box {_s(spike.get('time_box'))}"))
    if _s(release.get("interleave_subtype")):
        rows.append(("interleave_subtype", _s(release.get("interleave_subtype"))))
    if relaxed or restores:
        rows.append(("restored_in", "; ".join(relaxed + [f"restores {x}" for x in restores])))
    if _s(release.get("type")) == "integrator":
        consumption = "; ".join(f"{_s(r.get('piece'))} ← {_s(r.get('uses'))} ({_s(r.get('from'))})" for r in _dicts(payload.get("integrator_consumption")))
        rows.append(("integrator_consumption", consumption or nothing))
    for key in ("releasable", "value_type", "changes_actor", "surfaces", "non_technical_start_condition"):
        if key in release:
            value = release[key]
            rows.append((key, ", ".join(map(str, value)) if isinstance(value, list) else str(value)))
    rows.append(("suggested_scope", copy["yes"] if release.get("suggested_scope") else copy["no"]))
    rows.append(("tombstones", copy["tombstones"].format(n=tombstones)))
    rows.append(("sad_and_prototype", copy["not_split"]))
    return [f"#### {copy['block']}", ""] + [f"- `{key}`: {value}" for key, value in rows] + [""]


def compile_release_brief(brief_text: str, payload: dict[str, Any], release_id: str, assignment: dict[str, Any],
                          language: str = "en", reattributed: dict[int, str] | None = None,
                          project_id: str = "") -> tuple[str, dict[str, str]]:
    """One release brief and its local id map (brief id → local id). Pure."""
    copy = COPY.get(language, COPY["en"])
    lines = brief_text.splitlines()
    owners: dict[int, list[str]] = assignment["owners"]
    unrouted = {row["line"] for row in assignment["unrouted"]}
    releases = {_s(r.get("id")): r for r in _dicts(payload.get("releases"))}
    release = releases[release_id]
    local = _local_items(lines, owners, release_id)
    out: list[str] = []
    tombstones = 0
    for i, line in enumerate(lines):
        holder = owners.get(i)
        if (holder and release_id not in holder) or i in unrouted:
            indent = line[: len(line) - len(line.lstrip())]
            if i in unrouted:
                where = copy["not_routed"]
            elif reattributed and i in reattributed and reattributed[i] in holder:
                where = copy["reattributed"].format(rid=reattributed[i])
            elif holder[0].startswith("sketch:"):
                where = copy["outside"].format(name=holder[0].split(":", 1)[1])
            else:
                where = copy["lives"].format(rid=", ".join(sorted(holder, key=release_order)))
            if line.lstrip().startswith("|"):  # a table row keeps its columns
                cells = line.strip().strip("|").split("|")
                out.append(f"{indent}| {TOMBSTONE} {where}: {_plain(cells[0])[:60]} |" + " → |" * (len(cells) - 1))
                tombstones += 1
                continue
            there = ""
            ids = _C_RE.findall(line)
            if ids and holder and len(holder) == 1 and not holder[0].startswith("sketch:") and i not in unrouted:
                there = f" → {holder[0]} `{_local_items(lines, owners, holder[0]).get(ids[0], ids[0])}`"
            out.append(f"{indent}- {TOMBSTONE} {where}: {_plain(line)[:90]}{there}")
            tombstones += 1
            continue
        if holder and release_id in holder:
            line = _C_RE.sub(lambda m: f"`{local.get(m.group(1), m.group(1))}`", line)
        out.append(line)
    title = next((n for n, line in enumerate(out) if line.startswith("# ")), None)
    if title is not None:
        out[title] = f"{out[title]} · {release_id} {_s(release.get('name'))}".rstrip()
    model = parse_brief("\n".join(out))
    legend = model.sections.get("0.1")
    block = _series_block(payload, release, tombstones, copy)
    if legend is not None:
        at = legend.start + 1
        while at < len(out) and not out[at].strip():
            at += 1
        out[at:at] = block
    else:
        out[(title or 0) + 1:(title or 0) + 1] = [""] + block
    return "\n".join(out).rstrip() + "\n", local


def _integrity(text: str, gaps: dict[str, dict[str, str]], registry: list[dict[str, Any]]) -> list[str]:
    from .anchors import anchor_findings
    from .brief_integrity import mark_findings, value_findings

    return mark_findings(text, gaps) + value_findings(text) + anchor_findings(text, registry)


def render_index(project_id: str, payload: dict[str, Any], partition: dict[str, Any], brief_sha: str,
                 id_maps: dict[str, dict[str, str]], reattributions: list[dict[str, str]],
                 sync: dict[str, Any], language: str = "en") -> str:
    copy = COPY.get(language, COPY["en"])
    releases = sorted(_dicts(payload.get("releases")), key=lambda r: release_order(_s(r.get("id"))))
    who = partition.get("confirmed_by") or {}
    out = [f"# {copy['index_title'].format(project=project_id)}", "",
           copy["status"].format(ba=who.get("ba", ""), tech=who.get("technical_team", ""), gap=CLIENT_GAP_ID), "",
           copy["source"].format(sha=brief_sha[:12]), ""]
    if partition.get("brief_sha256") and partition.get("brief_sha256") != brief_sha:
        out += [copy["stale"], ""]
    core = payload.get("core") if isinstance(payload.get("core"), dict) else {}
    out += [f"## {copy['one_page']}", "", f"- {copy['core']}: {_s(core.get('text'))} (§{_s((core.get('anchor') or {}).get('place'))})"]
    for v in _dicts(payload.get("variations")):
        out.append(f"- {copy['variations']}: {_s(v.get('id'))} {_s(v.get('text'))}")
    for c in _dicts(payload.get("criteria")):
        out.append(f"- {copy['criteria']}: {_s(c.get('id'))} — {_s(c.get('why'))}")
    base = payload.get("base") if isinstance(payload.get("base"), dict) else {}
    for piece in _dicts(base.get("pieces")):
        out.append(f"- {copy['base']}: {_s(piece.get('piece'))} — {_s(piece.get('reason'))}")
    out += ["", f"## {copy['series']}", "", copy["series_header"], "|---|---|---|---|---|---|---|"]
    for r in releases:
        rid = _s(r.get("id"))
        deps = ", ".join(_s(e.get("release")) for e in _dicts(r.get("depends_on"))) or copy["nothing"]
        out.append(f"| {rid} | {_s(r.get('name'))} | {_s(r.get('type'))} | {int(r.get('wave', 0) or 0)} | {_s(r.get('goal'))} | {deps} | `02_requirements/{rid}/project-brief.md` |")
    out += ["", f"## {copy['waves']}", ""]
    for wave, ids in (partition.get("waves") or {}).items():
        out.append(f"- {copy['wave'].format(n=wave)}: {', '.join(ids)}")
    out += ["", f"## {copy['contracts']}", "", copy["contracts_header"], "|---|---|---|---|---|"]
    frozen = partition.get("contracts_frozen") or {}
    for k in sorted(_dicts(payload.get("contracts")), key=lambda k: int(_s(k.get("id"))[1:] or 0)):
        kid = _s(k.get("id"))
        out.append(f"| {kid} | {_s(k.get('name'))} | {_s(k.get('kind'))} | {_s(k.get('created_by'))} | `{str(frozen.get(kid, ''))[:12]}` |")
    out += ["", f"## {copy['id_map']}", "", copy["id_header"], "|---|---|---|"]
    for r in releases:
        rid = _s(r.get("id"))
        for orig, loc in sorted(id_maps.get(rid, {}).items(), key=lambda kv: int(kv[1].split("-")[1])):
            out.append(f"| {rid} | `{loc}` | `{orig}` |")
    sketches = _dicts(payload.get("sketches"))
    if sketches:
        out += ["", f"## {copy['sketches']}", ""]
        out += [f"- {_s(s.get('name'))}: {_s(s.get('goal'))} ({_s(s.get('pattern'))})" for s in sketches]
    if reattributions:
        out += ["", f"## {copy['reattributions']}", ""]
        out += [copy["reattr_row"].format(**row) for row in reattributions]
    out += ["", f"## {copy['not_split_title']}", "", f"- {copy['not_split_index']}", "", f"## {copy['findings']}", ""]
    rows = [copy["unresolved"].format(**u) for u in sync["unresolved"]]
    rows += [copy["unrouted"].format(**u) for u in sync["unrouted"]]
    rows += [copy["release_finding"].format(rid=rid, finding=f) for rid, found in sync["integrity"].items() for f in found]
    rows += [copy["retired"].format(rid=rid) for rid in sync.get("retired", [])]
    out += rows or [copy["no_findings"]]
    return "\n".join(out).rstrip() + "\n"


def compile_series(project_id: str) -> dict[str, Any]:
    """Compile the index and every release brief from the brief v2 and the confirmed partition."""
    from .brief_integrity import _gap_rows
    from .core.io import read_json, write_text
    from .core.paths import workspace_path
    from .gap_resolution import project_language
    from .split import brief_hash

    base = workspace_path(project_id)
    series = base.joinpath(*PROPOSAL_DIR)
    partition = read_json(series / PARTITION_FILE, None)
    if not isinstance(partition, dict) or partition.get("status") != "confirmed":
        raise ReleaseSplitError("the series compiles only from a confirmed partition; run /split --confirm")
    stored = read_json(series / PROPOSAL_FILE, None)
    payload = stored.get("proposal") if isinstance(stored, dict) else None
    if not isinstance(payload, dict) or stored.get("proposal_sha256") != partition.get("proposal_sha256"):
        raise ReleaseSplitError("the stored proposal is not the one confirmed; run /split --confirm again")
    brief_path = base / "02_requirements" / "project-brief.md"
    text = brief_path.read_text(encoding="utf-8")
    if parse_brief(text).version != 2:
        raise ReleaseSplitError("a series does not mix v1 and v2 [A43]: the brief is v1; recompile it as v2")
    language = project_language(project_id)
    sha = brief_hash(brief_path)
    assignment = assign_owners(text, payload)
    lines = text.splitlines()
    previous = read_json(series / MAP_FILE, None)
    previous = previous if isinstance(previous, dict) else {}
    old_owner = previous.get("owners") or {}
    owners_by_key = {_key(lines[i]): sorted(h, key=release_order) for i, h in assignment["owners"].items()}
    reattributed: dict[int, str] = {}
    reattributions: list[dict[str, str]] = []
    for i, holder in sorted(assignment["owners"].items()):
        before = old_owner.get(_key(lines[i]))
        now = sorted(holder, key=release_order)
        if before and before != now:
            reattributed[i] = now[0]
            reattributions.append({"unit": _plain(lines[i])[:80], "old": ", ".join(before), "new": ", ".join(now)})
    gaps = _gap_rows(base)
    manifest = read_json(base / "00_raw" / "source_manifest.json", {}) or {}
    registry = manifest.get("registry", []) if isinstance(manifest, dict) else []
    releases = sorted((_s(r.get("id")) for r in _dicts(payload.get("releases"))), key=release_order)
    id_maps: dict[str, dict[str, str]] = {}
    integrity: dict[str, list[str]] = {}
    paths: list[str] = []
    for rid in releases:
        brief, local = compile_release_brief(text, payload, rid, assignment, language, reattributed, project_id)
        id_maps[rid] = local
        found = _integrity(brief, gaps, registry)
        if found:
            integrity[rid] = found
        target = base / "02_requirements" / rid / "project-brief.md"
        write_text(target, brief)
        paths.append(target.as_posix())
    # a release the confirmed partition no longer has keeps its file (never deleted) and is listed as retired
    retired = sorted(set(previous.get("releases") or []) - set(releases), key=release_order)
    sync = {"unresolved": assignment["unresolved"], "unrouted": [{k: v for k, v in u.items() if k != "line"} for u in assignment["unrouted"]],
            "integrity": integrity, "retired": retired}
    write_text(series / INDEX_FILE, render_index(project_id, payload, partition, sha, id_maps, reattributions, sync, language))
    write_text(series / MAP_FILE, json.dumps({"brief_sha256": sha, "proposal_sha256": partition.get("proposal_sha256"),
                                              "releases": releases, "id_map": id_maps, "owners": dict(sorted(owners_by_key.items()))},
                                             ensure_ascii=False, indent=2) + "\n")
    report = {"status": "compiled", "brief_sha256": sha, "releases": releases, "reattributions": reattributions, **sync}
    write_text(series / REPORT_FILE, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return {"status": "compiled", "index": (series / INDEX_FILE).as_posix(), "releases": paths,
            "findings": len(sync["unresolved"]) + len(sync["unrouted"]) + sum(len(v) for v in integrity.values()),
            "reattributions": len(reattributions)}


def refresh_series_if_stale(project_id: str) -> dict[str, Any] | None:
    """Recompile an existing series when the brief changed. No confirmed partition, nothing happens."""
    from .core.io import read_json, write_text
    from .core.paths import workspace_path
    from .split import brief_hash

    base = workspace_path(project_id)
    series = base.joinpath(*PROPOSAL_DIR)
    partition = read_json(series / PARTITION_FILE, None)
    brief_path = base / "02_requirements" / "project-brief.md"
    if not isinstance(partition, dict) or partition.get("status") != "confirmed" or not brief_path.is_file():
        return None
    current = read_json(series / MAP_FILE, None)
    if isinstance(current, dict) and current.get("brief_sha256") == brief_hash(brief_path):
        return None
    try:
        return compile_series(project_id)
    except ReleaseSplitError as exc:
        write_text(series / REPORT_FILE, json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False, indent=2) + "\n")
        return {"status": "blocked", "reason": str(exc)}
