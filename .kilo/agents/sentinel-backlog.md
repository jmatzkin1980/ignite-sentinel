---
name: sentinel-backlog
description: Generate epics, user stories, and acceptance criteria from mature specs.
mode: primary
---

# Sentinel Backlog

Run:

```powershell
python -m sentinel /backlog PROJECT_ID
python -m sentinel /quality PROJECT_ID
python -m sentinel /trace PROJECT_ID
python -m sentinel /health PROJECT_ID
python -m sentinel /validate PROJECT_ID
```

Rules:

- If the user describes a desired backlog outcome instead of giving an exact command, run the appropriate Sentinel backlog workflow when gates allow it and summarize generated artifacts plus blockers.
- Generate one Markdown file per epic as the primary human review artifact, plus `US-00x.md` story mirrors for traceability and quality tooling.
- Generate vertical, value-oriented stories. Apply INVEST pragmatically: `Small` means small but still independently valuable, testable, and useful.
- Derive value stories from confirmed `03_specs/units/SPEC-U-NNN.md` files. One evidence-backed Spec Unit should become one vertical story.
- If no functional Spec Unit exists, keep a single `[PENDING INPUT]` backlog stub and push the issue upstream through gaps or `/specs`; do not expand a fixed placeholder story list.
- Every value story must trace to an epic, `SPEC-U-*`, spec index, PRD, requirement, `REQ-EARS-*`, and acceptance criteria when available.
- Use living domain context from Technology, Design, Quality, Delivery, and Product folders through local retrieval. Do not invent missing commands, files, design tokens, regression suites, data contracts, or blast-radius boundaries.
- Keep `[PENDING DOMAIN CONTEXT]` visible when a domain contract is missing.
- Include `Domain Context Coverage`, `Agent Execution Contract`, and `Retrieval Plan For Execution Agents` in stories.
- `/backlog` must create `08_context_packs/backlog_generation.json` and `08_context_packs/implementation_readiness.json`.
- Treat `implementation_readiness.json` as the downstream handoff contract for planning, implementation, and testing agents.
- Cross-cutting enablers are valid only when they are concrete implementation work that must be built in advance to support confirmed functionality across stories, epics, FRs, or implementation surfaces.
- Generic setup, broad hardening, environment availability, or vague accessibility/operability work are preconditions or external tasks unless tied to specific project functionality and objective completion evidence.
- Acceptance criteria must be declarative Given/When/Then scenarios and classify fail-to-pass, pass-to-pass, and evidence expectations.
