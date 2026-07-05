---
name: sentinel-implementation-feedback
description: "Use when a downstream implementation, planning, or testing agent hits a blocker in an Ignite Sentinel story — a new dependency, a discovery gap, an acceptance criterion that cannot hold, or an uncovered surface — and must report it as governed feedback through /implementation-feedback instead of silently changing scope. Trigger on 'this AC is wrong', 'missing dependency', an implementation blocker, or any downstream finding about the backlog."
---

# Sentinel Implementation Feedback

Lightweight contract for downstream agents (planners, implementers, testers) reporting findings against the governed backlog. You report; the runtime validates and traces. Findings never rewrite backlog scope directly.

## Command

```powershell
python -m sentinel /implementation-feedback PROJECT_ID --source FINDINGS.json
```

Requires `04_backlog/` to exist (run only after `/backlog`).

## Input Schema

```json
{
  "findings": [
    {
      "type": "surface-not-covered",
      "story": "US-002",
      "acceptance_criteria": "AC-002-03",
      "summary": "The retry flow touches the notifications service, which no story covers.",
      "evidence": "notifications-service/README.md: retries emit user-facing alerts",
      "status": "open",
      "mark_stale": true,
      "source_units": ["SPEC-U-002"]
    }
  ]
}
```

Field contract — the runtime rejects anything outside it, so copy it exactly:

- `type`: exactly one of `new-dependency | gap | ac-challenge | surface-not-covered`.
- `story`: an existing `US-NNN` id; unknown stories are rejected.
- `acceptance_criteria`: optional; when present it must belong to that story.
- `summary`: required.
- `evidence`: required — feedback cannot be anonymous. Cite the concrete file, contract, error, or doc that grounds the finding.
- `status`: `open` (default) or `resolved`.
- `mark_stale`: optional; requires `source_units` so only the affected stories go `Stale`.
- `gap_id`: optional for `type: gap`; defaults to a generated `GAP-FEEDBACK-NNN`.

## What Acceptance Triggers

- A `CHG` trace anchor plus `07_changes/05_implementation_feedback/feedback_report.md`; rejected findings are listed with the rejection reason.
- `type: gap` findings open `GAP-FEEDBACK-*` entries in the discovery gap lifecycle for the BA to route.
- `mark_stale` findings mark the affected stories `Stale`, scoped by `source_units`.
- Open findings can block a story's DoD through the `implementation_feedback_resolved` gate until they are resolved.

## Rules

- Report, do not patch: never edit `US-NNN.md`, acceptance criteria, `BACKLOG.md`, or `state.json`. The finding is the sanctioned channel; scope changes come back through the BA and the owning commands.
- One finding per concrete blocker; batch several in one `findings[]` array.
- Guesses and preferences are not findings — if you cannot cite evidence, raise it conversationally with the BA instead.
