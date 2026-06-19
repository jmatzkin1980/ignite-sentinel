# Ignite Sentinel Artifact Reference

This document explains the artifacts generated inside each project workspace.

## Workspace Root

```text
workspaces/[PROJECT_ID]/
```

Each project is isolated by ID. Do not mix unrelated client/project work in the same workspace.

## `state.json`

Operational state for the workspace.

Typical fields:

- `project_id`
- `phase`
- `health`
- `created_at`
- `updated_at`
- `artifacts`
- `project_language`
- `privacy_mode`
- `last_gap_resolution_id`
- `gap_counts`
- `readiness_stage`
- `metrics`
- `story_lifecycle`
- `story_gates`
- `story_quality`
- `story_acceptance_evidence`

Use this file to understand where the project is in the workflow. `story_lifecycle` is the governed ledger for current `US-NNN` status and owner; `story_gates` stores the latest DoR/DoD evaluation per story; `story_quality` stores the latest `/quality` score for the governed INVEST/SPIDR/Lawrence story model; `story_acceptance_evidence` records local evidence artifacts attached for Done; `implementation_feedback` records open downstream findings that may stale stories or block DoD. Mutate lifecycle and evidence only through `/story-status`; submit downstream findings only through `/implementation-feedback`; refresh quality through `/quality`.

## `sentinel.config.yaml`

Project-level configuration.

Default sections:

```yaml
project_id: PROJECT_ID
version: 0.1.0
project_language: auto
privacy_mode: local-only
domains:
  - product
  - business
  - functional
  - technical
  - design
  - quality
  - delivery
  - compliance
maturity:
  blocking_gap_severities:
    - critical
    - high
  required_domains:
    - product
    - functional
    - quality
memory:
  provider: lancedb-hybrid
  lancedb_optional: true
  fallback: json-hybrid
  embedding: local-hash
gap_resolution:
  auto_close_rule: confirmed_structured
backlog_gate:
  threshold: 1.0
  strict: false
privacy_scan:
  mode: warn
```

For now, the maturity gate uses `blocking_gap_severities`. `backlog_gate.strict` and `privacy_scan.mode` are opt-in hardening controls: their defaults keep backlog handoff non-blocking while still surfacing warnings.

`project_language` controls the language used for human-facing generated artifacts. Supported values:

- `auto`: detect language from the first ingested client requirement.
- `es`: force Spanish.
- `en`: force English.

The detected or configured language is also stored in `state.json` as `project_language`.

## `00_raw/`

Contains raw input copied from the source file used in `ingest`, plus the source manifest used by autonomous sync.

Examples:

- client notes
- meeting transcripts
- stakeholder emails converted to Markdown
- initial requirement briefs

Raw input is evidence. It is not automatically considered mature truth.

### `source_manifest.json`

Tracks files processed by `/ingest` and `/sync`.

Important fields:

- `path`
- `hash`
- `status`
- `event_id`
- `last_seen_at`
- `last_processed_at`

`/sync PROJECT_ID` uses this manifest to detect new or modified files.

## `01_discovery/`

Discovery artifacts created from raw input.

### `raw_input_digest.md`

Short summary of the ingested source.

### `gaps.md`

List of missing, ambiguous, risky, or unverified information.

This document is designed to be shared with client or domain stakeholders. It includes:

- project metadata and document version;
- response instructions;
- one human-friendly section per gap framed as elicitation (IMP-022): ID, title, lens, severity, description, **why it matters (risk if left open)**, **what answering it unblocks** (the downstream brief/PRD/spec section that consumes the answer), the question, the **expected response format**, an example answer, and blank response fields;
- a framework trace table with lens, severity, status, parent, question, source consulted, detected trigger, and `Origin` (`checklist` for deterministic gaps; `agent` for gaps contributed through `/annotate`, IMP-021).

When the answered document returns, save it under `input/interactions/` or `workspaces/PROJECT_ID/00_raw/05_interactions/` and run `/resolve-gaps PROJECT_ID --source PATH`.

Important statuses:

- `OPEN`
- `ANSWERED`
- `PARTIALLY_CLOSED`
- `CLOSED`
- `SUPERSEDED`
- `NEW_REQUIREMENT`
- `NEW_GAP`

Important severities:

- `critical`
- `high`
- `medium`
- `low`

### `agent_annotation_log.md` and `annotations/`

Sanctioned record of agentic discovery analysis contributed through `/annotate` (IMP-021). Each entry lists the merged semantic gaps with their lens, severity, question, and the verbatim evidence quote the agent cited, plus reported ambiguities and implicit assumptions. The raw analysis JSON is archived under `01_discovery/annotations/`. These gaps carry `origin: agent` in `gaps.md` and an `agent_annotation` traceability node linked from the raw input to the gap report. Source files remain the authority: the agent proposes with evidence; the runtime validates and persists.

