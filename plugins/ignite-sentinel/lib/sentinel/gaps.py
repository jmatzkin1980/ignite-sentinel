from __future__ import annotations

import re
from typing import Any

from .core.markdown import parse_table_rows


GAP_ROW_FIELDS = (
    "id",
    "lens",
    "severity",
    "status",
    "parent",
    "description",
    "question",
    "source",
    "evidence_mention",
    "origin",
    "resolution_note",
    "unit",
    "kind",  # IMP-257: appended at the end; older tables simply lack it
    "closure_reason",
)
BLOCKING_GAP_STATUSES = {"OPEN", "ANSWERED", "PARTIALLY_CLOSED"}
GAP_STATUSES = BLOCKING_GAP_STATUSES | {"CLOSED"}
DEFAULT_BLOCKING_GAP_SEVERITIES = {"critical", "high"}

# IMP-185: gap closures resolved as out-of-scope/not-applicable are governed
# Non-Goals. The gap-resolution decisions table tags each row with a Kind so the
# brief/PRD compilers can project the scope-exclusion rows without re-deriving.
NON_GOAL_KIND = "non-goal"
DECISION_KIND = "decision"
NON_GOAL_MARKER = {
    "es": (
        "- Sin non-goals registrados: no hay cierres out-of-scope/no-aplica ni "
        "decisiones de alcance que excluyan trabajo. Se completa solo desde datos "
        "gobernados; no se inventa."
    ),
    "en": (
        "- No non-goals recorded: no out-of-scope/not-applicable gap closures or "
        "scope decisions exclude work yet. Populated only from governed data; "
        "never invented."
    ),
}


def blocking_severities(config: dict[str, Any] | None) -> set[str]:
    maturity = config.get("maturity", {}) if isinstance(config, dict) else {}
    configured = maturity.get("blocking_gap_severities", DEFAULT_BLOCKING_GAP_SEVERITIES)
    if not isinstance(configured, (list, tuple, set)):
        return set(DEFAULT_BLOCKING_GAP_SEVERITIES)
    severities = {str(value).strip().lower() for value in configured if str(value).strip()}
    return severities or set(DEFAULT_BLOCKING_GAP_SEVERITIES)


def parse_gap_table(text: str, *, include_legacy: bool = False, strip_code_ticks: bool = True) -> list[dict[str, str]]:
    """The one gaps.md table reader (IMP-257): columns after the 8th are optional."""
    gaps: list[dict[str, str]] = []
    for line in text.splitlines():
        rows = parse_table_rows(line, strip_code_ticks=strip_code_ticks)
        cells = rows[0] if rows else []
        if not cells or not cells[0].startswith("GAP-"):
            continue
        if len(cells) >= 8:
            gap = {
                "id": cells[0],
                "lens": cells[1],
                "severity": cells[2],
                "status": cells[3],
                "parent": cells[4],
                "description": cells[5],
                "question": cells[6],
                "source": cells[7],
            }
            for index, field in enumerate(GAP_ROW_FIELDS[8:], start=8):
                if len(cells) > index and cells[index] not in {"", "N/A"}:
                    gap[field] = cells[index]
            gaps.append(gap)
            continue
        if include_legacy:
            legacy = legacy_gap_row(cells)
            if legacy:
                gaps.append(legacy)
    return gaps


def legacy_gap_row(cells: list[str]) -> dict[str, str] | None:
    if len(cells) < 4:
        return None
    second = cells[2].strip("`").upper()
    if second in GAP_STATUSES:
        return {
            "id": cells[0],
            "lens": "",
            "severity": cells[1],
            "status": cells[2],
            "parent": "",
            "description": cells[3],
            "question": "",
            "source": "",
        }
    return {
        "id": cells[0],
        "lens": cells[1],
        "severity": cells[2],
        "status": cells[3],
        "parent": "",
        "description": cells[4] if len(cells) > 4 else "",
        "question": "",
        "source": "",
    }


def is_blocking(
    gap: dict[str, Any],
    severities: set[str] | None = None,
    statuses: set[str] | None = None,
) -> bool:
    blocking = severities or DEFAULT_BLOCKING_GAP_SEVERITIES
    blocking_statuses = statuses or BLOCKING_GAP_STATUSES
    severity = str(gap.get("severity", "")).strip("`").lower()
    status = str(gap.get("status", "OPEN")).strip("`").upper()
    return severity in blocking and status in blocking_statuses


