---
name: sentinel-quality
description: "Use when generating or auditing Ignite Sentinel quality artifacts after backlog generation: /quality test cases, the dynamic backlog readiness audit, INVEST/SPIDR/Lawrence story scoring, and US->TC traceability checks. Trigger on 'generate test cases', story quality scoring, DoR warnings, or acceptance-criteria coverage questions. Not for structural workspace validation or gate overrides (use sentinel-health)."
---

# Sentinel Quality

Use this skill after backlog generation.

## Workflow

1. Run `python -m sentinel /quality PROJECT_ID`.
2. Review `workspaces/PROJECT_ID/05_quality/`, especially `backlog_readiness_audit.md`.
3. Run `python -m sentinel /trace PROJECT_ID` to confirm `US -> TC` coverage.
4. Run `python -m sentinel /health PROJECT_ID`.

## Rules

- Every test case must trace to a user story.
- Acceptance criteria coverage must be explicit.
- The backlog readiness audit scores only the governed Ignite model: INVEST, vertical slicing, SPIDR/Lawrence, concrete enabler boundary, AC coverage, traceability, and explicit dependencies.
- Treat story quality findings as DoR warnings by default. Strict backlog gates are opt-in; do not harden them without explicit project configuration.
- Keep automation notes practical and implementation-agnostic.

## Change (`--change CHG-NNN`)

`python -m sentinel /quality PROJECT_ID --change CHG-NNN` (IMP-431) audits only the stories that change wrote (`04_backlog/US-*.md` with `change: CHG-NNN`) and writes `05_quality/CHG-NNN/` (`TC-nnn.md`, `backlog_readiness_audit.md`) in the change's language.

- It needs the change's backlog to be current: `/backlog PROJECT_ID --change CHG-NNN` first. A change with a confirmed series audits the stories of every release already derived.
- The verdict (`PASS` / `PARTIAL` / `ATTENTION`) lives in `state.changes[CHG-NNN].quality`, never in the project's `phase` or `health`; it stays current until a story of the change is edited or regenerated, then `/next --change` asks for `/quality --change` again.
- It does not combine with `--release`, and the project's `/quality` skips the change's stories. A workspace that only has changes refuses the project form.