### `challenge_report.md`

Versionable record of the advanced-elicitation pass contributed through `/challenge` (IMP-023). Groups the merged findings by lens, showing the technique that surfaced each one (pre-mortem, role-play, assumption inversion), plus the imagined failure modes and inverted assumptions the agent reported. These gaps carry `origin: challenge` in `gaps.md` and a `challenge_report` traceability node linked from the raw input to the gap report. Like `/annotate`, findings are validated against the raw input before merging — the agent proposes with evidence; the runtime is the authority. The raw analysis JSON is archived under `01_discovery/challenges/`.

### `scrutiny_report.md`

Versionable record of the deep scrutiny pass contributed through `/scrutinize` (IMP-066). It groups cited findings by lens and finding type: unstated assumptions, contradictions, mentions without counterpart, and domain conflicts. Findings may cite raw input or local domain context, but unsupported citations are rejected before anything is merged.

These gaps carry `origin: scrutiny` in `gaps.md`, create a `scrutiny_report` traceability node, and refresh `knowledge_state.md/json` so open scrutiny findings stay visible as governed ledger units instead of becoming free-form agent notes. The raw JSON source is archived under `01_discovery/scrutiny/`.

### `assumptions.md`

Governed assumption register contributed through `/assume` (IMP-067). It records explicit BA-owned assumptions with lens, statement, human owner, risk level, verbatim local justification, optional provisional `GAP-*` link, and lifecycle status.

Assumptions start as `ASSUMED`: the visible middle state between confirmed evidence and open uncertainty. Knowledge metabolism can later move them to `VALIDATED` when `/resolve-gaps` or structured `/sync` closes the linked gap, or to `INVALIDATED` when `/sync` receives explicit local evidence against an `ASM-*`. The ledger maps validated assumptions to `CONFIRMED` units and invalidated assumptions back to `OPEN` units. Downstream artifacts may cite assumptions explicitly, but an assumption never becomes confirmed scope without a governed gap answer.

### `decisions.md`

Pending or captured decisions that affect the requirement.

### `identity_seeds.md`

Atomic project truths and pending truths extracted from evidence. Seeds preserve origin, lens, status, and node type.

### `knowledge_state.md` and `knowledge_state.json`

Canonical discovery knowledge ledger generated by `/ingest`. It consolidates `identity_seeds.md`, `gaps.md`, and `decisions.md` into bounded knowledge units by lens, each with:

- `status`: `CONFIRMED`, `ASSUMED`, `OPEN`, or `INFERRED`;
- `evidence`: a trace ID plus quote, or `[PENDING INPUT]` when the knowledge is still open;
- `links`: seed, gap, decision, or artifact references that connect the unit back to the traceability graph.

Do not edit this ledger by hand. It is rebuilt by Sentinel from governed artifacts and exists so downstream agents can retrieve the current discovery state without treating memory as authority. `/resolve-gaps` and `/sync` refresh it after confirmations or explicit assumption invalidations.

### `development_readiness.json`

Machine-readable development certainty matrix generated by `/maturity` (IMP-068) under `01_discovery/`.

It turns the mature requirement coverage rubric from `lens_review.md` into 16 evaluable areas by Ignite lens. Every cell has:

- `status`: `CONFIRMED`, `ASSUMED`, or `OPEN`;
- `evidence`: a trace ID plus quote, governed assumption details, or `[PENDING INPUT]`;
- `links`: related gaps, assumptions, or area IDs;
- `score`: contribution to the lens/global certainty score.

The summary exposes status counts, per-lens scores, a global score, high-risk assumption IDs, and a Crystallization Gate verdict. This artifact does not replace `gaps.md`, `assumptions.md`, or `knowledge_state.json`; it is a derived view that makes development uncertainty explicit for `/maturity`, `/status`, and the dashboard.

### `discovery_log.md`

Multi-lens discovery log covering input census, JTBD, technology context, design context, quality/testability, atomic inventory, and refinement hooks.

### `lens_review.md`

Critical discovery review across four reviewer stances:

- Business/Product: outcome, users, scope, metric fidelity, and value intent.
- Technology: data sources, integrations, ownership, security, performance, and observability.
- Design: journey, screens, interaction states, accessibility, and UX resilience.
- Quality: acceptance strategy, testability, risks, negative paths, and evidence.

This artifact is designed to prevent thin discovery before PRD/spec/backlog generation. Critical and high gaps block maturity; medium gaps remain visible as assumptions or follow-up.

It also includes a mature requirement coverage rubric. The rubric checks whether the requirement has enough evidence for identity/value, actors, scope, as-is/to-be delta, business rules, data/integrations, technology deep-dive readiness, frontend/backend implementation surfaces, non-functional constraints, UX journey/states, design prototype readiness, acceptance/quality, quality handoff readiness, and delivery readiness.

### `requirement_maturity_report.md`

