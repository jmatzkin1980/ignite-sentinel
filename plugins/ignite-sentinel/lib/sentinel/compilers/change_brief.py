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

from ..change_assumptions import open_change_assumptions
from ..changes import change_gaps_path, change_language, get_change
from ..crosses.state import cross_status, crosses_fingerprint
from ..core.io import write_json, write_text
from ..core.markdown import table_cell
from ..extraction.coverage import extraction_view
from ..extraction.lines import format_ranges
from ..gaps import BLOCKING_GAP_STATUSES, blocking_severities, parse_gap_responses, parse_gap_rows
from ..harvest import load_harvest
from ..pending_marks import count_pending_marks
from ..prior_decisions import load_priors
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


def collect_change_brief_inputs(project_id: str, change_id: str, extraction: bool = True) -> dict[str, Any]:
    """`extraction=False` leaves out the extraction view (the lens view of the change is built before the extraction)."""
    change = get_change(project_id, change_id)
    base = workspace_path(project_id)
    gaps_path = change_gaps_path(base, change_id)
    rows = parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if gaps_path.exists() else []
    answers = _answers(base, change)
    priors = load_priors(base, change_id)  # IMP-410: a question the BA confirmed with the earlier decision has that answer
    severities = blocking_severities(load_config(project_id))
    gaps = []
    for row in rows:
        gap = dict(row)
        entry = priors.get(gap["id"])
        response = answers.get(gap["id"]) or (
            {"answer": entry["answer"], "option": entry.get("option", "")} if entry and entry.get("accepted_at") else {})
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
        "assumptions": open_change_assumptions(project_id, change_id),  # IMP-412: [] when the change has no register
        "harvest": load_harvest(base),
        "note_title": _note_title(base, change),
        "extraction": extraction_view(project_id, change_id) if extraction else {},
        "crosses": cross_status(project_id, change_id),
        "crosses_fingerprint": crosses_fingerprint(project_id, change_id),
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

    def is_out_of_code(gap_id: str) -> bool:
        # IMP-384: a harvest question for the domain (out of code) is a technical-lens question
        # (§5); the divergences of a harvest stay in the blast radius (§8).
        gap = by_id.get(gap_id, {})
        return gap_id.startswith("GAP-HRV-") and str(gap.get("kind", "")).strip("`").lower() == "domain"

    def is_divergence(gap_id: str) -> bool:
        # A harvest gap that is not a question for the domain (out of code) is a divergence.
        gap = by_id.get(gap_id, {})
        return (gap_id.startswith("GAP-HRV-") and not is_out_of_code(gap_id)
                and str(gap.get("origin", "harvest")).strip("`").lower() == "harvest")

    def section_of(gap_id: str) -> int | None:
        if is_out_of_code(gap_id):
            return None
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
                if is_divergence(gap_id):
                    # IMP-398: the quote of a divergence may say that something does not exist, so
                    # "already exists" would read backwards: answer first, the baseline as support.
                    section.fill(f"{answer or copy['no_text']} — {copy['baseline_support']}: «{text.strip()}» "
                                 f"(`{path.group(1).strip()}`, {gap_id})")
                    return
                section.fill(f"{copy['already']}: «{text.strip()}» (`{path.group(1).strip()}`, {gap_id})")
                return
        section.fill(f"{answer or copy['no_text']} ({gap_id})")

    def surface_line(item: dict) -> str:
        return f"{item['type']} — {item['name']} ({item['cite']})"

    def routed_gaps(number: int) -> list[dict]:
        return [gap for gap in gaps if section_of(gap["id"]) == number]

    extraction_pending: list[int] = []

    # IMP-402: what the extraction confirmed. Without an inventory nothing below changes a byte.
    view = inputs.get("extraction") or {}
    has_inventory = view.get("state", "missing") != "missing"
    ext_elements: list[dict] = list(view.get("elements", [])) if has_inventory else []
    ext_items: dict = view.get("items", {}) if has_inventory else {}
    ext_by_id = {element["id"]: element for element in ext_elements}
    inventory_cite = f"02_requirements/{change_id}/extraction/inventory.json"

    def is_confirmed(element: dict) -> bool:
        item = ext_items.get(element["id"])
        return (isinstance(item, dict) and item.get("status") == "confirmed"
                and item.get("element_sha") == element.get("sha"))

    def extracted_entries(section: _Section, number: int) -> None:
        for entry in view.get("sections", []) if has_inventory else []:
            if entry.get("brief_section") != number:
                continue
            quote = str(entry.get("quote") or "").strip()
            content = entry.get("content")
            if content is not None:
                # IMP-406: the section is the request text as written, never a summary of it
                section.fill(copy["extracted_content"].format(
                    element=entry.get("element", ""), path=entry.get("path", ""),
                    lines=format_ranges(entry.get("lines") or []) or entry.get("line", "")))
                section.raw("")
                for line in str(content).split("\n"):
                    section.raw(line)
                section.raw("")
                continue
            text = str(entry.get("text") or "").strip()
            fields = {"quote": quote, "path": entry.get("path", ""), "line": entry.get("line", ""),
                      "element": entry.get("element", "")}
            section.fill(copy["extracted" if text else "extracted_quote"].format(text=text, **fields))

    def extracted_rows(section: _Section, unchanged: bool) -> None:
        for element_id, rows in (view.get("rows", {}) if has_inventory else {}).items():
            element = ext_by_id.get(element_id)
            if element is None:
                continue
            for row in rows:
                if (str(row.get("delta", "")).strip().upper() == "UNCHANGED") != unchanged:
                    continue
                section.fill(copy["extracted_row"].format(
                    statement=row.get("statement", ""), delta=row.get("delta", ""), row=row.get("id", ""),
                    element=element_id, path=element.get("path", ""), line=element.get("line", "")))

    def extraction_marks(section: _Section, number: int) -> None:
        """A deferred mark while elements of this section are unconfirmed; else an empty section says so."""
        left = [e["id"] for e in ext_elements if e.get("home") == number and not is_confirmed(e)]
        if left:
            ids = ", ".join(left[:5]) + (", …" if len(left) > 5 else "")
            section.mark(copy["extraction_left"].format(n=len(left), ids=ids, cite=inventory_cite))
            extraction_pending.append(number)
        elif not section.lines:
            home = [e["id"] for e in ext_elements if e.get("home") == number]
            if not home:
                section.info(copy["extraction_none"].format(cite=inventory_cite))
            else:
                # every element of this section is confirmed, none landed here: say where they went
                discarded = all((ext_items.get(i) or {}).get("treatment") == "descarte" for i in home)
                ids = ", ".join(home[:5]) + (", …" if len(home) > 5 else "")
                section.info(copy["extraction_discarded" if discarded else "extraction_elsewhere"].format(
                    n=len(home), ids=ids, cite=inventory_cite))

    def empty_note(section: _Section, number: int) -> None:
        if has_inventory:
            extracted_entries(section, number)
            if number == 7:
                extracted_rows(section, False)
            extraction_marks(section, number)
            return
        ids = ", ".join(gap_id for gap_id, n in routed.items() if n == number)
        key = "note_covers" if lenses_open or number in (2, 3, 4) else "lenses_not_open"
        if not section.lines:
            if key == "note_covers":
                # IMP-398: the request covers the topic and the brief does not hold it yet. It is a
                # deferred mark (extraction owes it), never "no open question".
                section.mark(copy[key].format(ids=ids, cite=gaps_cite))
                extraction_pending.append(number)
            else:
                section.info(copy[key].format(ids=ids, cite=gaps_cite))

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

    # Harvest facts only follow a confirmed border: the blocks of the surface types it holds.
    border_blocks: set[str] = set()
    for item in border:
        border_blocks |= set(template["surface_blocks"].get(item.get("type"), []))

    # IMP-398: the cross-cutting blocks (architecture, operations) belong to any technical border.
    transversal = template.get("transversal", {})
    cross = bool({item.get("type") for item in border} & set(transversal.get("surfaces", [])))

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
    crosses = inputs.get("crosses") or {}
    if any(info.get("state") in ("done", "waived") for info in (crosses.get("kinds") or {}).values()):
        s1.raw(copy["crosses"].format(text=crosses.get("text", "")))
    for repo in harvest.get("repos", []):
        s1.fill(f"{copy['repo']}: {repo} (`{HARVEST_CITE}`)")
    for doc in harvest.get("docs", []):
        s1.fill(f"{copy['doc']}: {doc} (`{HARVEST_CITE}`)")
    if cross:
        for entry in facts_of(set(transversal.get("context", []))):
            s1.fill(fact_line(entry))

    # 2, 4, 7: the answers of their gaps (4 adds the harvest flows)
    for number in (2, 4, 7):
        for gap in routed_gaps(number):
            gap_line(sec[number], gap)
        if number == 4:
            if "B7" in border_blocks:
                for entry in facts_of({"B7"}):
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
        unchanged_rows = (view.get("preserved") or {}).get("rows", {}) if has_inventory else {}
        for item in preserved:
            line = surface_line(item)
            if has_inventory:
                found = unchanged_rows.get(item.get("name"), [])
                line += " — " + (copy["preserved_rows"].format(rows=", ".join(found)) if found
                                 else copy["preserved_missing"])
            s6.fill(line)
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
    if has_inventory:
        extracted_entries(s3, 3)
        extracted_entries(s6, 6)
        extracted_rows(s6, True)
    for gap in routed_gaps(8):
        gap_line(s8, gap)
    if not border_confirmed and not routed_gaps(8):
        s8.info(copy["after_border"].format(cite=scope_cite))

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
            if cross and lens == "technical":
                blocks |= set(transversal.get("technical", []))
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
    assumed = list(inputs.get("assumptions") or [])
    if assumed:  # IMP-412: what the BA went on with, to be validated by someone else
        es = language == "es"
        s9.raw("")
        s9.raw("**Supuestos a validar**" if es else "**Assumptions to validate**")
        s9.raw("")
        head = ["Supuesto", "Enunciado", "Valida", "Pregunta"] if es else ["Assumption", "Statement", "Validates", "Question"]
        s9.raw("| " + " | ".join(head) + " |")
        s9.raw("|" + "|".join("---" for _ in head) + "|")
        for row in assumed:
            s9.raw(f"| {row['id']} | {table_cell(row['statement'])} | {table_cell(row['validate_with'])} | {row['gap']} |")
    if has_inventory or extraction_pending:
        s9.raw("")
    if has_inventory:
        for element in ext_elements:
            item = ext_items.get(element["id"])
            if is_confirmed(element) and item.get("treatment") == "descarte":
                s9.info(copy["discarded"].format(
                    element=element["id"], reason=str(item.get("reason", "")).strip(),
                    path=element.get("path", ""), line=element.get("line", "")))
        s9.info(copy["coverage"].format(text=(view.get("coverage") or {}).get("text", "")))
    if extraction_pending:
        s9.info(copy["extraction_summary"].format(sections=", ".join(f"§{n}" for n in extraction_pending)))

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
        "extraction_pending": [str(number) for number in extraction_pending],
        "blocking_open": count_pending_marks(text).blocking,
        "extraction": view.get("coverage") if has_inventory else None,
        "extraction_fingerprint": view.get("fingerprint", "") if has_inventory else "",
        "crosses_fingerprint": inputs.get("crosses_fingerprint", ""),
        **({"assumptions_open": [row["id"] for row in assumed]} if assumed else {}),
        "preserved_missing": list((view.get("preserved") or {}).get("missing", [])) if has_inventory else [],
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
