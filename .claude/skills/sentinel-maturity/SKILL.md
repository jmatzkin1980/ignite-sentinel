---
name: sentinel-maturity
description: "Use when deciding whether an Ignite Sentinel requirement is mature enough to generate specs or backlog: run /maturity, read the maturity report, its metrics (gap closure rate, maturity score, trend, requirement quality, maturation telemetry) and the development readiness matrix, and recommend the right remediation per case. Trigger on 'is it ready', 'can we generate specs/backlog yet', maturity checks, or a downstream command blocked by maturity."
---

# Sentinel Maturity

Use this skill before specs or backlog generation.

## Workflow

1. Run `python -m sentinel /maturity PROJECT_ID`.
2. Read `workspaces/PROJECT_ID/01_discovery/requirement_maturity_report.md`.
3. If readiness is `BLOCKED`, resolve critical or high gaps before proceeding.
4. If readiness is `READY_FOR_SPECS`, continue with `sentinel-specs` or `sentinel-backlog`.

## Rules

- Critical and high open gaps block downstream generation.
- Maturity is a gate, not a writing exercise.
- Prefer concise gap remediation questions over speculative completion.

## Metrics Block (summarize what the command actually returns)

`/maturity` returns a `metrics` block. Cover it in your summary — not just the readiness verdict:

- Core: `gap_closure_rate`, `open_gaps_by_severity`, `artifact_evidence_scores`/`evidence_score`, combined `maturity_score`, and `trend_vs_previous_run`. Recommend gap resolution when the trend is flat or negative.
- `requirement_quality` / `requirement_quality_score`: EARS-based quality of `requirements.md` statements (classifications plus warnings). A low score calls for EARS reformulations through `/resolve-gaps` confirmations, not manual rewriting.
- `maturation_telemetry`: where maturation stalls — how many `/resolve-gaps` rounds ran, closed gaps split by origin (checklist vs `annotate`/`challenge`/`scrutiny` agents) and by response source (client/domain/inference), open blocking count, and `EARS-eligible, not normalized` gaps. Use it to say *why* maturity is stuck, not just that it is.
- `brief_section_readiness` / `prd_section_readiness` (once those artifacts exist), `assumptions` (risk × uncertainty summary), and `development_readiness` + `unit_implementability` (below).

## Development Readiness Matrix

`/maturity` computes and persists `01_discovery/development_readiness.json` — read it and explain it instead of paraphrasing readiness:

- **Areas matrix**: 16 areas (`DRA-01`…`DRA-16`) from the mature-requirement rubric (identity/value, actors, scope, as-is/to-be, business rules, data/integrations, technology/frontend/backend readiness, NFRs, UX journey, design prototype, acceptance, quality handoff, delivery, backlog slicing), each scored per lens with status `CONFIRMED`, `ASSUMED`, or `OPEN`. Derived only from ledger/gaps/assumptions — an ungrounded area stays `OPEN` with explicit pending input; nothing is inferred.
- **`unit_implementability`**: per `RU-*` × lens matrix with statuses `CONFIRMED`, `DEFERRED_TO_CONTEXT` (a domain context pack can still answer it — discoverable, never blocks), and `OPEN` (non-inferable: only the client can answer). The summary names implementable, deferred, and not-implementable units and feeds the soft `implementability_gate` on `/brief`.

Recommend per case: `OPEN` cell or unit → chase the anchored `GAP-*` via `/resolve-gaps`; `DEFERRED_TO_CONTEXT` → raise a domain context request (`sentinel-domain-request`); `ASSUMED` → validate the backing assumption first when its priority signal is "watch closely" or "test before advancing".

## Adaptive Decision Ladder (coaching posture)

When the BA asks "what now?" after reading the report, don't hand down a single verdict — present the applicable rungs as numbered options with *use this when…* and surface the *why* as you go. The rung depends on the readiness state and the matrix, not on eagerness to advance. (Posture: the Adaptive Decision Ladder, Peters — extends the per-case remediation above.)

1. **Chase the blocking gaps** — use this when readiness is `BLOCKED` or any `OPEN` critical/high gap remains. Route them through `/resolve-gaps` (`sentinel-gap-response`). Why: critical/high open gaps mean the requirement's core is still unknown, so nothing downstream is trustworthy yet.
2. **Raise a domain context request** — use this when a cell or unit is `DEFERRED_TO_CONTEXT` (domain-discoverable, never blocking). Route via `sentinel-domain-request`. Why: the answer lives in a domain pack, not with the client, so asking the client would only stall.
3. **Validate the backing assumption first** — use this when a cell is `ASSUMED` and its priority signal is "watch closely" / "test before advancing". Why: advancing on an untested high-risk assumption is the cheapest place to be wrong.
4. **Proceed to specs/backlog** — use this when readiness is `READY_FOR_SPECS` and no blocking gaps remain. Continue with `sentinel-specs` or `sentinel-backlog`. Why: the gate is a floor, not a sign-off — proceeding is right once it clears, not before.

Name the rung you'd pick and why, but leave the choice to the BA; a flat or negative `trend_vs_previous_run` is itself a signal to stay on rung 1.