Readiness report generated by `maturity`.

Important verdicts:

- `READY_FOR_SPECS`
- `BLOCKED`

### `gap_resolution_log.md`

Append-only history generated by `/resolve-gaps`.

It records:

- change ID;
- resolution report ID;
- number of closed gaps;
- number of partially closed gaps;
- number of still-open gaps.

## `02_requirements/`

Contains the requirement register.

### `requirements.md`

Initial requirement artifact extracted from raw input.

This is the first structured step from raw client language toward AI-friendly specs and backlog.

When confirmed gap answers are already written in EARS syntax, Sentinel appends them under `Normalized Requirements (EARS)` as `REQ-EARS-*` rows with pattern, statement, and source. Generated PRD/spec/backlog artifacts cite those IDs; the source of truth remains this file.

### `project-brief.md`

Mature discovery brief generated by `maturity` when no critical or high gaps remain open.

It can also be generated explicitly with:

```powershell
python -m sentinel /brief PROJECT_ID
```

This is the crystallized handoff from iterative discovery into PRD/spec/backlog work. It uses the project-brief structure validated from mature real-world briefs:

- identity and value;
- business actors and role-level needs;
- product as-is/to-be process and journey;
- design flows and UX resilience;
- technical data, connectivity, and architecture;
- governance, constraints, decisions, seeds, inferences, and remaining gaps.

Narrative sections 1–6 are compiled from evidence, not templated (IMP-024). The compiler extracts initiative, objective, metric, actors, as-is/to-be, and scope from the raw client input and from confirmed answers of closed gaps (routed to their section by the IMP-022 gap→section map), citing the source for every claim. A sub-detail with no evidence references the gap that tracks it; a section with no anchor evidence renders an explicit `[PENDING INPUT]` pointing to its gap — never generic TBD or invented text.

The brief should hit the discovery sweet spot: complete enough for Design, Technology, Frontend, Backend, and Quality to start deep analysis, but not so detailed that it becomes their final deliverable. For Technology, this usually means endpoint/event inventory, create/modify/reuse decisions, source-of-truth ownership, constraints, and risks; full request/response contracts, schemas, dictionaries, and diagrams can live in dedicated context packs.

When present, `specs` uses this brief as its mature source instead of the thinner initial `requirements.md`.

## `03_specs/`

Contains the PRD and AI-friendly spec produced from the mature project brief and retrieved domain context.

### `prd.md`

Generated by `specs`.

This is the human/business-facing PRD. It explains what is being built, why it matters, scope, personas, functional requirements with acceptance criteria, NFRs, KPIs, JTBD traceability, dependency map, risks, assumptions, MVP/roadmap, mandatory constraints, team responsibilities, glossary, governance notes, pending inputs, audit trail, and traceability back to the mature requirement.

The first PRD sections are evidence-compiled rather than filled from a static template. `/specs` reads the mature brief, raw/source evidence, confirmed gap answers, EARS-normalized requirements, decisions, and focused local-memory retrieval. Claims are rendered with source IDs or source hints such as `REQ-*`, `REQ-EARS-*`, `CHG-*`, `DEC-*`, or `00_raw/`. If a section has no supporting evidence, Sentinel leaves `[PENDING INPUT]` with the `GAP-*` that must be resolved instead of inventing scope.

Closed gap answers are routed to PRD sections through the discovery gap map. For example, persona answers feed section 3, functional/acceptance answers feed section 4, and KPI/NFR answers feed sections 5 or 6. This keeps the PRD falsable: a reviewer can trace each populated line back to evidence or see the exact pending gap.

Agent-authored PRD enrichment can be merged through `/compose`. Accepted blocks appear under an `Agent Composition` subsection with `Origin: agent` and paragraph-level citations. Sentinel accepts only paragraphs whose citations are found verbatim in local source-of-truth artifacts, and it refuses to enrich PRD sections that still contain pending markers.

### `compositions/`

Generated by `/compose`.

This folder keeps the audit trail for PRD composition:

- the archived JSON source submitted to `/compose`;
- `accepted_blocks.json`, the machine-readable set of blocks that may be reapplied during `/specs` regeneration;
- `composition_report.md`, listing accepted and rejected blocks with reasons;
- `regeneration_report.md`, written when `/specs` reapplies or discards previously accepted blocks.

Composition artifacts are not a second source of truth. They are validated overlays on top of `prd.md`; if the cited evidence disappears or a target section becomes pending, regeneration discards the affected block and reports why.

### `specs.md`

Generated by `specs`.

This is the compact agent-facing specification index. It should be readable by:

- BA/Product
- Technical Leader
- Frontend
- Backend
- UX/UI
- Quality
- Test Automation
- Delivery
- AI agents

