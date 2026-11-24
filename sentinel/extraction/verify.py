"""IMP-406 task 5: verification sampling of a confirmed extraction.

A reproducible sample of the confirmed elements goes to a file the BA (or a fresh agent) reads against the
request; each `difiere` takes its element back to proposed with a `verificacion_difiere` mark.
"""
from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any

from ..change_requirements import load_change_ears
from ..changes import change_language, get_change
from ..core.io import read_json, write_json, write_text
from ..core.paths import workspace_path
from ..errors import InputError
from . import extraction_dir
from .coverage import extraction_fingerprint
from .inventory import _read_text, _split_lines, element_lines, load_inventory
from .lines import format_ranges
from .proposals import _now, load_proposals

DEFAULT_SAMPLE = 10

_RESULT = re.compile(
    r"^\s*[-*]\s*(?P<id>[^\s:]+)\s*:\s*(?P<verdict>igual|difiere|same|differs)\b\s*"
    r"(?:(?:—|-|:)\s*(?P<note>.+?))?\s*$",
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
    return change_language(project_id, get_change(project_id, change_id)) == "es"


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
        for start, end in element.get("spans", []):
            lines.extend(f"  > {line}" for line in source[start - 1 : end])
    else:
        lines.append(f"- {'Motivo' if es else 'Reason'}: {item.get('reason') or ''}")
    lines.append("")
    return lines


def start_verification(project_id: str, change_id: str, sample: int = DEFAULT_SAMPLE) -> dict:
    """Draw the sample of confirmed elements, write its file and open the run."""
    es = _es(project_id, change_id)
    if sample < 1:
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
    picked = random.Random(int(fingerprint, 16) if fingerprint else 0).sample(ids, min(sample, len(ids)))
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
        "n": number, "requested_at": _now(), "fingerprint": fingerprint, "sample": picked, "status": "open",
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
    for element_id in sample:
        outcome = results[element_id]
        if outcome["verdict"] != "difiere":
            continue
        item = proposals["items"].get(element_id)
        if not isinstance(item, dict):
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
        "reopened": reopened, "review_path": result.get("review_path"),
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
            "same": outcomes.count("igual"), "differs": outcomes.count("difiere"),
            "reopened": list(run.get("reopened") or []),
        }
    return {"runs": len(runs), "open": any(r.get("status") == "open" for r in runs), "last": last}