def count_gaps(gaps: list[dict[str, Any]], severities: set[str] | None = None) -> dict[str, int]:
    """The one gap counter (IMP-248). `blocking_open` follows the configured severities."""
    counts = {"open": 0, "answered": 0, "partially_closed": 0, "closed": 0, "blocking_open": 0, "total": len(gaps)}
    keys = {"OPEN": "open", "ANSWERED": "answered", "PARTIALLY_CLOSED": "partially_closed", "CLOSED": "closed"}
    for gap in gaps:
        key = keys.get(str(gap.get("status", "OPEN")).strip("`").upper())
        if key:
            counts[key] += 1
        if is_blocking(gap, severities):
            counts["blocking_open"] += 1
    return counts


# --- IMP-257: gaps as elicitation ------------------------------------------------

# What kind of gap it is. `domain` is the deferrable class; `synthesis` comes from
# reading several sources (contradictions, agentic channels); `template` from the
# structure itself (the brief v2 umbrella gaps).
GAP_KINDS = ("synthesis", "template", "client", "domain")
SYNTHESIS_ORIGINS = {"agent", "challenge", "scrutiny", "implementability-probe", "self-review", "sufficiency", "anchor-review", "cross-review", "sync",
                     "injection_signal", "contradiction", "cited_not_delivered"}
# How a gap closed: a closed vocabulary, never free text.
CLOSURE_REASONS = (
    "answered", "by_absence", "by_removal", "by_transfer", "accepted_debt", "risk_accepted", "split",
    "reframed", "dissolved", "narrowed", "by_decision", "already_closed_elsewhere", "resolved_by_inference",
)
REOPEN_FALSE_PREMISE = "reopened_false_premise"
# A closure reason that needs a specific id in its citation.
CLOSURE_CITES = {"by_decision": "DEC-", "resolved_by_inference": "ASM-"}


def gap_kind(gap: dict[str, Any]) -> str:
    """The recorded kind, else derived: origin, umbrella, then severity (blocking = client)."""
    kind = str(gap.get("kind", "")).strip("`").lower()
    if kind in GAP_KINDS:
        return kind
    if str(gap.get("origin", "")).strip("`") in SYNTHESIS_ORIGINS:
        return "synthesis"
    if str(gap.get("id", "")).startswith("GAP-BRIEF-"):
        return "template"
    return "client" if str(gap.get("severity", "")).strip("`").lower() in DEFAULT_BLOCKING_GAP_SEVERITIES else "domain"


_TOPIC_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "are", "not", "what", "which", "how", "who", "when", "where",
    "is", "of", "to", "in", "on", "or", "a", "an", "be", "it", "its", "by", "as", "at", "from", "does", "do",
    "el", "la", "los", "las", "de", "del", "que", "en", "y", "o", "un", "una", "por", "para", "con", "se",
    "no", "es", "son", "al", "lo", "como", "qué", "cuál", "cómo", "quién", "está", "están",
}


def topic_tokens(gap: dict[str, Any]) -> frozenset[str]:
    import unicodedata

    text = f"{gap.get('description', '')} {gap.get('question', '')}"
    folded = "".join(ch for ch in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(ch))
    return frozenset(t for t in re.findall(r"[a-z0-9]{3,}", folded) if t not in _TOPIC_STOPWORDS)


TOPIC_OVERLAP = 0.6


def same_topic(first: dict[str, Any], second: dict[str, Any]) -> bool:
    """Same lens and most of the words in common (Jaccard >= 0.6)."""
    if str(first.get("lens", "")).strip("`") != str(second.get("lens", "")).strip("`"):
        return False
    a, b = topic_tokens(first), topic_tokens(second)
    if len(a) < 3 or len(b) < 3:
        return False
    return len(a & b) / len(a | b) >= TOPIC_OVERLAP