It includes a spec contract, requirement snapshot, backlog-relevant contract, spec-unit index, progressive disclosure context map, backlog retrieval plan, backlog seeds, decisions, assumptions, and traceability. Agents should use the retrieval plan and the referenced `SPEC-U-*` units instead of loading every workspace document before backlog generation.

### `units/SPEC-U-NNN.md`

Generated by `specs` when confirmed evidence supports a bounded execution unit.

Each unit has parseable frontmatter with stable `SPEC-U-NNN` ID, status, trace IDs, EARS IDs when applicable, and source anchors. The body points back to `requirements.md`, `prd.md`, and the confirmed normalized statement instead of restating a full implementation contract. Sentinel creates one unit per confirmed EARS statement today; fixed placeholders like `CAP-001`, `JTBD-001`, `US-001`, or `ASM-001` are not treated as source-backed spec units.

When `/specs` regenerates existing units, Sentinel writes a unit-level delta under `07_changes/04_regeneration/` named `regen-NNN-spec-units-delta.md`. The report classifies each unit as `ADDED`, `MODIFIED`, `REMOVED`, or `UNCHANGED`, summarizes frontmatter changes, EARS IDs, and source pointer changes, and traces the report to the triggering `CHG-*` when one exists. This lets BA and backlog agents inspect exactly which spec units changed instead of rereading the whole PRD/spec bundle.

### `08_context_packs/specs_generation.json`

Generated by `specs`.

This context pack records the focused local-memory retrieval used to draft PRD sections. It is not the source of truth, but it makes progressive disclosure auditable and lets downstream agents retrieve the same section-oriented context without rereading the entire workspace.

Its section queries come from `sentinel/retrieval_plans/specs_generation.json`. Each section records the active plan metadata (`query`, `filters`, `limit`, `budget_chars`, `lenses`, `source_sections`) plus result-level `read_plan` anchors (`source_path`, `section_path`, `line_start`, `line_end`) so reviewers can jump from summary to source.

## `04_backlog/`

Contains execution-oriented backlog artifacts.

### `EPIC-001.md`

Primary backlog artifact generated from evidence-backed Spec Units and focused local memory retrieval.

Each epic file includes:

- YAML frontmatter for machine routing and Git-friendly review;
- epic outcome, source and retrieval summary;
- domain context coverage for Product, Technology, Design, Quality, and Delivery;
- slicing strategy loaded from `sentinel/slicing/backlog_slicing_model.json`, based on Product Backlog transparency, INVEST, vertical slicing, SPIDR, and Lawrence-style smallest-useful-slice patterns;
- a story map with dependencies, labels, slicing patterns, and trace IDs;
- embedded user stories with description, narrative, context used, domain coverage, agent execution contract, retrieval plan for execution agents, optional task-seed contract, in/out of scope, Given/When/Then acceptance criteria, Definition of Ready, Definition of Done, and traceability.

Sentinel derives value stories from confirmed `03_specs/units/SPEC-U-NNN.md` files: one Spec Unit becomes one vertical story, and its AC evidence path cites the unit plus applicable `REQ-EARS-*` rows. When no functional Spec Unit exists, Sentinel renders one `[PENDING INPUT]` stub instead of the old fixed five-story scaffold, so missing evidence remains visible.

Each story records both `Slicing Pattern` and `Slicing Rationale`. The pattern is selected from the existing declarative slicing catalog according to the shape of the Spec Unit, without changing the cross-cutting enabler boundary.

This is the main file a human reviewer should inspect before handing work to planning, implementation, or test agents.

Agent-authored backlog refinement can be merged through `/refine-backlog`. Accepted proposals appear under an `Agent Backlog Refinements` subsection with `Origin: agent`, target stories, source units, recommendations, and verbatim citations. Sentinel accepts only proposals grounded in local source-of-truth artifacts, rejects pending stubs/units, and treats enabler candidates as concrete cross-cutting work only when they satisfy the existing `EPIC-002` boundary.

### `BACKLOG.md`

BA-facing backlog board generated by `/backlog`, `/story-status`, or `/backlog-status`.

This artifact summarizes the current backlog without becoming the source of truth. It is generated from:

- `state.json#story_lifecycle` for story status and owner;
- `state.json#story_gates` for the latest DoR/DoD evaluation;
- `04_backlog/US-NNN.md` for story identity, title, and parent epic;
- `08_context_packs/implementation_readiness.json` for readiness score, pending domain context, dependencies, and execution readiness.

The file contains:

- summary totals for stories, epics, Ready/Done percentages, average readiness, blockers, and owners;
- rollup by epic, including `EPIC-002` when concrete cross-cutting enabler stories exist;
- a board grouped by governed story status.

Do not edit `BACKLOG.md` manually. To change the board, update story lifecycle through `/story-status`, regenerate the backlog through `/backlog`, or refresh the view with `/backlog-status`.

### `SLICE-PLAN.md`

Deterministic implementation handoff plan generated by `/backlog`.

