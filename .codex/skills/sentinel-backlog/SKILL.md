---
name: sentinel-backlog
description: "Use when transforming mature Ignite Sentinel specs into the governed backlog and operating it: /backlog derivation from SPEC-U-* units, SLICE-PLAN ordering, story lifecycle and owners via /story-status, acceptance-criteria freeze and deltas, the BA board via /backlog-status, downstream findings via /implementation-feedback, and the INVEST/SPIDR/Lawrence slicing model. Trigger on 'generate the backlog', epic/user-story/acceptance-criteria work, story status changes, or implementation handoff."
---

# Sentinel Backlog

Use this skill to generate execution-ready backlog artifacts.

## Workflow

1. Run `python -m sentinel /maturity PROJECT_ID`.
2. Run `python -m sentinel /backlog PROJECT_ID`.
3. Review `workspaces/PROJECT_ID/08_context_packs/backlog_generation.json` to confirm focused local retrieval was used globally and under `per_story.US-NNN` for each Spec Unit-derived story.
4. Review `workspaces/PROJECT_ID/08_context_packs/implementation_readiness.json` to confirm each story has required domains, pending execution context, execution contract with anchors, retrieval plan, validation contract, dependencies, and freshness snapshot.
5. Review `workspaces/PROJECT_ID/04_backlog/SLICE-PLAN.md` and `workspaces/PROJECT_ID/08_context_packs/slice_plan.json` to confirm concrete EPIC-002 enablers, implementation waves, checkpoints, and per-story handoff packs are ordered without generating task IDs.
6. Review `workspaces/PROJECT_ID/04_backlog/EPIC-001.md` as the primary backlog artifact. It contains the epic, domain context coverage, story map, slicing rationale, retrieved context summary, agent execution contracts, retrieval plans, and embedded stories.
7. Review generated `US-00x.md` files only as story-level traceability and quality handoff mirrors.
8. Run `python -m sentinel /backlog-status PROJECT_ID` when the BA needs a current epic/status rollup or board view.
9. When status, owner, or Done evidence changes are needed, run `python -m sentinel /story-status PROJECT_ID --story US-NNN --set STATE --owner "NAME" [--evidence PATH]`.
10. Use `python -m sentinel /backlog PROJECT_ID --with-task-seeds` only when a downstream consumer explicitly asks for task-seed intentions.
11. When downstream implementation reports a dependency, gap, invalid AC, or missing surface, run `python -m sentinel /implementation-feedback PROJECT_ID --source FINDINGS.json`.
12. Run `python -m sentinel /quality PROJECT_ID`.
13. Run `python -m sentinel /trace PROJECT_ID` and `python -m sentinel /health PROJECT_ID`.

## Rules — Generating The Backlog (`/backlog`)

- Generate vertical, value-oriented stories. Avoid layer-only frontend/backend/data stories unless the item is explicitly framed as a spike or a valid cross-cutting enabler.
- Derive value stories from confirmed `03_specs/units/SPEC-U-NNN.md` files. One evidence-backed Spec Unit should become one vertical story.
- If no functional Spec Unit exists, keep a single `[PENDING INPUT]` backlog stub and push the issue upstream through gaps or `/specs`; do not expand the old fixed five-story scaffold.
- Every value story must cite `REQ-001`, `PRD-001`, `SPEC-001`, its `SPEC-U-*` source unit, and applicable `REQ-EARS-*` rows when available.
- `/backlog` returns `foundation_warnings` when the foundation it builds on (specs layer) drifted — its sources changed after generation. Explain the warning to the BA and recommend regenerating the stale upstream through its owning command (or confirming the change is immaterial) before building on it. Soft by default (`drift_gate.strict` opts into blocking); never "fix" drift by editing artifacts.
- Treat `sentinel/slicing/backlog_slicing_model.json` as the declarative source for the slicing model. It preserves the existing INVEST, vertical slicing, SPIDR, Lawrence, small-but-valuable and enabler-boundary guidance.
- Review each story's `Slicing Pattern` and `Slicing Rationale`; the runtime selects them from the declarative model according to the shape of the Spec Unit.
- Apply INVEST as a quality filter, but interpret `Small` as `small but valuable`: the smallest independently meaningful, testable, useful slice. Do not split below the value boundary into button/endpoint/table micro-stories that cannot be accepted on their own.
- Apply slicing patterns deliberately:
  - SPIDR: Spikes, Paths, Interfaces, Data, Rules.
  - Lawrence-style reduction: isolate the smallest useful variation first, then add workflow steps, edge cases, performance, external dependency, or discovery stories.
