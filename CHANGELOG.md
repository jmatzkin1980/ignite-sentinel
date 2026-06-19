# Changelog

All notable changes to Ignite Sentinel vNext are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `/dashboard` generates a local, read-only, self-contained `dashboard.html` portfolio view for all workspaces, with lifecycle pipeline, gaps copy flow, embedded markdown documents, backlog rollup, gates, warnings, and suggested prompts/commands.
- `sentinel-dashboard` skill and user guide page document natural-language dashboard generation, interpretation, and the section/stage registry contract for safe dashboard evolution.
- `/ingest` now materializes a discovery knowledge ledger (`01_discovery/knowledge_state.md` and `.json`) with lens-scoped `CONFIRMED`/`ASSUMED`/`OPEN`/`INFERRED` units, evidence or `[PENDING INPUT]`, traceability links, local memory indexing, and a `/status` summary.
- `/scrutinize` adds governed multi-lens discovery scrutiny: cited findings from raw input or domain context become `origin: scrutiny` gaps, `scrutiny_report.md`, traceability edges, and refreshed ledger units.
- `/self-review` adds a skeptical PRD/spec review channel: cited findings become `origin: self-review` gaps, hard-to-reverse decisions are registered under `03_specs/self_review/`, and generated PRD/spec artifacts are not auto-edited.
- `/assume` registers governed BA-owned assumptions with human owner, risk, verbatim local basis, optional provisional gap link, `assumptions.md`, traceability, maturity/status risk summary, and `ASSUMED` ledger units.
- `/maturity` now persists `01_discovery/development_readiness.json`, a 16-area lens readiness matrix with `CONFIRMED`/`ASSUMED`/`OPEN` cells, evidence, scores, and a Crystallization Gate verdict exposed through `/status` and the dashboard.
- `/resolve-gaps` and `/sync` now metabolize governed knowledge into the ledger: confirmed answers can validate assumptions, explicit `ASM-*` invalidations open linked ledger units, development readiness is recalculated, impact reports name affected `KLU-*` units, and `/health` flags stale downstream artifacts.
- `/view` generates a local, read-only, self-contained HTML view for one artifact (`gaps`, `brief`, `prd`, `specs`, or `backlog`) with section navigation, markers, citations, and trace-node context. Its marker panel now enriches gaps and governed assumptions with lens/severity/status, why/unblocks/expected-format, owner/risk, inline `#marker-*` anchors, filtering, and section certainty badges.
- `/view` evidence chips now resolve trace IDs against the real local graph, embed bounded source fragments, and render one-hop mini trace graphs without network or external libraries.
- `/view` now includes a local feedback loop: reviewers can save section or marker comments in `localStorage` and export Markdown shaped for existing `/resolve-gaps` and `/sync` flows, without the HTML writing to source artifacts or introducing a new parser format.
- `/view` now includes guided response mode: gap and assumption markers are classified as client, domain, or BA/assumption items, client questions are shown by default, and local draft progress is tracked in `localStorage`.
- Artifact views now derive sections from a governed Markdown-to-blocks interlingua with a closed catalog (`section`, `requirement-table`, `persona`, `ears-statement`, `decision`, `traceability`, `pending`, `assumption`) and fixture-tested Markdown round trips. Markdown remains the source of truth.

### Changed
- Backlog privacy scan is now configurable through `privacy_scan.mode` (`off`, `warn`, `block`) and defaults to non-blocking `warn`; `block` preserves the previous hard gate as opt-in.

## [0.1.0] — 2026-06-14

First consolidated release of the governed requirement-maturation lifecycle (Discovery → Specs → Backlog), local-first and fully reconstructible from versionable workspace files.

### Discovery → Brief
- Inquisitive, lens-based gap detection with an externalized lens registry (`sentinel/lenses/`).
- Sanctioned agentic channels validated against verbatim citations: `/annotate` (semantic gaps) and `/challenge` (pre-mortem + per-lens role-play).
- EARS normalization of confirmed functional answers into testable `REQ-EARS-*` statements.
- Evidence-compiled project brief with per-section readiness and maturation telemetry; reopened-gap tracking on `/sync`.

### Specs
- `/specs` emits a human PRD, a compact spec index, and bounded `SPEC-U-*` units derived from confirmed evidence.
- `/compose` merges cited agent-authored PRD narrative (`Origin: agent`); unsupported citations rejected.
- Unit-level deltas and stale-unit propagation on regeneration.

### Backlog — Horizon 8 (governed backlog)
- Stories derived from confirmed Spec Units instead of a fixed seed list; `[PENDING INPUT]` stubs instead of invented scope.
- Externalized slicing model (`sentinel/slicing/`) preserving INVEST ("small but valuable"), vertical slicing, SPIDR and Lawrence, with one explained pattern per story.
- Bounded cross-cutting enabler epic (`EPIC-002`) with strict acceptance.
- Per-story progressive-disclosure context (`per_story.US-NNN`) with `read_plan` anchors propagated into story execution signals.
- `SLICE-PLAN.md` + `slice_plan.json` deterministic handoff with a pre-handoff DoR gate (soft by default, strict opt-in); optional `--with-task-seeds` that never execute, estimate, assign, or schedule.
- Governed story lifecycle and BA rollup board: `/story-status`, `/backlog-status`.
- `/quality` INVEST/SPIDR/Lawrence scoring with a dynamic `backlog_readiness_audit.md` feeding DoR warnings.
- Agentic `/refine-backlog` (cited proposals) and downstream `/implementation-feedback` loop (`GAP-FEEDBACK-*`, DoD gating).
- Backlog answer-key evals; deterministic local privacy scan over `04_backlog/`.

### Memory & platform
- Layered local retrieval: optional semantic embeddings and LanceDB hybrid (vector + FTS + reciprocal rank fusion), with a first-class deterministic `json-hybrid` fallback.
- Heading-aware chunking with `section_path` and line anchors; incremental reindex by `source_hash` / `embedding_version` / `chunking_version`.
- Single command manifest drives Kilo / Claude / Codex / MCP adapters and skill mirrors; local stdio MCP server.
- `verify.ps1` runs the unit suite, `/doctor`, and the eval harness (discovery, brief, PRD, specs, backlog, retrieval).
