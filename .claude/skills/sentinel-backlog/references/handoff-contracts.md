# Backlog Handoff Contracts — Field-Level Detail

Reference for the downstream handoff artifacts `/backlog` produces. `SKILL.md` says when to use each contract; this file details what each one carries so agents and BAs can read them without guessing.

## `08_context_packs/implementation_readiness.json`

The handoff contract for downstream agents. Per story it carries:

- required domains and pending execution context per domain
- the agent execution contract (with anchors, see below)
- the retrieval plan for execution agents
- the validation contract (what proves the story done)
- dependencies and a freshness snapshot of the evidence used

Scoring (IMP-007): a per-story `readiness_score` (1.0 = ready) plus a `summary` block with `avg_readiness_score` and `pending_context_by_domain`. Planning agents prioritize stories by score and request the pending domain context before implementation. A `needs-context` report means: resolve missing domain context upstream, or rerun `/reindex` and `/backlog` after domain owners update their files.

## Agent Execution Contract (per story)

Derived from retrieved context, never invented: agent profile, command hints, critical surfaces, design match, engineering practices, autonomy limits, blast radius, validation contract, and parallelization/sequencing notes. Confirmed context signals include anchors — `source_path`, `section_path`, `line_start`, `line_end` — so agents open the exact source range instead of re-reading whole files.

## Retrieval Plan For Execution Agents (per story)

The focused `/retrieve` queries that planners, implementers, and testers should run before touching code or tests. Runs against local workspace memory only.

## `04_backlog/SLICE-PLAN.md` + `08_context_packs/slice_plan.json`

The deterministic ordering layer for downstream handoff: enablers first, value-story waves next, checkpoints between waves, and per-story handoff packs bundling execution contract, retrieval plan, and anchors. Not tasking artifacts: no task IDs, no estimates, no implementation steps.

## Task seeds (opt-in)

Emitted only with `/backlog --with-task-seeds`. They contain implementation intentions traced to acceptance criteria and critical surfaces. They never mean Ignite executes, estimates, assigns, schedules, or manages downstream tasks.

## Context packs and scoring

- `08_context_packs/backlog_generation.json`: the focused local retrieval evidence used — global sections plus `per_story.US-NNN` mini-contexts for Spec Unit-derived stories.
- `08_context_packs/specs_generation.json`: includes a `coverage_map` and `coverage_score` per retrieval section (`none` / `weak` / `strong`).

## Domain Context Coverage (per epic/story)

Product, Technology, Design, Quality, and Delivery evidence used versus pending. Story coverage is computed from that story's own mini-context; the global pack remains an aggregate index.