- Each story should include description, narrative, slicing pattern, dependencies, in/out of scope, context used, acceptance criteria, Definition of Ready, Definition of Done, and traceability.
- The story statement is phrased per the selected format: default `user` ("As a target user, I want ... so that ...") or, with `python -m sentinel /backlog PROJECT_ID --story-format job` (or the `story_format` field in `sentinel.config.yaml`, which the flag overrides), the JTBD-native `job` shape ("When [situation], I want [motivation], so I can [outcome]") — the natural output when the input names no persona, so none is invented. Only the wording changes; acceptance criteria, slicing, and traceability are identical, and a missing outcome stays `[PENDING INPUT]`.
- Acceptance criteria must be declarative Given/When/Then scenarios covering happy path, validation path, failure/recovery path, regression path, and quality evidence path.
- Classify acceptance criteria as `fail-to-pass`, `pass-to-pass`, or `evidence` so downstream Quality and implementation agents know which tests should become newly green, which existing regression must stay green, and which evidence proves completion.
- Cross-cutting enablers may be grouped in a dedicated enabler epic only when they are implementation work, frontend/backend/architecture, that must be built in advance to support confirmed functionality across stories, epics, FRs, or implementation surfaces.
- A valid enabler names the capability boundary it supports, why it must be built earlier, which risk/dependency it reduces, and what objective evidence proves completion.
- Reject loose enablers. Generic environment availability, broad infrastructure hardening, "make an internal tool accessible", or unspecified setup are preconditions/external tasks unless tied to confirmed project functionality and implementation evidence.
- Use progressive disclosure: retrieve focused local context for business value, functional slicing, technical dependencies, UX states, quality risks, and open uncertainty. For Spec Unit-derived stories, use the `per_story.US-NNN` mini-context instead of applying one epic-level context to every story.

## Rules — Interpreting The Handoff (context packs, SLICE-PLAN)

Full field-level detail of every handoff contract lives in [references/handoff-contracts.md](references/handoff-contracts.md); the operating rules are:

- Treat `implementation_readiness.json` as the handoff contract for downstream agents. If it reports `needs-context`, resolve missing domain context upstream or rerun `/reindex` and `/backlog` after domain owners update their files.
- Each epic/story should include `Domain Context Coverage` for Product, Technology, Design, Quality, and Delivery so humans and agents can see which domain evidence was used and what remains pending. Story coverage is computed from that story's mini-context; the global pack remains an aggregate index.
- Each story may include an `Agent Execution Contract` derived from retrieved context, with anchors (`source_path`, `section_path`, `line_start`, `line_end`) so agents can open the exact source range, and must include a `Retrieval Plan For Execution Agents` so planners, implementers, and testers know which focused `/retrieve` queries to run before touching code or tests.
- Treat `SLICE-PLAN.md` and `08_context_packs/slice_plan.json` as the deterministic ordering layer for downstream handoff: enablers first, value-story waves next, checkpoints between waves, and per-story handoff packs. They are not tasking artifacts; do not add task IDs, estimates, or implementation steps.
- Treat task seed contracts as an explicit scope boundary. They are emitted only with `/backlog --with-task-seeds`, contain implementation intentions traced to AC and critical surfaces, and never mean Ignite executes, estimates, assigns, schedules, or manages downstream tasks.
- Context packs carry scoring (IMP-007): `specs_generation.json` includes a `coverage_map` and `coverage_score` per retrieval section (`none`/`weak`/`strong`); `implementation_readiness.json` includes a per-story `readiness_score` (1.0 = ready) and a `summary` block with `avg_readiness_score` and `pending_context_by_domain`. Planning agents should prioritize stories by score and request the pending domain context before implementation.

## Rules — Governing The Lifecycle (`/story-status`, `/backlog-status`)

