---
name: sentinel-quality
description: Use when Codex needs to generate or audit Ignite Sentinel quality artifacts, test cases, automation notes, and acceptance-criteria coverage for generated user stories.
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