This artifact orders the backlog for downstream planning agents without turning Ignite into a tasking tool. It is generated from current story specs, concrete `EPIC-002` enabler links, `implementation_readiness.json`, DoR/DoD gate state, dependencies, retrieval plans, execution contracts and anchors.

The file contains:

- summary counts for stories, enablers, value stories and implementation waves;
- a Phase 0 table for concrete cross-cutting enablers when `EPIC-002` exists;
- implementation waves where stories can be planned in parallel once prerequisites are satisfied;
- checkpoints after enablers and each wave;
- a pointer to the machine-readable per-story handoff packs in `08_context_packs/slice_plan.json`.

Do not edit `SLICE-PLAN.md` manually. Rerun `/backlog` after upstream evidence, domain context, story dependencies, enabler links, or DoR/DoD signals change.

### `US-001.md`

Story-level mirror used by traceability and quality tooling.

Sentinel keeps individual `US-00x.md` files so downstream quality artifacts can link directly to a story node. The epic file remains the human-facing backlog bundle; story files repeat the critical story contract with source context, functional slice guidance, acceptance criteria, and readiness checklist.

Story mirrors also include an `Agent Execution Contract` and `Retrieval Plan For Execution Agents` when domain context is available. This contract can include:

- expected downstream agent profile;
- command hints from Technology context;
- critical files, services, APIs, data stores, or shared surfaces;
- design match signals from Design context;
- engineering practice or handbook references;
- autonomy limits: always, ask first, never;
- blast-radius boundaries;
- validation contract split into `fail-to-pass`, `pass-to-pass`, and evidence checks;
- parallelization or sequencing notes;
- focused `/retrieve` queries that implementation, planning, frontend/backend, design, and quality agents should run before executing the story.

When domain context is missing, Sentinel leaves `[PENDING DOMAIN CONTEXT]` instead of inventing commands, file paths, design tokens, regression suites, or implementation boundaries.

When `/backlog --with-task-seeds` is used, story mirrors also include a `Task Seed Contract`. It lists optional implementation intentions derived from the story's acceptance criteria and confirmed critical surfaces. This contract is a downstream planning aid only: Ignite does not execute, estimate, assign, schedule, or manage the seeds, and default `/backlog` does not render them.

Story mirrors receive the same `Agent Backlog Refinements` section when a validated proposal targets that story. These sections are review overlays, not rewritten scope.

Story mirrors also carry governed lifecycle frontmatter:

- `status`: one of `Draft`, `Ready`, `In Progress`, `In Review`, `Done`, `Blocked`, or `Stale`;
- `owner`: the accountable person, role, or team when assigned.

These fields are synchronized from `state.json` and must be changed with `/story-status`, not by editing Markdown directly. `/backlog` preserves existing lifecycle values on regeneration.

Story mirrors also render evaluated DoR/DoD checklists. Missing items remain visible under `DoR Gate Missing Items` or `DoD Gate Missing Items`; passed items are checked. The same evaluation is machine-readable in `08_context_packs/implementation_readiness.json`.

### `status_log.md`

Generated by `/story-status`.

This append-only review log records story lifecycle transitions with timestamp, story ID, previous status, new status, and owner. The source of truth for current state remains `state.json`; the log exists for human review and traceability.

### `acceptance_evidence/`

Generated by `/story-status --evidence PATH`.

This folder stores local downstream evidence files used to support a `Done` transition. Each copied artifact becomes a `story_acceptance_evidence` trace node linked to the story through `acceptance_evidence_for`. Sentinel registers the evidence; it does not execute tests.

### `refinements/`

Generated by `/refine-backlog`.

This folder keeps the audit trail for agentic backlog refinement:

- the archived JSON source submitted to `/refine-backlog`;
- `accepted_refinements.json`, the machine-readable set of accepted proposals with `origin: agent`;
- `refinement_report.md`, listing accepted and rejected proposals with reasons.

Refinement artifacts are not a second source of truth. They are governed proposals over `EPIC-001.md` and `US-NNN.md`; if evidence is missing, pending, non-verbatim, or outside the enabler boundary, Sentinel rejects the proposal instead of inventing backlog scope.

### `07_changes/05_implementation_feedback/`

Generated by `/implementation-feedback`.

This folder keeps the audit trail for downstream implementation findings:

- the archived JSON source submitted to `/implementation-feedback`;
- `feedback_report.md`, listing accepted and rejected findings with reasons.

Accepted findings are persisted in `state.json#implementation_feedback`, traced as `implementation_feedback` change events, and linked to the target story, optional AC, and optional `GAP-FEEDBACK-*`. They may mark only affected stories `Stale` and feed the DoD item `implementation_feedback_resolved`. They are not a second source of backlog scope and do not rewrite `US-NNN.md` beyond the generated gate checklist.

### `EPIC-002-cross-cutting-enablers.md`

Optional enabler epic.

