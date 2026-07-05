---
name: sentinel-discovery
description: "Use when starting or refreshing Ignite Sentinel discovery for a project: ingest raw client requirements, regenerate the shareable gaps document, review discovery artifacts, or decide whether missing information becomes a gap. Covers /init, /ingest, /gaps, focused retrieval, RU-* requirement units, gap statuses and the evidence-or-silence rules. Trigger on new client input, 'run discovery', 'ingest this requirement', or any gaps.md work."
---

# Sentinel Discovery

Use this skill to start or refresh discovery for a project.

## Workflow

1. Confirm or create the project workspace with `python -m sentinel /init PROJECT_ID`.
2. Place domain-owned context in the workspace context folders when available:
   - `workspaces/PROJECT_ID/00_raw/01_business_context/`
   - `workspaces/PROJECT_ID/00_raw/02_technology_context/`
   - `workspaces/PROJECT_ID/00_raw/03_design_context/`
   - `workspaces/PROJECT_ID/00_raw/04_quality_context/`
   - `workspaces/PROJECT_ID/00_raw/05_interactions/`
3. Ingest raw material with `python -m sentinel /ingest PROJECT_ID --source PATH`.
4. Regenerate the shareable gap document when needed: `python -m sentinel /gaps PROJECT_ID`.
5. Use focused retrieval before analysis: `python -m sentinel /retrieve PROJECT_ID --query "DISCOVERY_TOPIC" --workflow discovery --write-pack`.
6. Review generated artifacts in `workspaces/PROJECT_ID/01_discovery/` and `02_requirements/`, especially `requirement_units.md`, `identity_seeds.md`, `discovery_log.md`, `lens_review.md`, `gaps.md`, and `requirements.md`.
7. Share `01_discovery/gaps.md` with the client or domain owner when maturity is blocked.
8. Run `python -m sentinel /health PROJECT_ID` before downstream specs or backlog work.

## Deepening Cycle After `/gaps`

The lexical checklist behind `/gaps` is the floor, not the ceiling. Once `gaps.md` exists, chain the agentic deepening passes — each has its own skill with the full contract:

1. `/annotate` (skill `sentinel-annotate`) — first pass, run it always: contribute the semantic gaps you detected by actually reading the raw input (ambiguity hiding behind a reassuring keyword, implicit assumptions the checklist cannot see).
2. `/challenge` (skill `sentinel-challenge`) — when the requirement looks complete and needs pressure: registry elicitation techniques (pre-mortem, role-play, assumption inversion, JTBD forces, plus the extended set) to surface what is NOT being said.
3. `/scrutinize` (skill `sentinel-scrutiny`) — when domain context folders have content or the lenses need a systematic pass: unstated assumptions, contradictions, mentions without counterpart, domain conflicts.
4. `/assume` (skill `sentinel-assume`) — only on an explicit BA decision to move forward over a gray area: governed, owned, cited assumptions instead of silent guesses.

Run 1 always; 2 and 3 when their trigger fits; 4 never on your own initiative. All four propose through governed commands — none of them closes gaps or edits artifacts directly.

## Memory

- Sentinel uses local LanceDB memory under `workspaces/PROJECT_ID/memory.lancedb/`.
- `/ingest` indexes generated artifacts and context folders so Codex can retrieve technology, design, quality, business, and interaction evidence without generating those domain specs.
- If artifacts were edited manually, run `python -m sentinel /reindex PROJECT_ID` before relying on `/retrieve`.

## Rules

- Treat raw input as evidence, not truth.
- Treat technology, design, and quality context folders as source input owned by external domains.
- Scrutinize every initial requirement through Product/BA, Technology, Design, and Quality lenses before declaring it mature.
- Use the mature requirement rubric in `lens_review.md`: identity/value, actors, scope, as-is/to-be delta, business rules, data/integrations, non-functional constraints, UX journey/states, acceptance/quality, delivery readiness, and PRD coverage readiness.
- Use `references/requirement-maturity-gap-checklist.md` when deciding whether missing information should become a gap. This checklist covers the sweet spot for Product, Design/prototype readiness, Technology deep-dive readiness, Frontend, Backend, and Quality handoff.
- Convert missing or ambiguous information into explicit `GAP` entries.
- Treat `gaps.md` as a human response contract and a framework artifact. Do not strip IDs, response fields, or the trace table.
- Gap statuses are `OPEN`, `PARTIALLY_CLOSED`, `ANSWERED`, `CLOSED`, `SUPERSEDED`, `NEW_REQUIREMENT`, and `NEW_GAP`. Critical/high `OPEN`, `PARTIALLY_CLOSED`, or `ANSWERED` gaps still block maturity.
- Do not invent metrics, users, scope, functional requirements, acceptance criteria, NFRs, dependencies, roadmap, or governance constraints.
- Preserve traceability from `RAW` to `RU`, `SEED`, `DISC`, `REQ`, `GAP`, and `DEC`.
- Treat `RU-*` Requirement Units as discovery-only analysis anchors cited from raw input. They do not replace `SPEC-U-*`, stories, enablers, or backlog slicing.
- Lenses run per unit (IMP-116): when Requirement Units exist, each gap is anchored to the `RU-*` whose cited evidence explains it (the `Unit` column in the `gaps.md` trace table), and each unit's evidence is scoped on its own so a trigger token present in one unit cannot suppress an inquisitive gap that belongs to another. Document-level gaps and legacy workspaces leave `Unit` as `N/A`. Do not remove the column.
- Discovery applies an inquisitive tier: when the input mentions a surface (screen, portal, api, integration) without describing its counterpart (journey, UI states, contracts, failure behavior, architecture input), the gap fires anyway and anchors the question to the detected mention (`evidence_mention`, rendered as "Evidence that triggers the question" in `gaps.md`). A bare mention never suppresses a question.
- Counterpart anchoring for surface concepts (IMP-117): naming a metric/KPI/indicator or auth/login/permission/role without its counterpart (definition/formula/source/threshold for metrics; auth method/permission model/role catalog for access) does not count as coverage — it raises a cited `medium` gap (`GAP-METRIC-DEFINITION`, `GAP-AUTH-MODEL`) instead of passing. If the concept is not named at all, nothing fires; if the counterpart is present, it is suppressed.
- Implementability probe (IMP-119): `/scrutinize --mode implementability-probe` is the pre-flight, per-`RU-*` mirror of `/implementation-feedback`, where a coding agent declares what it is missing to implement each unit. Full contract (unit anchoring, probe finding types, report) in the `sentinel-scrutiny` skill.