- Story lifecycle fields (`status`, `owner`) and DoR/DoD gate evidence are governed workspace state. Update them only via `/story-status`; never edit `US-NNN.md`, `BACKLOG.md`, `state.json`, or acceptance evidence records by hand. Moving a story into active execution may also auto-mark lagging peers `Stale` when the same `source_unit` or fallback `domain` diverges. Default `backlog_gate` warnings do not block; strict mode is opt-in.
- **Acceptance-criteria freeze:** `/story-status --set Ready` snapshots the story's acceptance criteria (hashed, `frozen_at`) into `state.json#acceptance_criteria_freezes`. From then on, backlog regeneration audits the current AC against the frozen snapshot: `changed`/`removed` criteria and `added_after_freeze` entries are written to `04_backlog/acceptance_criteria_deltas.md` and recorded in state history. Since IMP-187 that report also has a canonical `Delta` column (`ADDED`/`MODIFIED`/`REMOVED`) beside the nuanced `Change` column, so the `added_after_freeze` review signal is preserved while the marker stays machine-consumable. Frozen criteria must never change silently — when a regeneration produces deltas, walk the BA through that report before anyone builds against the story.
- Treat `04_backlog/BACKLOG.md` as a generated BA board from `/backlog`, `/story-status`, or `/backlog-status`, not as a source of truth. It rolls up current stories, including concrete EPIC-002 enabler stories when they exist, by epic and lifecycle status.
- If BA/Product intentionally proceeds despite a `WARN` from `/backlog-status` or a sub-`PASS` `/quality` verdict, use `--override PATH` with cited `decisions[]` in `DEC-*` shape so Sentinel records the rationale under `06_traceability/gate_overrides/` without changing the underlying gate verdict.
- If `/health` reports that domain context changed after backlog generation, do not hand off implementation from the stale backlog. Run `/reindex` and `/backlog` first.

## Rules — Downstream Feedback (`/implementation-feedback`)

- Downstream implementation feedback must enter through `/implementation-feedback`. Accepted findings are traced `CHG`/`GAP-FEEDBACK-*` records linked to existing stories or AC, may mark affected stories `Stale`, and may block DoD through `implementation_feedback_resolved`; they never rewrite backlog scope directly.

## Prioritization frameworks (coaching, the BA chooses)

Ignite governs the backlog and its ordering signals (SLICE-PLAN waves, readiness scores, dependencies) but does **not** impose a prioritization method or auto-rank value stories. When the BA is deciding *what to build first*, [references/prioritization-frameworks.md](references/prioritization-frameworks.md) is an educational menu of nine established frameworks (MoSCoW, Kano, RICE, ICE, WSJF, Value vs Effort, Opportunity Scoring, Cost of Delay, Story Mapping) — what each optimizes for, its inputs, when to reach for it, and its trap. Offer it in the coaching posture the maturity/health skills adopt (their `## Adaptive Decision Ladder`): surface the options and the trade-offs; the BA picks the frame. A score is only as good as its inputs — reach, impact, and effort must rest on cited evidence or explicit assumptions, never invented numbers.

## Anti-patterns

Each row is a mistake this skill exists to prevent, with the correction:

- **Splitting below the value boundary** — button/endpoint/table micro-stories that cannot be accepted on their own. → Read INVEST `Small` as *small but valuable*: the smallest independently meaningful, testable slice.
- **Layer-only stories** — a "backend story" plus a "frontend story" for one capability. → Generate vertical, value-oriented stories from one `SPEC-U-*` unit; reserve layer work for explicit spikes or valid cross-cutting enablers.
- **Loose enablers** — "harden infrastructure", "make the tool accessible", generic setup dropped into the enabler epic. → A valid enabler names the capability boundary it supports, why it must be built earlier, the risk it reduces, and the evidence of completion; reject the rest as preconditions.
- **Hand-editing the board** — fixing `BACKLOG.md`, `US-NNN.md`, `state.json`, or acceptance evidence directly. → Mutate only through `/backlog`, `/story-status`, and `/backlog-status`; the board is generated.
- **Building over silent AC drift** — regenerating and ignoring the acceptance-criteria deltas. → Walk the BA through `acceptance_criteria_deltas.md` (the canonical `Delta` column) before anyone builds against a re-frozen story.
- **Inventing domain detail** — filling in commands, test data, or design tokens to look complete. → Keep `[PENDING DOMAIN CONTEXT]` / `[PENDING INPUT]` visible and push the issue upstream.

## Guardrails (always)

- Keep source of truth in workspace files. Treat memory context as retrieval evidence, not as authority over project files.
- Treat domain context as living input across the whole lifecycle. Technology, Design, Quality, Delivery or other domain owners may add context files over time; `/ingest`, `/sync`, and `/reindex` make that context available for backlog retrieval.
- Do not invent Technology, Design or Quality execution details. If commands, files, design tokens, regression suites, handbook references, test data or blast-radius boundaries are missing, keep `[PENDING DOMAIN CONTEXT]` visible and push the issue upstream through `/context-request`, `/sync`, gaps, or domain updates.
- If required information is missing, keep `[PENDING INPUT]` visible and push the issue upstream through gaps, `/sync`, or domain context requests instead of inventing scope.
- Do not copy sensitive client details, credentials, private URLs, account IDs, raw payloads, or confidential facts into backlog examples.
