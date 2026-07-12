"""IMP-191: structured digest of unstructured interactions.

`/sync` already ingests and indexes mails, Slack threads and meeting transcripts
as `CHG` events. This module is the *analysis layer on top*: it reads the change
text and extracts, always with a verbatim citation to the source line, four
classes of signal —

  (a) candidate answers to still-open gaps -> a pre-filled `/resolve-gaps`
      response file, every entry marked `PROPOSED` (never `CONFIRMED`);
  (b) decision candidates (`DEC-*`) -> a proposed payload for the decision channel;
  (c) new gaps detected in the change (surfaced from the sync gap scan);
  (d) assumption-contradiction signals -> reused verbatim from the sync
      metabolism (`invalidated_assumptions` + associative candidates, IMP-125),
      never re-detected here.

Hard rule (seed §4 #7): **the digest proposes and routes; it never applies.**
Every impact still enters through its owning command with BA confirmation. The
extraction is deterministic (no LLM): each candidate is a line quoted verbatim,
so the BA can always trace a claim back to who said it before confirming it.
The pre-filled response file uses the `PROPOSED` decision status precisely so
that running `/resolve-gaps` over it as-is cannot close a gap — the BA must
identify the speaker and set `CONFIRMED` by hand first.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .discovery import parse_gap_rows
from .gaps import BLOCKING_GAP_STATUSES
from .workspace import read_json, workspace_path

# Deterministic decision cues (bilingual). A line matching one of these is a
# *candidate* decision to route to the decision channel — never an applied DEC-*.
DECISION_CUE_RE = re.compile(
    r"\b("
    r"we (?:decided|agreed|chose|will use|are going to use)|the decision is|"
    r"decided to|agreed to|we'?ll go with|"
    r"decidimos|acordamos|definimos que|optamos por|vamos a usar|"
    r"se decidi[oó]|queda decidido|la decisi[oó]n es|resolvimos"
    r")\b",
    re.I,
)

# A candidate gap answer needs this many shared significant tokens with the gap
# description. Conservative on purpose (seed §4 #7 warns against reading a
# passing comment as an answer); the BA reviews every candidate anyway.
GAP_ANSWER_MIN_OVERLAP = 3
SIGNIFICANT_TOKEN_RE = re.compile(r"[a-z0-9áéíóúñ]{5,}")

# The response status stamped on every pre-filled entry. Chosen so that it is
# NOT in `gap_resolution.CONFIRMED_STATUSES`: `/resolve-gaps` over the file
# as-is cannot close a gap, forcing BA confirmation.
PROPOSED_STATUS = "PROPOSED"


def _normalize(text: str) -> str:
    return (
        text.lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )


def significant_tokens(text: str) -> set[str]:
    return set(SIGNIFICANT_TOKEN_RE.findall(_normalize(text)))


def iter_citable_lines(text: str) -> list[tuple[int, str]]:
    """1-based line number + stripped content for every non-empty line.

    Line-based (not sentence-based) because transcripts, mails and Slack are
    naturally line-addressable ("Speaker: ..."), which keeps citations stable.
    """
    lines: list[tuple[int, str]] = []
    for index, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if stripped:
            lines.append((index, stripped))
    return lines


def gap_answer_candidates(
    open_gaps: list[dict[str, str]],
    lines: list[tuple[int, str]],
    *,
    min_overlap: int = GAP_ANSWER_MIN_OVERLAP,
) -> list[dict[str, Any]]:
    """Best-matching source line per open gap, by significant-token overlap.

    Returns at most one candidate per gap (the highest-overlap line). Never
    fabricates an answer: the ``quote`` is the source line verbatim.
    """
    candidates: list[dict[str, Any]] = []
    for gap in open_gaps:
        gap_tokens = significant_tokens(gap.get("description", ""))
        if not gap_tokens:
            continue
        best: tuple[int, int, str] | None = None  # (overlap, line_no, quote)
        for line_no, quote in lines:
            overlap = len(gap_tokens & significant_tokens(quote))
            if overlap >= min_overlap and (best is None or overlap > best[0]):
                best = (overlap, line_no, quote)
        if best is not None:
            candidates.append(
                {
                    "gap_id": gap["id"],
                    "gap_description": gap.get("description", ""),
                    "quote": best[2],
                    "line": best[1],
                    "overlap": best[0],
                }
            )
    return candidates


def decision_candidates(lines: list[tuple[int, str]]) -> list[dict[str, Any]]:
    """Lines carrying a decision cue, quoted verbatim with the matched cue."""
    found: list[dict[str, Any]] = []
    for line_no, quote in lines:
        match = DECISION_CUE_RE.search(quote)
        if match:
            found.append({"quote": quote, "line": line_no, "cue": match.group(0).lower()})
    return found


def asm_contradiction_signals(metabolism: dict[str, Any] | None) -> dict[str, Any]:
    """Reuse the sync metabolism's assumption signals — never re-detect (IMP-125).

    ``invalidated_assumptions`` is the deterministic contradiction path;
    ``associative_findings`` are meaning-based candidates for BA review. Both are
    already cited/governed upstream; the digest only surfaces and routes them.
    """
    metabolism = metabolism or {}
    return {
        "invalidated": list(metabolism.get("invalidated_assumptions", []) or []),
        "associative": list(metabolism.get("associative_findings", []) or []),
    }


def load_open_gaps(base: Path) -> list[dict[str, str]]:
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        return []
    rows = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
    return [
        gap
        for gap in rows
        if gap.get("id") not in {None, "NONE"}
        and str(gap.get("status", "OPEN")).upper() in BLOCKING_GAP_STATUSES
    ]


def _project_language(project_id: str) -> str:
    state = read_json(workspace_path(project_id) / "state.json", {})
    language = state.get("project_language", "en")
    return str(language if language in {"es", "en"} else "en")


def render_proposed_gap_response(
    source_ref: str,
    candidates: list[dict[str, Any]],
    language: str = "en",
) -> str:
    """A `/resolve-gaps`-compatible response file, pre-filled but non-applying.

    Each entry stamps `Decision status: PROPOSED` (not in CONFIRMED_STATUSES),
    so running `/resolve-gaps` over the file cannot close the gap. The owner
    field stays an explicit placeholder: the BA must identify the speaker first
    (seed §4 #7).
    """
    es = language == "es"
    header = (
        "# Respuestas propuestas por el digest (revisar antes de confirmar)\n"
        if es
        else "# Digest-proposed gap responses (review before confirming)\n"
    )
    guard = (
        "> PROPUESTO por análisis del digest — NO aplicado. Cada respuesta cita "
        "su línea de origen verbatim. Antes de confirmar: identificá al hablante "
        "y cambiá el estado a `Confirmado`. Correr `/resolve-gaps` sobre este "
        "archivo tal cual NO cierra ningún gap (estado `PROPOSED`).\n"
        if es
        else "> PROPOSED by digest analysis — NOT applied. Each answer quotes its "
        "source line verbatim. Before confirming: identify the speaker and set the "
        "status to `Confirmed`. Running `/resolve-gaps` over this file as-is closes "
        "no gap (status `PROPOSED`).\n"
    )
    answer_label = "Respuesta / Answer"
    owner_label = "Owner / fuente"
    evidence_label = "Evidencia o referencia"
    status_label = "Estado de decisión / Decision status"
    owner_placeholder = (
        "[PENDIENTE — identificá al hablante antes de confirmar]"
        if es
        else "[PENDING — identify the speaker before confirming]"
    )
    blocks = [header, "\n", guard, "\n"]
    for cand in candidates:
        blocks.append(f"### {cand['gap_id']}\n")
        blocks.append(f"- {answer_label}: {cand['quote']}\n")
        blocks.append(f"- {owner_label}: {owner_placeholder}\n")
        blocks.append(f"- {evidence_label}: `{source_ref}` L{cand['line']}\n")
        blocks.append(f"- {status_label}: {PROPOSED_STATUS}\n\n")
    return "".join(blocks)


def render_interaction_digest(
    project_id: str,
    change_id: str,
    source_ref: str,
    gap_candidates: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    new_gaps: list[str],
    asm_signals: dict[str, Any],
    proposed_response_ref: str | None,
) -> str:
    """Human-readable digest. Explicit empty markers when a section has no signal
    (acceptance: artifacts with no signal produce an explicit empty digest, never
    invented content)."""

    def gap_answer_rows() -> str:
        if not gap_candidates:
            return "- None."
        return "\n".join(
            f"- `{c['gap_id']}` <- \"{c['quote']}\" (`{source_ref}` L{c['line']}, "
            f"overlap {c['overlap']})"
            for c in gap_candidates
        )

    def decision_rows() -> str:
        if not decisions:
            return "- None."
        return "\n".join(
            f"- \"{d['quote']}\" (`{source_ref}` L{d['line']}, cue: {d['cue']})"
            for d in decisions
        )

    def new_gap_rows() -> str:
        return "\n".join(f"- `{gap_id}`" for gap_id in new_gaps) or "- None."

    def invalidated_rows() -> str:
        return "\n".join(f"- `{item}`" for item in asm_signals.get("invalidated", [])) or "- None."

    def associative_rows() -> str:
        findings = asm_signals.get("associative", [])
        if not findings:
            return "- None."
        rows = []
        for finding in findings:
            citation = finding.get("citation", {}) or {}
            source = citation.get("source_path", "") or "unknown source"
            line_start = citation.get("line_start", 0)
            line_end = citation.get("line_end", 0)
            locator = f"`{source}`"
            if line_start or line_end:
                locator += f" L{line_start}-{line_end}"
            rows.append(f"- `{finding.get('target')}` (sim {finding.get('score')}) — cita {locator}")
        return "\n".join(rows)

    response_line = (
        f"Pre-filled response file (all entries `PROPOSED`): `{proposed_response_ref}`. "
        f"Review speakers, set `Confirmed`, then run `/resolve-gaps`."
        if proposed_response_ref
        else "No gap-answer candidates -> no response file written."
    )

    return f"""# Interaction Digest - {project_id}

- Change: `{change_id}`
- Source: `{source_ref}`
- Status: `proposed` (nothing applied)

> **This digest proposes and routes; it never applies.** Every signal below is a
> candidate the deterministic scan extracted with a verbatim citation. Each
> impact still enters through its owning command **with your confirmation** — the
> governed mutation path is untouched. Before confirming a gap answer, identify
> who said it (seed §4 #7).

## (a) Candidate Answers To Open Gaps -> /resolve-gaps

{gap_answer_rows()}

{response_line}

## (b) Decision Candidates -> /self-review (decision channel)

{decision_rows()}

_These are proposed `DEC-*` payloads. Route each confirmed one through
`/self-review`; the digest never writes a decision node._

## (c) New Gaps Detected In This Change

{new_gap_rows()}

_Raised into `gaps.md` with `origin: sync` by the change scan (their owning
path). Listed here so the digest is a single view of the change's impact._

## (d) Assumption Contradiction Signals (from sync metabolism, IMP-125)

Deterministically invalidated assumptions:

{invalidated_rows()}

Associative candidates (BA review — nothing auto-invalidated):

{associative_rows()}

_Reused verbatim from the sync metabolism; the digest does not re-detect. Route
assumption movement through the assumptions channel._

## Routing Summary

Nothing above has mutated governed state. Confirm and route each signal through
its owning command: `/resolve-gaps` for gap answers, `/self-review` for
decisions, the assumptions flow for `ASM-*` contradictions.
"""


def build_interaction_digest(
    project_id: str,
    change_id: str,
    source_ref: str,
    source_text: str,
    *,
    target_dir: Path,
    stem: str,
    metabolism: dict[str, Any] | None = None,
    new_gaps: list[str] | None = None,
) -> dict[str, Any]:
    """Orchestrate the digest pass (IO): write the digest and, when there are
    gap-answer candidates, the pre-filled `PROPOSED` response file.

    Returns paths and counts. Adds no governed gap/decision/assumption state —
    it only writes the digest artifacts (proposes and routes, never applies).
    """
    base = workspace_path(project_id)
    lines = iter_citable_lines(source_text)
    open_gaps = load_open_gaps(base)
    gap_candidates = gap_answer_candidates(open_gaps, lines)
    decisions = decision_candidates(lines)
    asm_signals = asm_contradiction_signals(metabolism)
    new_gaps = new_gaps or []

    language = _project_language(project_id)
    proposed_response_path: Path | None = None
    if gap_candidates:
        proposed_response_path = _unique(target_dir / f"{stem}_gap_response_proposed.md")
        proposed_response_path.write_text(
            render_proposed_gap_response(source_ref, gap_candidates, language),
            encoding="utf-8",
        )

    digest_path = _unique(target_dir / f"{stem}_interaction_digest.md")
    digest_path.write_text(
        render_interaction_digest(
            project_id,
            change_id,
            source_ref,
            gap_candidates,
            decisions,
            new_gaps,
            asm_signals,
            proposed_response_path.as_posix() if proposed_response_path else None,
        ),
        encoding="utf-8",
    )
    return {
        "digest_path": digest_path.as_posix(),
        "proposed_response_path": proposed_response_path.as_posix() if proposed_response_path else None,
        "gap_answer_candidates": [c["gap_id"] for c in gap_candidates],
        "decision_candidates": len(decisions),
        "new_gaps": list(new_gaps),
        "invalidated_assumptions": asm_signals["invalidated"],
        "associative_candidates": [f.get("target") for f in asm_signals["associative"]],
        "has_signal": bool(
            gap_candidates or decisions or new_gaps or asm_signals["invalidated"] or asm_signals["associative"]
        ),
    }


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1
