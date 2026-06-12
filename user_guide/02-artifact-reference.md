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

Use this file to understand where the project is in the workflow.

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
```

For now, the maturity gate uses `blocking_gap_severities`.

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

### `decisions.md`

Pending or captured decisions that affect the requirement.

### `identity_seeds.md`

Atomic project truths and pending truths extracted from evidence. Seeds preserve origin, lens, status, and node type.

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

### `specs.md`

Generated by `specs`.

This is the compact agent-facing specification. It should be readable by:

- BA/Product
- Technical Leader
- Frontend
- Backend
- UX/UI
- Quality
- Test Automation
- Delivery
- AI agents

It includes a spec contract, requirement snapshot, backlog-relevant contract, JTBD, functional capabilities, progressive disclosure context map, backlog retrieval plan, backlog seeds, decisions, assumptions, and traceability. Agents should use the retrieval plan instead of loading every workspace document before backlog generation.

### `08_context_packs/specs_generation.json`

Generated by `specs`.

This context pack records the focused local-memory retrieval used to draft PRD sections. It is not the source of truth, but it makes progressive disclosure auditable and lets downstream agents retrieve the same section-oriented context without rereading the entire workspace.

## `04_backlog/`

Contains execution-oriented backlog artifacts.

### `EPIC-001.md`

Primary backlog artifact generated from specs and focused local memory retrieval.

Each epic file includes:

- YAML frontmatter for machine routing and Git-friendly review;
- epic outcome, source and retrieval summary;
- domain context coverage for Product, Technology, Design, Quality, and Delivery;
- slicing strategy based on Product Backlog transparency, INVEST, vertical slicing, SPIDR, and Lawrence-style smallest-useful-slice patterns;
- a story map with dependencies, labels, slicing patterns, and trace IDs;
- embedded user stories with description, narrative, context used, domain coverage, agent execution contract, retrieval plan for execution agents, in/out of scope, Given/When/Then acceptance criteria, Definition of Ready, Definition of Done, and traceability.

This is the main file a human reviewer should inspect before handing work to planning, implementation, or test agents.

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

This pack supports progressive disclosure: agents can inspect why context was retrieved without loading the whole workspace.

### `08_context_packs/implementation_readiness.json`

Machine-friendly handoff pack for downstream planning, implementation, and test agents.

It records, per story:

- readiness verdict: `ready` or `needs-context`;
- story type, title, dependencies, enabler links, and trace IDs;
- required domains such as Product, Technology, Design, Quality, or Delivery;
- pending execution context that must be resolved before implementation;
- retrieval plan with focused queries and workflow labels;
- validation contract: fail-to-pass, pass-to-pass, and evidence expectations;
- blast-radius boundaries and parallelization notes.

The pack also stores a domain context snapshot hash. If Technology, Design, Quality, Delivery, or other context files change after backlog generation, `/health` reports that the backlog may be stale and should be refreshed with `/reindex` and `/backlog` before implementation handoff.

## `05_quality/`

Contains quality and test coverage artifacts.

### `TC-001.md`

Generated test-case set linked to a user story.

### `backlog_readiness_audit.md`

Backlog readiness audit linked to user stories. It checks JTBD linkage, vertical slicing, testability, domain context citations, and traceability.

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

Append-only log of sync events, impacted nodes, new/unresolved gaps, and required follow-up actions.

### `00_client_responses/`

Controlled storage for client or domain gap answers processed by `/resolve-gaps`.

Generated reports follow this naming pattern:

```text
[source]_gap_resolution_report.md
```

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

## `memory.lancedb/`

Local memory area.

Primary local vector store:

- `lance/ba_memory.lance`

JSON fallback and metadata:

- `memory.json`
- `artifact_manifest.json`

This is a local retrieval index and fallback. It is not the source of truth.

## Context Pack Scoring

`specs_generation.json` exposes `coverage_map` and `coverage_score`: how many PRD retrieval sections found supporting evidence in local memory (`none`/`weak`/`strong` per section). `implementation_readiness.json` exposes a per-story `readiness_score` (1.0 means no pending context or execution fields) and a `summary` block (`stories_ready`, `avg_readiness_score`, `pending_context_by_domain`). Downstream agents can filter or prioritize stories by score instead of parsing prose.

## Regeneration Diffs

When `/specs` or `/backlog` regenerate an artifact that already existed and its content changed, Sentinel writes a summary under `07_changes/04_regeneration/` (`regen-NNN-<artifact>.md`): triggering change id, lines added/removed, and sections added/removed. The regenerated artifact remains the source of truth; the diff exists so humans can review what a change actually impacted before downstream handoff. These records are traced (`regeneration_diff` nodes, `triggers_regeneration` edges) and excluded from domain-context freshness hashing.

Change impact reports created by `/sync` also include `Reopened Closed Gaps` when new evidence triggers a gap ID that had previously been closed. This is a review signal, not an automatic state mutation: the BA decides whether to reopen, resolve again, or treat the change as out of scope.

## Base de Conocimiento de Lentes (`sentinel/lenses/`)

El conocimiento de los lentes (qué escruta cada lente, con qué severidad, qué tokens lo cierran y qué pregunta dispara) **no vive hardcodeado en Python**: es una fuente declarativa versionable bajo `sentinel/lenses/`, un archivo JSON por lente (`business.json`, `product.json`, `quality.json`, `technical.json`, `compliance.json`, `delivery.json`, `design.json`). El motor de discovery (`detect_gaps`) y los context-requests por dominio leen esa misma fuente, así que nunca divergen. Es 100% local: JSON puro, sin dependencias ni red (IMP-033).

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

Regla de identidad (invariante #1 de la propuesta de evolución): el modelo de lentes es conocimiento propio del equipo de Ignite. Esta base es el lugar para volcar esa experiencia de forma revisable en PR, no para copiar checklists genéricas de otras fuentes.