Sentinel creates this only when source/context evidence mentions concrete cross-cutting implementation work such as frontend/backend foundations, architecture/SAD decisions, prototype-driven shared UI structure, auth, permissions, database/query/persistence, integration contracts, audit, logs, or observability. The work must be built in advance to support confirmed functionality across stories, epics, FRs, or implementation surfaces.

Do not use this epic for loose infrastructure or operational preconditions. Examples that should not become enabler stories by themselves:

- "make an internal tool accessible";
- "prepare environments";
- "general backend setup";
- "harden infrastructure";
- "create base project structure".

A valid enabler states which capability boundary it supports, why it must be built earlier, what risk or dependency it reduces, and how Quality can verify completion.

### `08_context_packs/backlog_generation.json`

Focused local retrieval pack used by `/backlog`.

It records which local memory chunks were consulted for:

- epic value and MVP;
- functional slicing and acceptance criteria;
- technical dependencies;
- execution commands and critical surfaces;
- engineering practices;
- UX states;
- design match;
- quality risks;
- regression contract;
- open uncertainty.

This pack supports progressive disclosure: agents can inspect why context was retrieved without loading the whole workspace. The top-level `sections` block is the aggregate backlog view; `domain_context_coverage` summarizes that global coverage. When value stories are derived from `SPEC-U-*` files, the `per_story` block stores `US-NNN` mini-contexts built from the story's Spec Unit statement and the same declarative retrieval sections, so `critical_surfaces`, design signals, quality signals, and coverage can differ by story.

Its section queries come from `sentinel/retrieval_plans/backlog_generation.json`, with the same per-result `read_plan` anchors used by `/retrieve` and `/specs`. Those anchors are also propagated into story execution signals under `execution_contract.*.anchor`.

### `08_context_packs/implementation_readiness.json`

Machine-friendly handoff pack for downstream planning, implementation, and test agents.

It records, per story:

- readiness verdict: `ready` or `needs-context`;
- story type, title, dependencies, enabler links, and trace IDs;
- required domains such as Product, Technology, Design, Quality, or Delivery;
- pending execution context that must be resolved before implementation;
- full `execution_contract` used by the story handoff, including `anchor` pointers for confirmed commands, critical surfaces, design match, and engineering practices when retrieved;
- retrieval plan with focused queries and workflow labels;
- validation contract: fail-to-pass, pass-to-pass, and evidence expectations;
- blast-radius boundaries and parallelization notes.
- optional `task_seed_contract` when `/backlog --with-task-seeds` was requested; default backlog generation omits it.

The pack also stores a domain context snapshot hash. If Technology, Design, Quality, Delivery, or other context files change after backlog generation, `/health` reports a freshness warning. Refresh retrieval with `/reindex` before implementation handoff, and rerun `/backlog` only when the change materially affects story scope, sequencing, acceptance criteria, dependencies, or execution contracts.

If `/specs` is regenerated after this pack exists, Sentinel adds `stale_spec_units`: changed `SPEC-U-*` units with their delta status and report path. Implementation agents should treat those entries as a review signal before executing stories that cite the affected unit.

### `08_context_packs/slice_plan.json`

Machine-readable mirror of `04_backlog/SLICE-PLAN.md`.

It contains:

- `phases.enabler_phase`: concrete `EPIC-002` enabler stories that should be accepted or explicitly stubbed before dependent value stories start;
- `phases.implementation_waves`: ordered waves of stories that can be planned in parallel after their prerequisites;
- `phases.positions`: per-story phase, wave, order, parallel group and prerequisites;
- `checkpoints`: review points after enablers and each wave;
- `handoff_packs.US-NNN`: per-story position, lifecycle state, owner, readiness score, DoR/DoD, dependencies, `execution_contract`, `retrieval_plan`, anchors, validation contract, trace IDs and context-pack pointer.

This JSON is for downstream planners and implementation/test agents. It deliberately avoids task IDs, estimates, or execution instructions beyond the governed handoff context.

## `05_quality/`

Contains quality and test coverage artifacts.

### `TC-001.md`

Generated test-case set linked to a user story.

### `backlog_readiness_audit.md`

Backlog readiness audit linked to user stories. It now contains a dynamic story census with INVEST/SPIDR score, status, per-check findings, and a non-blocking verdict. The checks preserve the existing slicing model: governed slicing pattern, vertical story or concrete `EPIC-002` enabler boundary, small-but-valuable scope, AC coverage, traceability, and explicit dependencies. The same result is machine-readable in `state.json#story_quality` and feeds the DoR warning item `story_quality_invest` after `/quality` runs.

## `06_traceability/`

Contains graph, matrix, and health outputs.

### `traceability_graph.json`

Machine-readable graph of nodes and edges.

### `traceability_matrix.md`

Human-readable table of source-target relationships.

### `traceability_graph.md`

