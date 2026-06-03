---
name: sentinel-specs
description: Use when Codex needs to generate AI-friendly PRD/specification artifacts from mature Ignite Sentinel requirements while preserving source traceability.
---

# Sentinel Specs

Use this skill to create the AI-friendly PRD/spec layer.

## Workflow

1. Run `python -m sentinel maturity PROJECT_ID`.
2. If ready, run `python -m sentinel specs PROJECT_ID`.
3. Review `workspaces/PROJECT_ID/03_specs/prd_ai_friendly.md`.
4. Run `python -m sentinel trace PROJECT_ID` to confirm `REQ -> SPEC` linkage.

## Rules

- Specs must elaborate existing requirements.
- Do not proceed while maturity is `BLOCKED`.
- Keep Product, Technology, Design, Quality, and Delivery signals visible.