def merge_gaps_by_topic(existing: list[dict[str, str]], new: list[dict[str, str]]) -> dict[str, Any]:
    """IMP-257: the common rule for opening gaps. A new id joins; a known id is
    skipped; a new id on the topic of an open gap extends that row instead."""
    rows = [dict(gap) for gap in existing]
    known = {gap["id"] for gap in rows}
    added: list[dict[str, str]] = []
    skipped: list[str] = []
    extended: dict[str, str] = {}
    for gap in new:
        if gap["id"] in known:
            skipped.append(gap["id"])
            continue
        twin = next((row for row in rows if str(row.get("status", "OPEN")).upper() != "CLOSED" and same_topic(row, gap)), None)
        if twin is not None:
            mention = gap.get("evidence_mention") or gap["id"]
            current = twin.get("evidence_mention") or ""
            twin["evidence_mention"] = f"{current}; {mention}" if current and current != "N/A" else mention
            extended[gap["id"]] = twin["id"]
            skipped.append(gap["id"])
            continue
        rows.append(gap)
        added.append(gap)
        known.add(gap["id"])
    return {"gaps": rows, "added": added, "skipped": skipped, "extended": extended}


def parse_gap_responses(text: str) -> dict[str, dict[str, str]]:
    pattern = re.compile(r"^###\s+(GAP-[A-Z0-9-]+).*?(?=^###\s+GAP-[A-Z0-9-]+|\Z)", re.M | re.S)
    responses: dict[str, dict[str, str]] = {}
    for match in pattern.finditer(text):
        gap_id = match.group(1).strip()
        block = match.group(0)
        responses[gap_id] = {
            "answer": extract_field(block, ("Respuesta", "Answer")),
            "owner": extract_field(block, ("Owner / fuente", "Owner / source")),
            "evidence": extract_field(block, ("Evidencia o referencia", "Evidence or reference")),
            "decision_status": extract_field(block, ("Estado de decisión", "Decision status")),
        }
        closure = extract_field(block, ("Motivo de cierre", "Closure reason"))  # IMP-257, optional
        if closure:
            responses[gap_id]["closure"] = closure
    return responses


def extract_field(block: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        # IMP-257: horizontal whitespace only, so an empty field stays empty instead of
        # swallowing the next line (an empty citation used to read the decision status).
        pattern = re.compile(rf"^[ \t]*-[ \t]*{re.escape(label)}[ \t]*:[ \t]*(.*)$", re.I | re.M)
        match = pattern.search(block)
        if match:
            return match.group(1).strip()
    return ""


def parse_gap_answers(text: str) -> dict[str, dict[str, str]]:
    """Map gap_id -> confirmed answer from the gap-resolution seed/decision tables."""
    answers: dict[str, dict[str, str]] = {}
    for row in parse_table_rows(text, skip_separator_rows=True):
        if len(row) >= 5 and row[1].startswith("GAP-") and row[2].upper() == "CONFIRMED":
            answers.setdefault(row[1], {"statement": row[3], "source": row[4]})
    return answers


def parse_non_goals(decisions_text: str) -> list[dict[str, str]]:
    """Governed Non-Goals from the gap-resolution decisions table (IMP-185).

    Only rows tagged ``Kind == non-goal`` (a gap closed out-of-scope/not-applicable)
    are projected; each carries its gap id and source so the entry stays cited.
    No matching rows -> empty list (compilers render the explicit marker, never
    an invented non-goal).
    """
    non_goals: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in parse_table_rows(decisions_text, skip_separator_rows=True):
        if len(row) < 6 or not row[1].startswith("GAP-"):
            continue
        if row[5].strip().lower() != NON_GOAL_KIND:
            continue
        gap_id = row[1]
        if gap_id in seen:
            continue
        seen.add(gap_id)
        non_goals.append({"gap_id": gap_id, "statement": row[3], "source": row[4]})
    return non_goals


def render_non_goals_block(non_goals: list[dict[str, str]], language: str) -> str:
    """Render the governed Non-Goals bullets, or the explicit empty marker."""
    if not non_goals:
        return NON_GOAL_MARKER["es" if language == "es" else "en"]
    lines: list[str] = []
    for item in non_goals:
        gap_id = str(item.get("gap_id", "")).strip()
        statement = str(item.get("statement", "")).strip()
        source = str(item.get("source", "")).strip()
        cite = f"`{gap_id}`" + (f" / `{source}`" if source else "")
        lines.append(f"- {statement} _({cite})_")
    return "\n".join(lines)