Mermaid diagram of the graph.

### `health_report.md`

Human-readable health report.

### `health_report.json`

Machine-readable health verdict and findings.

## `07_changes/`

Contains controlled change events.

### `[source].md`

Copied source of the change.

### `[source]_impact_report.md`

Impact report generated by `sync`.

Use this before patching specs or backlog.

### `metabolism_log.md`

Append-only log of sync events, impacted nodes, new/unresolved gaps, impacted knowledge units, downstream stale artifacts, and required follow-up actions.

### `00_client_responses/`

Controlled storage for client or domain gap answers processed by `/resolve-gaps`.

Generated reports follow this naming pattern:

```text
[source]_gap_resolution_report.md
```

Each report includes closed, answered, partial, and still-open gaps. After IMP-069 it also includes `Knowledge Ledger Metabolism`: refreshed ledger/readiness paths, impacted `KLU-*` units, validated assumptions, and downstream artifacts that should be reviewed for staleness.

## `08_context_packs/`

Contains retrieval context packs generated by:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "..." --workflow sync --write-pack
```

These packs help Codex load only the context needed for a workflow.

### `requests/`

Domain-specific context requests generated by `/context-request`.

Examples:

- `technology_context_request.md`
- `design_context_request.md`
- `quality_context_request.md`
- `frontend_context_request.md`
- `backend_context_request.md`

Each request's "Lens Checks To Cover" section frames every lens check as elicitation (IMP-022): besides the check description and its `why`, it states what answering it **unblocks** downstream and the **expected format** of a closing answer — the same three factors surfaced per gap in `gaps.md`.

### `exports/`

Shareable artifact copies generated by `/export`.

### `views/`

Read-only artifact views generated by `/view`.

Examples:

- `gaps.html`
- `brief.html`
- `prd.html`
- `specs.html`
- `backlog.html`

These HTML files are self-contained local snapshots derived from Markdown source artifacts plus workspace state and traceability. They are ignored by git and can be rebuilt at any time. The Markdown files remain the source of truth; review feedback should enter through governed commands such as `/resolve-gaps`, `/sync`, `/annotate`, or `/compose`.

The marker panel is a derived review aid. `GAP-*` markers are enriched from `01_discovery/gaps.md` with lens, severity, status, why the gap matters, what it unblocks, and the expected answer format. `ASM-*` / `ASSUMED` markers are enriched from `01_discovery/assumptions.md` with owner, risk, statement, status, and linked gap. Section badges summarize whether the visible artifact section is populated, still pending, or proceeding under a governed assumption.

The evidence panel is also derived. Backticked trace IDs such as `REQ-001`, `FR-001`, `SPEC-U-001`, `US-001`, `AC-001`, `RAW-001`, `GAP-*`, or `ASM-*` are resolved only when a matching node exists in `06_traceability/traceability_graph.json`. For each matched node the view embeds a bounded local source fragment and a one-hop mini graph made from real trace edges. Missing nodes remain visible as unmatched citations; the view never fabricates evidence or graph relationships.

The feedback panel is local browser state. It stores anchored comments in `localStorage` and exports Markdown instead of writing to source artifacts. Comments on `GAP-*` markers are shaped as existing `/resolve-gaps` answer blocks; other comments are plain review notes suitable for `/sync --source PATH --note "Artifact review feedback"`.

## `memory.lancedb/`

Local memory area.

Primary local vector store:

- `lance/ba_memory.lance`

JSON fallback and metadata:

- `memory.json`
- `artifact_manifest.json`

This is a local retrieval index and fallback. It is not the source of truth.

## Context Pack Scoring

`specs_generation.json` exposes `coverage_map` and `coverage_score`: how many PRD retrieval sections found supporting evidence in local memory (`none`/`weak`/`strong` per section). `implementation_readiness.json` exposes a per-story `readiness_score` (1.0 means no pending context or execution fields), DoR/DoD gate results, lifecycle status/owner, and a `summary` block (`stories_ready`, `avg_readiness_score`, `pending_context_by_domain`). Downstream agents can filter or prioritize stories by score instead of parsing prose.

Once `03_specs/prd.md` exists, `/maturity` and `/status` also expose `maturity_metrics.prd_section_readiness` (IMP-041): numbered PRD sections 1-13, per-section status, evidence citation count, `coverage_score`, and feeding gaps for poor sections. `/specs` returns the same block plus `specs_gate`; strict blocking is opt-in through workspace config and reports `SPECS_BELOW_THRESHOLD` instead of silently pushing weak PRD sections downstream.

## Regeneration Diffs

When `/specs` or `/backlog` regenerate an artifact that already existed and its content changed, Sentinel writes a summary under `07_changes/04_regeneration/` (`regen-NNN-<artifact>.md`): triggering change id, lines added/removed, and sections added/removed. The regenerated artifact remains the source of truth; the diff exists so humans can review what a change actually impacted before downstream handoff. These records are traced (`regeneration_diff` nodes, `triggers_regeneration` edges) and excluded from domain-context freshness hashing.

Change impact reports created by `/sync` also include `Reopened Closed Gaps` when new evidence triggers a gap ID that had previously been closed. This is a review signal, not an automatic state mutation: the BA decides whether to reopen, resolve again, or treat the change as out of scope.

After IMP-069, `/sync` impact reports also include structured gap responses applied by sync, `Knowledge Ledger Metabolism`, and downstream staleness. Use these sections to see which `KLU-*` units moved, which assumptions were validated or invalidated, and whether brief, PRD, specs, backlog, or readiness packs need review before implementation handoff.

## Base de Conocimiento de Lentes (`sentinel/lenses/`)

El conocimiento de los lentes (qué escruta cada lente, con qué severidad, qué tokens lo cierran y qué pregunta dispara) **no vive hardcodeado en Python**: es una fuente declarativa versionable bajo `sentinel/lenses/`, un archivo JSON por lente (`business.json`, `product.json`, `quality.json`, `technical.json`, `compliance.json`, `delivery.json`, `design.json`). El motor de discovery (`detect_gaps`) y los context-requests por dominio leen esa misma fuente, así que nunca divergen. Es 100% local: JSON puro, sin dependencias ni red (IMP-033).

IMP-046 agrega una regla práctica para checks "grado PRD": un token tranquilizador no debe cerrar una pregunta si no trae detalle consumible por PRD/specs. Por ejemplo, `goal/objective` no alcanza para cerrar detalle de personas si faltan dolor, frecuencia o proficiencia; una métrica o target no alcanza para cerrar NFR/KPI si faltan método de medición y ventana; y un plan de ejecución necesita rollout, ambientes o restricciones de release explícitas.

Cada lente tiene una lista `checks`; cada check declara:

- `id`: identificador estable `GAP-*`.
- `severity`: `critical | high | medium | low`.
- `description`: qué falta (en inglés, como en los artefactos).
- `rule`: cómo dispara el check.
  - `absent_tokens`: dispara cuando **ninguno** de los `tokens` aparece en la evidencia.
  - `mention_without_counterpart`: tier inquisitivo — dispara cuando se menciona una superficie (`triggers`) pero falta su contracara (`counterparts`); ancla la pregunta a la mención detectada.
  - `metric_without_source`: dispara cuando hay una métrica cuantitativa pero no aparece ninguno de los `suppressors` (palabras de fuente/baseline).
- `evidence_scope`: qué texto lee la regla — `source | technical | design | quality | frontend | all`.
- `why` (opcional): la experiencia de campo que motiva el check; notas del equipo, se muestran en el context-request.

### Cómo agregar conocimiento a un lente (sin tocar Python)

1. Abrí el archivo del lente correspondiente, por ejemplo `sentinel/lenses/technical.json`.
2. Agregá un objeto nuevo al array `checks` con los campos de arriba. Ejemplo:

   ```json
   {
     "id": "GAP-OBSERVABILITY-RUNBOOK",
     "severity": "medium",
     "rule": "absent_tokens",
     "evidence_scope": "technical",
     "description": "Runbook and on-call ownership for the new surface are not explicit.",
     "tokens": ["runbook", "on-call", "oncall", "guardia"],
     "why": "Sin runbook ni owner de guardia, una falla en produccion no tiene dueno."
   }
   ```

3. Listo: el check aparece automáticamente en `gaps.md` al correr `/ingest` o `/gaps`, y en el context-request del dominio del lente al correr `/context-request`. No hay que tocar código.
4. Si cambiás el comportamiento de detección, corré `python tests/evals/run_discovery_evals.py` para confirmar que no introdujiste regresiones en los fixtures, y la suite con `python -m unittest discover -s tests`.

Para checks PRD-grade, actualizá también `tests/fixtures/evals/*/answer_key.json` (`must_fire`/`must_not_fire`) y, cuando haga falta atravesar gates reales hasta `/specs`, agregá una respuesta sintética en `gap_responses.md` del fixture. La expectativa es cero falsos positivos nuevos y preguntas que expliquen qué sección del PRD desbloquean.

Para cambios de backlog, usá el bloque `backlog` de los mismos answer keys. Ahí se registran historias esperadas, `SPEC-U-*` fuente, comportamiento de no-invención, patrón de slicing esperado y checks opt-in de anchors/contexto. `python tests/evals/run_discovery_evals.py` debe reportar cobertura de derivación, no-invención y slicing sin regresiones antes de abrir PR.

Regla de identidad (invariante #1 de la propuesta de evolución): el modelo de lentes es conocimiento propio del equipo de Ignite. Esta base es el lugar para volcar esa experiencia de forma revisable en PR, no para copiar checklists genéricas de otras fuentes.
