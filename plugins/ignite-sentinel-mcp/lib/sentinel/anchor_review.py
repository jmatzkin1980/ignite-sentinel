"""IMP-258b: anchors that hold, agentic part (`/scrutinize --mode anchors`).

IMP-258 checks what needs no judgment (the anchor resolves, the source is current,
it is not an echo). Whether the cited passage *supports* the sentence is judgment,
so an agent reviews each anchor and the runtime validates its review:

    {"anchors": [
      {"place": "2.1", "source": "F-01",
       "claim": "<verbatim sentence of the brief at that place>",
       "source_quote": "<verbatim passage of the cited source>",
       "verdict": "holds | says_less | says_opposite",
       "inverted": "what one would claim from the source alone",
       "adversarial": {"refuted": false, "quote": "<verbatim source passage, when refuted>"},
       "question": "...?"}]}

- `claim` sits verbatim at `place`, on a line that cites `source`.
- `source_quote` sits verbatim in that source.
- `says_less` / `says_opposite` need the inverted reading and a question.
- The adversarial pass tries to refute each "holds": a refutation with a verbatim
  source quote turns it into `says_less`.

Accepted findings open `GAP-ANC-*` gaps (`origin: anchor-review`); the brief is
never edited. Each review is appended to `01_discovery/anchor_review_log.md`.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .brief_model import lenses_for_v2_id, parse_brief

VERDICTS = ("holds", "says_less", "says_opposite")
SEVERITY = {"says_less": "medium", "says_opposite": "high"}
LENS_NAMES = {"1": "business", "2": "business", "3": "product", "4": "design", "5": "technical", "6": "compliance"}


class AnchorReviewError(RuntimeError):
    pass


def _norm(text: str) -> str:
    return " ".join(str(text).split()).lower()


def _place_lines(brief_text: str, place: str) -> list[str] | None:
    model = parse_brief(brief_text)
    section = model.sections.get(place)
    if section is None:
        return None
    return brief_text.splitlines()[section.start:section.end]


def validate_reviews(brief_text: str, sources: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    """Accepted gaps, rejected reviews (with reasons) and counts per verdict. Pure."""
    if parse_brief(brief_text).version != 2:
        raise AnchorReviewError("Anchor review reads a brief v2; compile one with /brief first.")
    reviews = payload.get("anchors")
    if not isinstance(reviews, list) or not reviews:
        raise AnchorReviewError("The payload needs a non-empty `anchors` list.")
    counts = {verdict: 0 for verdict in VERDICTS}
    accepted: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    for index, item in enumerate(reviews, start=1):
        if not isinstance(item, dict):
            rejected.append({"index": str(index), "reason": "not an object"})
            continue
        place, source = str(item.get("place", "")).strip(), str(item.get("source", "")).strip()
        verdict = str(item.get("verdict", "")).strip().lower()

        def reject(reason: str) -> None:
            rejected.append({"index": str(index), "place": place, "source": source, "reason": reason})

        if verdict not in VERDICTS:
            reject(f"verdict must be one of {', '.join(VERDICTS)}")
            continue
        lines = _place_lines(brief_text, place)
        if lines is None:
            reject("place is not a section or subsection of the brief")
            continue
        claim = str(item.get("claim", "")).strip()
        cited = [line for line in lines if f"# {source} " in line or f"# {source}—" in line]
        if not claim or not any(_norm(claim) in _norm(line) for line in cited):
            reject(f"the claim is not verbatim at §{place} on a line that cites {source}")
            continue
        text = sources.get(source)
        if text is None:
            reject(f"{source} is not a readable source")
            continue
        quote = str(item.get("source_quote", "")).strip()
        if not quote or _norm(quote) not in _norm(text):
            reject(f"the source quote is not verbatim in {source}")
            continue
        adversarial = item.get("adversarial") or {}
        if verdict == "holds" and isinstance(adversarial, dict) and adversarial.get("refuted"):
            refutation = str(adversarial.get("quote", "")).strip()
            if not refutation or _norm(refutation) not in _norm(text):
                reject("a refutation needs a verbatim quote of the source")
                continue
            verdict = "says_less"  # the adversarial pass found the source does not carry all of it
            quote = refutation
        if verdict == "holds":
            counts["holds"] += 1
            continue
        inverted, question = str(item.get("inverted", "")).strip(), str(item.get("question", "")).strip()
        if not inverted:
            reject("a finding needs the inverted reading (what the source alone supports)")
            continue
        if not question.endswith("?"):
            reject("a finding needs a `question` that ends with '?'")
            continue
        counts[verdict] += 1
        digest = hashlib.sha256(f"{place}|{source}|{_norm(claim)}|{verdict}".encode("utf-8")).hexdigest()[:8].upper()
        lenses = lenses_for_v2_id(place)
        accepted.append({
            "id": f"GAP-ANC-{digest}",
            "lens": LENS_NAMES.get(lenses[0], "product") if lenses else "product",
            "severity": SEVERITY[verdict],
            "status": "OPEN",
            "description": f"Anchor {verdict.replace('_', ' ')} at §{place} ({source}): \"{claim[:120]}\"; the source supports: {inverted[:160]}",
            "question": question,
            "evidence_mention": quote[:160],
            "origin": "anchor-review",
            "resolution_note": "",
        })
    return {"accepted": accepted, "rejected": rejected, "counts": counts}


def workspace_sources(base: Path) -> dict[str, str]:
    """Text of each governed source row, by F-NN, from its copy in the workspace."""
    from .core.io import read_json

    manifest = read_json(base / "00_raw" / "source_manifest.json", {}) or {}
    texts: dict[str, str] = {}
    search = [base / "00_raw", base / "07_changes" / "00_client_responses"]
    for row in manifest.get("registry", []) if isinstance(manifest, dict) else []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        for name in [Path(p).name for p in row.get("paths", [])] + [Path(p).name for p in row.get("copies", [])]:
            hit = next((folder / name for folder in search if (folder / name).is_file()), None)
            if hit is None:
                hit = next((p for p in (base / "00_raw").rglob(name) if p.is_file()), None)
            if hit is not None:
                texts[row["id"]] = hit.read_text(encoding="utf-8", errors="ignore")
                break
    return texts


def apply_anchor_review(project_id: str, source_path: Path) -> dict[str, Any]:
    from .agent_sweep import record_sweep
    from .core.io import append_text, read_json, write_text
    from .discovery import count_gaps, parse_gap_rows, readiness_stage_after_gap_change, render_gaps
    from .gaps import merge_gaps_by_topic
    from .workspace import read_state, update_state, workspace_path

    base = workspace_path(project_id)
    brief_path = base / "02_requirements" / "project-brief.md"
    if not brief_path.exists():
        raise AnchorReviewError("Anchor review needs a compiled brief: run /brief first.")
    payload = read_json(source_path, None)
    if not isinstance(payload, dict):
        raise AnchorReviewError("The anchor review payload must be a JSON object.")
    result = validate_reviews(brief_path.read_text(encoding="utf-8"), workspace_sources(base), payload)
    gaps_path = base / "01_discovery" / "gaps.md"
    existing = [g for g in parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if g.get("id") != "NONE"] if gaps_path.exists() else []
    merged = merge_gaps_by_topic(existing, result["accepted"])
    if gaps_path.exists() and (merged["added"] or merged["extended"]):
        state = read_state(project_id, {})
        language = state.get("project_language") if state.get("project_language") in {"es", "en"} else "en"
        req_id = existing[0].get("parent", "REQ-001").strip("`") if existing else "REQ-001"
        write_text(gaps_path, render_gaps(project_id, merged["gaps"], req_id, language))
        counts = count_gaps(merged["gaps"])
        update_state(project_id, gap_counts=counts, readiness_stage=readiness_stage_after_gap_change(project_id, counts))
    record_sweep(base, "anchor-review", payload, [g["id"] for g in merged["added"]])
    log = base / "01_discovery" / "anchor_review_log.md"
    if not log.exists():
        write_text(log, f"# Anchor review log - {project_id}\n\nDoes each cited passage hold what the brief attributes to it?\n")
    c = result["counts"]
    entry = ["\n## Review", "", f"- holds {c['holds']} · says less {c['says_less']} · says the opposite {c['says_opposite']}",
             f"- gaps opened: {', '.join(g['id'] for g in merged['added']) or 'none'}",
             f"- rejected: {len(result['rejected'])}"]
    entry += [f"  - #{r['index']} §{r.get('place', '?')} {r.get('source', '')}: {r['reason']}" for r in result["rejected"]]
    append_text(log, "\n".join(entry) + "\n")
    return {"project_id": project_id, "counts": c, "gaps_opened": [g["id"] for g in merged["added"]],
            "extended": merged["extended"], "rejected": result["rejected"], "log": str(log.as_posix())}
