---
name: sentinel-backlog
description: Use when Codex needs to transform mature Ignite Sentinel specs into AI-friendly epics, user stories, and acceptance criteria with traceability.
---

# Sentinel Backlog

Use this skill to generate execution-ready backlog artifacts.

## Workflow

1. Run `python -m sentinel /maturity PROJECT_ID`.
2. Run `python -m sentinel /backlog PROJECT_ID`.
3. Review `workspaces/PROJECT_ID/08_context_packs/backlog_generation.json` to confirm focused local retrieval was used.
4. Review `workspaces/PROJECT_ID/08_context_packs/implementation_readiness.json` to confirm each story has required domains, pending execution context, retrieval plan, validation contract, dependencies, and freshness snapshot.
5. Review `workspaces/PROJECT_ID/04_backlog/EPIC-001.md` as the primary backlog artifact. It contains the epic, domain context coverage, story map, slicing rationale, retrieved context summary, agent execution contracts, retrieval plans, and embedded stories.
6. Review generated `US-00x.md` files only as story-level traceability and quality handoff mirrors.
7. Run `python -m sentinel /quality PROJECT_ID`.
8. Run `python -m sentinel /trace PROJECT_ID` and `python -m sentinel /health PROJECT_ID`.

## Rules

- Generate vertical, value-oriented stories. Avoid layer-only frontend/backend/data stories unless the item is explicitly framed as a spike or a valid cross-cutting enabler.
- Every story must cite `REQ-001`, `PRD-001`, `SPEC-001`, and at least one FR/JTBD/rule when available.
- Use progressive disclosure: retrieve focused local context for business value, functional slicing, technical dependencies, UX states, quality risks, and open uncertainty.
- Treat domain context as living input across the whole lifecycle. Technology, Design, Quality, Delivery or other domain owners may add context files over time; `/ingest`, `/sync`, and `/reindex` make that context available for backlog retrieval.
- Keep source of truth in workspace files. Treat memory context as retrieval evidence, not as authority over project files.
- Do not invent Technology, Design or Quality execution details. If commands, files, design tokens, regression suites, handbook references, test data or blast-radius boundaries are missing, keep `[PENDING DOMAIN CONTEXT]` visible and push the issue upstream through `/context-request`, `/sync`, gaps, or domain updates.
- Apply INVEST as a quality filter, but interpret `Small` as `small but valuable`: the smallest independently meaningful, testable, useful slice. Do not split below the value boundary into button/endpoint/table micro-stories that cannot be accepted on their own.
- Apply slicing patterns deliberately:
  - SPIDR: Spikes, Paths, Interfaces, Data, Rules.
  - Lawrence-style reduction: isolate the smallest useful variation first, then add workflow steps, edge cases, performance, external dependency, or discovery stories.
- Each story should include description, narrative, slicing pattern, dependencies, in/out of scope, context used, acceptance criteria, Definition of Ready, Definition of Done, and traceability.
- Each epic/story should include `Domain Context Coverage` for Product, Technology, Design, Quality, and Delivery so humans and agents can see which domain evidence was used and what remains pending.
- Each story may include an `Agent Execution Contract` derived from retrieved context: agent profile, command hints, critical surfaces, design match, engineering practices, autonomy limits, blast radius, validation contract, and parallelization/sequencing notes.
- Each story must include a `Retrieval Plan For Execution Agents` so planners, implementers, and testers know which focused `/retrieve` queries to run before touching code or tests.
- Treat `implementation_readiness.json` as the handoff contract for downstream agents. If it reports `needs-context`, resolve missing domain context upstream or rerun `/reindex` and `/backlog` after domain owners update their files.
- If `/health` reports that domain context changed after backlog generation, do not hand off implementation from the stale backlog. Run `/reindex` and `/backlog` first.
- Acceptance criteria must be declarative Given/When/Then scenarios covering happy path, validation path, failure/recovery path, regression path, and quality evidence path.
- Classify acceptance criteria as `fail-to-pass`, `pass-to-pass`, or `evidence` so downstream Quality and implementation agents know which tests should become newly green, which existing regression must stay green, and which evidence proves completion.
- Cross-cutting enablers may be grouped in a dedicated enabler epic only when they are implementation work, frontend/backend/architecture, that must be built in advance to support confirmed functionality across stories, epics, FRs, or implementation surfaces.
- A valid enabler names the capability boundary it supports, why it must be built earlier, which risk/dependency it reduces, and what objective evidence proves completion.
- Reject loose enablers. Generic environment availability, broad infrastructure hardening, "make an internal tool accessible", or unspecified setup are preconditions/external tasks unless tied to confirmed project functionality and implementation evidence.
- If required information is missing, keep `[PENDING INPUT]` visible and push the issue upstream through gaps, `/sync`, or domain context requests instead of inventing scope.
- Do not copy sensitive client details, credentials, private URLs, account IDs, raw payloads, or confidential facts into backlog examples.
