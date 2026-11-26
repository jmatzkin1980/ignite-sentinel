"""IMP-406 task 5: verification sampling of a confirmed extraction.

A reproducible sample of the confirmed elements goes to a file the BA (or a fresh agent) reads against the
request; each `difiere` takes its element back to proposed with a `verificacion_difiere` mark.
"""
from __future__ import annotations

import math
import random
import re
from pathlib import Path
from typing import Any

from ..change_requirements import load_change_ears
from ..changes import change_language, resolve_scope
from ..core.io import read_json, write_json, write_text
from ..core.paths import workspace_path
from ..errors import InputError
from . import extraction_dir
from .coverage import extraction_fingerprint
from .inventory import _read_text, _split_lines, element_lines, load_inventory, span_text
from .lines import format_ranges
from .proposals import _now, load_proposals

DEFAULT_SAMPLE = 10
SAMPLE_SHARE = 0.05  # the default sample is 5 % of what is confirmed, at least DEFAULT_SAMPLE
VERIFY_ABOVE = 100  # an extraction with more elements than this asks for a verification
COVERS_SHARE = 0.8  # a verification covers the confirmations while it saw at least this share of what is confirmed now


def sample_size(confirmed: int) -> int:
    return max(DEFAULT_SAMPLE, math.ceil(SAMPLE_SHARE * confirmed))

_RESULT = re.compile(
    r"^\s*[-*]\s*(?P<id>[^\s:]+)\s*:\s*(?P<verdict>igual|difiere|same|differs)\b\s*"
    r"(?:(?:—|-|:)\s*)?(?P<note>.+?)?\s*$",
    re.IGNORECASE,
)
_LOOSE = re.compile(r"^\s*[-*]\s*(?P<id>[^\s:]+)\s*:\s*\S")
_VERDICTS = {"igual": "igual", "same": "igual", "difiere": "difiere", "differs": "difiere"}
_RESULTS_HEADING = re.compile(r"^##\s+(?:Resultados|Results)\s*$", re.MULTILINE)
_EXT_SOURCE = re.compile(r"`EXT:([^`]+)`")


def verification_path(base: Path, change_id: str) -> Path:
    return extraction_dir(base, change_id) / "verification.json"


def _load(base: Path, change_id: str) -> dict:
    data = read_json(verification_path(base, change_id), None)
    if not isinstance(data, dict) or not isinstance(data.get("runs"), list):
        return {"schema_version": 1, "change_id": change_id, "runs": []}
    return data


def _es(project_id: str, change_id: str) -> bool:
    return resolve_scope(project_id, change_id).language == "es"


def _confirmed_ids(inventory: dict, items: dict) -> list[str]:
    by_id = {e["id"]: e for e in inventory.get("elements", [])}
    return sorted(
        element_id for element_id, item in items.items()
        if isinstance(item, dict) and item.get("status") == "confirmed"
        and element_id in by_id and item.get("element_sha") == by_id[element_id].get("sha")
    )


def _entry(project_id: str, change_id: str, base: Path, element: dict, item: dict, es: bool,
           rows: dict[str, list[dict]]) -> list[str]:
    first, last = element_lines(element)
    treatment = str(item.get("treatment", ""))
    word = "líneas" if es else "lines"
    lines = [
        f"### {element['id']}",
        f"<!-- {element['source_id']} · {element.get('path', '')} · {word} {first}-{last} · {treatment} -->",
    ]
    quote = str(item.get("quote", "")).strip()
    if quote:
        lines.append(f"- {'Cita' if es else 'Quote'}: \"{quote}\"")
    if treatment == "requisito":
        for row in rows.get(element["id"], []):
            lines.append(f"- {'Enunciado' if es else 'Statement'} ({'fila' if es else 'row'} {row['id']}, "
                         f"Delta {row['delta']}): {row['statement']}")
    elif treatment == "seccion":
        declared = format_ranges(item.get("lines") or []) or f"{first}-{last}"
        text = _read_text(base, str(element.get("path", "")))
        source = _split_lines(text) if text is not None else []
        lines.append(f"- {'Sección' if es else 'Section'}: {item.get('section') or ''}")
        lines.append(f"- {'Texto literal' if es else 'Literal text'} ({word} {declared}):")
        literal = span_text(source, element.get("spans", []), element.get("cspan"))
        lines.extend(f"  > {line}" for line in literal.split("\n"))
    else:
        lines.append(f"- {'Motivo' if es else 'Reason'}: {item.get('reason') or ''}")
    lines.append("")
    return lines


