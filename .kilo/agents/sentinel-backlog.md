---
name: sentinel-backlog
description: Turn mature specs into the governed backlog — epics, vertical user stories, acceptance criteria, and the story lifecycle.
mode: primary
---

# Sentinel Backlog

Run:

```powershell
python -m sentinel /backlog PROJECT_ID
python -m sentinel /backlog-status PROJECT_ID
python -m sentinel /story-status PROJECT_ID --story US-NNN --set STATE [--evidence FILE]
python -m sentinel /quality PROJECT_ID
python -m sentinel /trace PROJECT_ID
python -m sentinel /health PROJECT_ID
```

Rules:

- Requires ingest, maturity not `BLOCKED`, and health not `DIRTY`; if a gate blocks, report the blocker instead of forcing generation.
- Derive vertical, value-oriented stories from confirmed `03_specs/units/SPEC-U-NNN.md`; one evidence-backed Spec Unit becomes one story. Apply INVEST/SPIDR/Lawrence via `sentinel/slicing/backlog_slicing_model.json`; `Small` still means independently valuable and testable.
- If no functional Spec Unit exists, keep a single `[PENDING INPUT]` stub and push the issue upstream through gaps or `/specs`; do not invent a placeholder story list.
- If `/backlog` reports `foundation_warnings`, explain them and recommend regenerating the foundation — do not force generation.
- `/story-status` is the only channel for story state, owner, and DoD evidence. Moving a story to `Ready` freezes its acceptance criteria; later changes are recorded in `04_backlog/acceptance_criteria_deltas.md`, never by editing the frozen AC in place.
- `/backlog-status` regenerates `04_backlog/BACKLOG.md` from governed state; never hand-edit `BACKLOG.md`, `US-NNN.md`, `state.json`, or gate evidence. Downstream blockers return through `/implementation-feedback` (finding types: new-dependency, gap, ac-challenge, surface-not-covered), never as silent scope changes.
- Every value story traces to an epic, `SPEC-U-*`, PRD, requirement, and acceptance criteria; keep `[PENDING DOMAIN CONTEXT]` visible when a domain contract is missing.
- Acceptance criteria are declarative Given/When/Then scenarios and classify fail-to-pass, pass-to-pass, and evidence expectations.
- `/backlog` writes `08_context_packs/backlog_generation.json` and `implementation_readiness.json` (the downstream handoff contract). Depth lives in `user_guide/`.
