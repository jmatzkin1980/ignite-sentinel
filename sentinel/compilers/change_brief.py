"""IMP-386: the brief of a change (CHG-nnn).

It compiles `02_requirements/CHG-nnn/project-brief.md` from what the change holds and nothing
else: the confirmed answers of the change's own gaps (`01_discovery/CHG-nnn/gaps.md`), the
baseline citations that closed gaps (`by_baseline`: "already exists"), the border the BA
confirmed, and the harvest facts of the blocks that belong to the border's surfaces.

The compiler never infers. Every content line ends with the origin it came from (a gap id, a
`00_raw/` path with its quote, `name:file` plus the harvest block, or the border's own
citation); what is missing is the pending mark of `templates/brief_v2.json`, never prose.
The project's brief, gaps and artifacts are never read as input nor written.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..changes import change_gaps_path, change_language, get_change
from ..core.io import write_json, write_text
from ..gaps import BLOCKING_GAP_STATUSES, blocking_severities, parse_gap_responses, parse_gap_rows
from ..harvest import load_harvest
from ..pending_marks import count_pending_marks
from ..resources import read_package_json
from ..workspace import load_config, workspace_path

BRIEF_NAME = "project-brief.md"
REPORT_NAME = "change_brief_report.json"
HARVEST_CITE = "01_discovery/harvest.json"
_CITE_PATH = re.compile(r"`([^`]+)`")
_CITE_QUOTE = re.compile(r'"([^"]*)"|“([^”]*)”')


def _v2_marker() -> str:
    """The v2 artifact marker: it makes count_pending_marks read blocking and deferred marks apart."""
    from ..citations import id_registry

    return id_registry()["v2_marker"]


def _template() -> dict[str, Any]:
    return read_package_json("templates", "change_brief.json")


def _markers() -> dict[str, Any]:
    return read_package_json("templates", "brief_v2.json")["markers"]


def _note_title(base: Path, change: dict) -> str:
    source = str(change.get("source", ""))
    try:
        for line in (base / source).read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except (OSError, UnicodeDecodeError):
        pass
    return Path(source).stem


def _answers(base: Path, change: dict) -> dict[str, dict[str, str]]:
    """Per gap, the last response that carries an answer text (later files correct earlier ones)."""
    found: dict[str, dict[str, str]] = {}
    for rel in change.get("responses", []):
        path = Path(rel)
        path = path if path.is_absolute() else base / path
        try:
            parsed = parse_gap_responses(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        for gap_id, response in parsed.items():
            if response.get("answer", "").strip():
                found[gap_id] = response
    return found


def collect_change_brief_inputs(project_id: str, change_id: str) -> dict[str, Any]:
    change = get_change(project_id, change_id)
    base = workspace_path(project_id)
    gaps_path = change_gaps_path(base, change_id)
    rows = parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if gaps_path.exists() else []
    answers = _answers(base, change)
    severities = blocking_severities(load_config(project_id))
    gaps = []
    for row in rows:
        gap = dict(row)
        response = answers.get(gap["id"], {})
        gap["answer"] = response.get("answer", "").strip()
        gap["evidence"] = response.get("evidence", "").strip()
        gap["owner"] = response.get("owner", "").strip()
        gap["blocks"] = (
            str(gap.get("status", "OPEN")).strip("`").upper() in BLOCKING_GAP_STATUSES
            and str(gap.get("severity", "")).strip("`").lower() in severities
        )
        gaps.append(gap)
    return {
        "project_id": project_id,
        "change_id": change_id,
        "change": change,
        "language": change_language(project_id, change),
        "gaps": gaps,
        "harvest": load_harvest(base),
        "note_title": _note_title(base, change),
    }


class _Section:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.filled = 0
        self.pending = 0
        self.na = 0

    def fill(self, text: str) -> None:
        self.lines.append(f"- {text}")
        self.filled += 1

    def mark(self, text: str) -> None:
        self.lines.append(f"- {text}")
        self.pending += 1

    def info(self, text: str) -> None:
        self.lines.append(f"- {text}")

    def na_line(self, text: str) -> None:
        self.lines.append(f"- {text}")
        self.na += 1

    def raw(self, text: str) -> None:
        self.lines.append(text)


def _is_open(gap: dict) -> bool:
    return str(gap.get("status", "OPEN")).strip("`").upper() != "CLOSED"


def render_change_brief(inputs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    template = _template()
    v2_marker = _v2_marker()
    language = inputs.get("language") if inputs.get("language") in {"es", "en"} else "es"
    copy = template["copy"][language]
    markers = _markers()
    pending_text = markers["pending"][language]
    domain_text = markers["pending_domain"][language]
    na_text = markers["na"][language]
    change = inputs["change"]
    change_id = inputs["change_id"]
    gaps: list[dict] = list(inputs.get("gaps", []))
    harvest = inputs.get("harvest") or {}
    border = list(change.get("border") or [])
    border_confirmed = bool(border)
    lenses_open = change.get("round") == "lenses"
    by_id = {gap["id"]: gap for gap in gaps}
    gaps_cite = f"01_discovery/{change_id}/gaps.md"

    sec = {item["id"]: _Section() for item in template["sections"]}
    routed: dict[str, int] = {}
    prefixes: list[tuple[str, int]] = []
    for item in template["sections"]:
        for gap_id in item.get("gaps", []):
            routed[gap_id] = item["id"]
        for prefix in item.get("gap_prefixes", []):
            prefixes.append((prefix, item["id"]))

    def section_of(gap_id: str) -> int | None:
        if gap_id in routed:
            return routed[gap_id]
        return next((number for prefix, number in prefixes if gap_id.startswith(prefix)), None)

    def mark_text(gap_id: str, blocks: bool = True) -> str:
        return (pending_text if blocks else domain_text).format(gap=gap_id)

    def gap_line(section: _Section, gap: dict) -> None:
        gap_id = gap["id"]
        if _is_open(gap):
            section.mark(mark_text(gap_id, bool(gap.get("blocks"))))
            return
        answer = gap.get("answer", "")
        if gap.get("closure_reason") == "by_baseline":
            path = _CITE_PATH.search(gap.get("evidence", ""))
            quote = _CITE_QUOTE.search(gap.get("evidence", ""))
            if path and quote:
                text = quote.group(1) if quote.group(1) is not None else quote.group(2)
                section.fill(f"{copy['already']}: «{text.strip()}» (`{path.group(1).strip()}`, {gap_id})")
                return
        section.fill(f"{answer or copy['no_text']} ({gap_id})")

    def surface_line(item: dict) -> str:
        return f"{item['type']} — {item['name']} ({item['cite']})"

    def routed_gaps(number: int) -> list[dict]:
        return [gap for gap in gaps if section_of(gap["id"]) == number]

    def empty_note(section: _Section, number: int) -> None:
        ids = ", ".join(gap_id for gap_id, n in routed.items() if n == number)
        key = "note_covers" if lenses_open or number in (2, 3, 4) else "lenses_not_open"
        if not section.lines:
            section.info(copy[key].format(ids=ids))

    # Harvest facts, each shown once: section 4 claims the flows (B7) before the lenses do.
    facts = [e for e in harvest.get("entries", []) if e.get("kind") == "fact"]
    used: set[int] = set()

    def fact_line(entry: dict) -> str:
        return f"{entry.get('text', '')} ({entry.get('ref', '')}, {entry.get('block', '')})"

    def facts_of(blocks: set[str]) -> list[dict]:
        taken = []
        for index, entry in enumerate(facts):
            if index not in used and entry.get("block") in blocks:
                used.add(index)
                taken.append(entry)
        return taken

    # 1 Context and baseline
    s1 = sec[1]
    source = str(change.get("source", ""))
    s1.fill(f"{copy['note']}: {inputs.get('note_title', '')} (`{source}`)")
    cited: dict[str, list[str]] = {}
    for gap in gaps:
        if gap.get("closure_reason") == "by_baseline" and not _is_open(gap):
            path = _CITE_PATH.search(gap.get("evidence", ""))
            if path:
                cited.setdefault(path.group(1).strip(), []).append(gap["id"])
    for path, ids in sorted(cited.items()):
        s1.fill(f"{copy['baseline_cited']}: `{path}` ({', '.join(ids)})")
    for repo in harvest.get("repos", []):
        s1.fill(f"{copy['repo']}: {repo} (`{HARVEST_CITE}`)")
    for doc in harvest.get("docs", []):
        s1.fill(f"{copy['doc']}: {doc} (`{HARVEST_CITE}`)")

    # 2, 4, 7: the answers of their gaps (4 adds the harvest flows)
    for number in (2, 4, 7):
        for gap in routed_gaps(number):
            gap_line(sec[number], gap)
        if number == 4:
            for entry in facts_of(set(template["surface_blocks"].get("proceso", [])) & {"B7"}):
                sec[4].fill(fact_line(entry))
        empty_note(sec[number], number)

    # 3 Border, 6 preserved behavior, 8 blast radius
    scope = by_id.get("GAP-SCOPE")
    scope_cite = "GAP-SCOPE"
    s3, s6, s8 = sec[3], sec[6], sec[8]
    if border_confirmed:
        for zone in ("nuevo", "adyacente"):
            items = [item for item in border if item.get("zone") == zone]
            if items:
                s3.raw(f"**{copy['zones'][zone]}**")
                for item in items:
                    s3.fill(surface_line(item))
        if scope and scope.get("answer"):
            s3.raw(f"**{copy['scope_answer']}**")
            s3.fill(f"{scope['answer']} ({scope_cite})")
        preserved = [item for item in border if item.get("zone") == "preservado"]
        for item in preserved:
            s6.fill(surface_line(item))
        if not preserved:
            s6.info(copy["no_preserved"].format(cite=scope_cite))
        adjacent = [item for item in border if item.get("zone") == "adyacente"]
        for item in adjacent:
            s8.fill(surface_line(item))
        if not adjacent:
            s8.info(copy["no_adjacent"].format(cite=scope_cite))
    else:
        if scope is not None:
            gap_line(s3, scope)
        else:
            s3.mark(mark_text(scope_cite))
        s6.info(copy["after_border"].format(cite=scope_cite))
    for gap in routed_gaps(8):
        gap_line(s8, gap)

    # 5 By lens
    s5 = sec[5]
    lens_gaps: dict[str, list[dict]] = {}
    for gap in gaps:
        if section_of(gap["id"]) is None:
            lens_gaps.setdefault(str(gap.get("lens", "")).strip("`").lower(), []).append(gap)
    if not border_confirmed:
        s5.info(copy["lenses_after_border"].format(cite=scope_cite))
    else:
        border_kinds = {item.get("type") for item in border}
        order = list(template["lens_titles"]) + [lens for lens in lens_gaps if lens not in template["lens_titles"]]
        for lens in order:
            title = template["lens_titles"].get(lens, {}).get(language, lens)
            kinds = [kind for kind in template["lens_surfaces"].get(lens, []) if kind in border_kinds]
            blocks: set[str] = set()
            for kind in kinds:
                blocks |= set(template["surface_blocks"].get(kind, []))
            body = _Section()
            for gap in lens_gaps.get(lens, []):
                gap_line(body, gap)
            for entry in facts_of(blocks):
                body.fill(fact_line(entry))
            if not body.lines:
                elsewhere = sorted({section_of(g["id"]) for g in gaps
                                    if str(g.get("lens", "")).strip("`").lower() == lens and section_of(g["id"])})
                if elsewhere:
                    refs = ", ".join(f"§{n}" for n in elsewhere)
                    body.info(copy["see_sections"].format(sections=refs))
                elif kinds:
                    for item in border:
                        if item.get("type") in kinds:
                            body.fill(surface_line(item))
                else:
                    reason = template["na_reason"][language].format(lens=title)
                    condition = template["na_condition"][language].format(lens=title)
                    body.na_line(na_text.format(reason=reason, condition=condition))
            s5.raw(f"### {title}")
            s5.lines.extend(body.lines)
            s5.raw("")
            s5.filled += body.filled
            s5.pending += body.pending
            s5.na += body.na
        while s5.lines and not s5.lines[-1]:
            s5.lines.pop()

    # 9 Open items
    s9 = sec[9]
    open_gaps = [gap for gap in gaps if _is_open(gap)]
    header = copy["table"]
    if open_gaps:
        s9.raw("| " + " | ".join(header) + " |")
        s9.raw("|" + "|".join("---" for _ in header) + "|")
        for gap in open_gaps:
            verdict = copy["yes"] if gap.get("blocks") else copy["no"]
            s9.raw(f"| {gap['id']} | {gap.get('lens', '')} | {gap.get('severity', '')} | {verdict} |")
    else:
        s9.info(copy["no_open"].format(cite=gaps_cite))

    heading = copy["heading"].format(change_id=change_id, title=inputs.get("note_title", ""))
    out = [v2_marker, "", f"# {heading}", "", f"{copy['project']}: {inputs.get('project_id', '')}", ""]
    for item in template["sections"]:
        out.append(f"## {item['id']}. {item['title'][language]}")
        out.append("")
        out.extend(sec[item["id"]].lines)
        out.append("")
    text = "\n".join(out).rstrip("\n") + "\n"

    pending_gaps = [gap["id"] for gap in open_gaps]
    report = {
        "change_id": change_id,
        "language": language,
        "sections": {
            str(number): {
                "filled": section.filled,
                "pending": section.pending,
                "na": section.filled == 0 and section.pending == 0 and section.na > 0,
            }
            for number, section in sec.items()
        },
        "pending_gaps": pending_gaps,
        "blocking_open": count_pending_marks(text).blocking,
    }
    return text, report


def compile_change_brief(project_id: str, change_id: str) -> dict[str, Any]:
    inputs = collect_change_brief_inputs(project_id, change_id)
    text, report = render_change_brief(inputs)
    folder = workspace_path(project_id) / "02_requirements" / change_id
    path = folder / BRIEF_NAME
    pending_total = count_pending_marks(text).total
    write_text(path, text)
    write_json(folder / REPORT_NAME, report)
    return {
        "project_id": project_id,
        "change_id": change_id,
        "path": str(path.as_posix()),
        "report": report,
        "summary": {"pending": pending_total, "blocking_open": report["blocking_open"]},
    }