def start_verification(project_id: str, change_id: str, sample: int | None = None) -> dict:
    """Draw the sample of confirmed elements, write its file and open the run.

    The size is `sample`, else max(10, 5 % of the confirmed elements). Elements confirmed without a line check
    (`legacy_ids`) are drawn first: they are the ones nothing has measured."""
    es = _es(project_id, change_id)
    if sample is not None and sample < 1:
        raise InputError("--sample debe ser 1 o más" if es else "--sample must be 1 or more")
    base = workspace_path(project_id)
    inventory = load_inventory(base, change_id) or {}
    items = load_proposals(base, change_id)["items"]
    ids = _confirmed_ids(inventory, items)
    if not ids:
        raise InputError(
            f"{change_id} no tiene elementos confirmados para verificar" if es
            else f"{change_id} has no confirmed elements to verify"
        )
    fingerprint = extraction_fingerprint(base, change_id)
    size = min(sample_size(len(ids)) if sample is None else sample, len(ids))
    draw = random.Random(int(fingerprint, 16) if fingerprint else 0)
    legacy = [i for i in ids if not items[i].get("lines")]
    picked = draw.sample(legacy, min(size, len(legacy)))
    rest = [i for i in ids if i not in picked]
    picked += draw.sample(rest, size - len(picked))
    by_id = {e["id"]: e for e in inventory.get("elements", [])}
    rows: dict[str, list[dict]] = {}
    for row in load_change_ears(project_id, change_id):
        found = _EXT_SOURCE.match(str(row.get("source", "")))
        if found:
            rows.setdefault(found.group(1), []).append(row)
    store = _load(base, change_id)
    number = max((int(r.get("n", 0)) for r in store["runs"]), default=0) + 1
    suffix = "muestra" if es else "sample"
    path = extraction_dir(base, change_id) / "verify" / f"{number:03d}-{suffix}.md"
    lines = [
        f"# Verificación {number} — {change_id}" if es else f"# Verification {number} — {change_id}", "",
        ("Releé cada elemento contra el pedido. Respondé en Resultados con `- ID: igual` o `- ID: difiere — qué falta o cambia`."
         if es else
         "Read each element against the request. Answer under Results with `- ID: same` or `- ID: differs — what is missing or changes`."),
        "",
    ]
    for element_id in picked:
        lines.extend(_entry(project_id, change_id, base, by_id[element_id], items[element_id], es, rows))
    lines.append("## Resultados" if es else "## Results")
    lines.extend(f"- {element_id}: " for element_id in picked)
    lines.append("")
    write_text(path, "\n".join(lines))
    for run in store["runs"]:
        if run.get("status") == "open":
            run["status"] = "superseded"
    store["runs"].append({
        "n": number, "requested_at": _now(), "fingerprint": fingerprint, "confirmed_count": len(ids),
        "sample": picked, "status": "open",
        "request_path": str(path), "results": {}, "reopened": [],
    })
    write_json(verification_path(base, change_id), store)
    return {"action": "verify", "run": number, "sample": picked, "request_path": str(path)}


def parse_verify_results(text: str) -> tuple[dict[str, dict], list[str]]:
    """The verdict of each id (`igual` or `difiere`, with its note) and the ids whose verdict is not one of those.

    The last line of an id wins; a line with an empty verdict (the file as it was handed out) is ignored."""
    results: dict[str, dict] = {}
    unknown: list[str] = []
    for line in str(text or "").splitlines():
        match = _RESULT.match(line)
        if match:
            results[match.group("id")] = {
                "verdict": _VERDICTS[match.group("verdict").lower()], "note": (match.group("note") or "").strip(),
            }
            continue
        loose = _LOOSE.match(line)
        if loose and loose.group("id") not in unknown:
            unknown.append(loose.group("id"))
    return results, [i for i in unknown if i not in results]


def record_verification(project_id: str, change_id: str, path: Path) -> dict:
    """Record the results of the open run, all or nothing; each `difiere` takes its element back to proposed."""
    from .confirm import _finish

    es = _es(project_id, change_id)
    base = workspace_path(project_id)
    store = _load(base, change_id)
    run = next((r for r in reversed(store["runs"]) if r.get("status") == "open"), None)
    if run is None:
        raise InputError(
            f"No hay una verificación abierta en {change_id}: corré /extract {project_id} --change {change_id} --verify" if es
            else f"There is no open verification in {change_id}: run /extract {project_id} --change {change_id} --verify"
        )
    text = Path(path).read_text(encoding="utf-8-sig")
    heading = _RESULTS_HEADING.search(text)
    results, unknown = parse_verify_results(text[heading.end():] if heading else text)
    sample = list(run["sample"])
    for element_id in [*results, *unknown]:
        if element_id not in sample:
            raise InputError(
                f"{element_id} no está en la muestra de la verificación {run['n']}" if es
                else f"{element_id} is not in the sample of verification {run['n']}"
            )
    missing = [i for i in sample if i not in results]
    if missing:
        raise InputError(
            f"faltan resultados para: {', '.join(missing)}" if es else f"missing results for: {', '.join(missing)}"
        )
    for element_id in sample:
        if results[element_id]["verdict"] == "difiere" and not results[element_id]["note"]:
            raise InputError(
                f"{element_id}: «difiere» necesita una nota con lo que falta o cambia" if es
                else f"{element_id}: «differs» needs a note with what is missing or changes"
            )
    proposals = load_proposals(base, change_id)
    reopened: list[str] = []
    not_reopened: list[str] = []
    for element_id in sample:
        outcome = results[element_id]
        if outcome["verdict"] != "difiere":
            continue
        item = proposals["items"].get(element_id)
        if not isinstance(item, dict) or item.get("status") != "confirmed":
            not_reopened.append(element_id)  # taken out or already back to proposed since the sample was drawn
            continue
        item["status"], item["confirmed_at"] = "proposed", None
        flags = [f for f in item.get("flags", []) or [] if f.get("ref") != f"verify:{run['n']}"]
        flags.append({"origin": "verify", "kind": "verificacion_difiere", "ref": f"verify:{run['n']}", "note": outcome["note"]})
        item["flags"] = flags
        reopened.append(element_id)
    run.update({"status": "done", "results": {i: results[i] for i in sample}, "reopened": reopened,
                "completed_at": _now()})
    result: dict[str, Any] = {}
    _finish(project_id, change_id, base, proposals, result)  # proposals.json, sections.json, review.md
    write_json(verification_path(base, change_id), store)
    return {
        "action": "verify_result", "run": run["n"],
        "same": [i for i in sample if results[i]["verdict"] == "igual"],
        "differs": [i for i in sample if results[i]["verdict"] == "difiere"],
        "reopened": reopened, "not_reopened": not_reopened, "review_path": result.get("review_path"),
    }


def verification_status(project_id: str, change_id: str) -> dict[str, Any]:
    runs = _load(workspace_path(project_id), change_id)["runs"]
    done = [r for r in runs if r.get("status") == "done"]
    last = None
    if done:
        run = done[-1]
        outcomes = [v.get("verdict") for v in (run.get("results") or {}).values()]
        last = {
            "n": run["n"], "completed_at": run.get("completed_at"), "sample": len(run.get("sample") or []),
            "fingerprint": run.get("fingerprint"), "confirmed_count": int(run.get("confirmed_count", 0) or 0),
            "same": outcomes.count("igual"), "differs": outcomes.count("difiere"),
            "reopened": list(run.get("reopened") or []),
        }
    return {"runs": len(runs), "open": any(r.get("status") == "open" for r in runs), "last": last}


def verification_needed(project_id: str, change_id: str, total: int | None = None) -> dict[str, Any]:
    """IMP-406 I5: a big extraction (more than 100 elements) asks for a verification that covers its confirmations.

    One covers them while its sample was drawn when at least 80 % of what is confirmed now was confirmed."""
    base = workspace_path(project_id)
    inventory = load_inventory(base, change_id) or {}
    elements = int(total if total is not None else (inventory.get("total") or len(inventory.get("elements", []))))
    state = verification_status(project_id, change_id)
    confirmed = len(_confirmed_ids(inventory, load_proposals(base, change_id)["items"]))
    last = state["last"]
    covered = last is not None and int(last["confirmed_count"]) >= COVERS_SHARE * confirmed
    needed = elements > VERIFY_ABOVE and confirmed > 0 and not covered
    return {"needed": needed, "total": elements, "confirmed": confirmed, "open": state["open"],
            "sample": sample_size(confirmed), "last": last}


def verification_gap_text(need: dict[str, Any], es: bool) -> str:
    """The sentence a status or verdict warning uses for `verification_needed` (no id prefix, no command)."""
    last = need["last"]
    if last is None:
        return (f"la extracción tiene {need['total']} elementos y no se verificó ninguna muestra" if es
                else f"the extraction has {need['total']} elements and no sample was verified")
    return (f"la extracción tiene {need['total']} elementos y la última verificación vio {last['confirmed_count']} de "
            f"{need['confirmed']} confirmados" if es
            else f"the extraction has {need['total']} elements and the last verification saw {last['confirmed_count']} of "
            f"{need['confirmed']} confirmed")
