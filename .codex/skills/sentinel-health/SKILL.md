---
name: sentinel-health
description: "Use when auditing an Ignite Sentinel workspace before or after downstream work: /health findings (traceability, blocking gaps, unbacked metrics, memory indexing, staleness), /validate structural verdict plus non-blocking semantic-quality and cross-artifact consistency warnings, and gate overrides with cited DEC-* decisions. Trigger on 'is the workspace healthy', a DIRTY verdict, validation warnings, or the final pre-handoff check."
---

# Sentinel Health

Use this skill as the final gate for any Sentinel workflow.

## Workflow

1. Run `python -m sentinel /health PROJECT_ID`.
2. Review `workspaces/PROJECT_ID/06_traceability/health_report.md`.
3. If verdict is `DIRTY`, fix each finding **by running the governed command that owns the artifact** and rerun health. Health findings are never fixed by editing artifacts.
4. Use `python -m sentinel /trace PROJECT_ID` when findings mention traceability.

## Rules

- Health is based on versionable artifacts and deterministic checks.
- LanceDB or fallback memory cannot override source files.
- Metrics without explicit source or baseline are findings.
- **Out-of-CLI edit detection (IMP-147):** every mutating command snapshots the sha256 of the governed artifacts into `state.json#artifact_hashes`; `/health` recomputes and compares. A mismatch means someone hand-edited a governed artifact — recommend regenerating it through its owning Sentinel command. Never "fix" the mismatch by editing the file back or touching `state.json`; the check warns, it does not revert.
- **Knowledge staleness:** after a change moves knowledge units, `state.json#knowledge_staleness` lists the downstream artifacts now stale. The finding clears only when those artifacts are regenerated via their commands (`/health` compares each artifact's mtime against the marker's `recorded_at`); unrelated passes do not clear it.
- **`needs_context` gate:** when workspace memory has too little indexed context for reliable downstream retrieval, `/health` raises it — as a warning by default, as a blocking finding in strict mode. The remediation is upstream: add/ingest domain context and `/reindex`, not proceed anyway.
- Domain context freshness: if domain context files changed after specs/backlog generation, health flags the stale derivation — regenerate via `/reindex` + the owning command before handoff.
- `/validate` also emits a non-blocking `semantic_quality` block (IMP-006): per-artifact score and classification (`evidence-backed` / `mixed` / `scaffolding`) for brief, PRD, and specs, plus `warnings`. Use it to decide whether downstream handoff content is mature, separate from structural validity.
- `/validate` also emits non-blocking `cross_artifact_consistency` warnings (IMP-045/IMP-134): brief->PRD continuity, confirmed `REQ-EARS-*` coverage in specs/spec units, FR extraction coverage, resolvable spec-unit source pointers, orphan EARS references, and lost `SPEC-U-*` statements between specs and backlog acceptance criteria. Report the layer, artifact, and suggested corrective command without treating the warning as a failed structural verdict.
- `/validate` folds in non-blocking Mom-Test warnings (IMP-180) over the questions in `gaps.md`: any elicited question phrased as a hypothetical or future opinion ("would you like…?", "¿le gustaría…?") instead of asking about a concrete past event is flagged with the question cited. It is advisory question-quality feedback, not a structural failure; questions about future *system* capacity are exempt.
- `/validate` emits an `iso29148_coverage` report (IMP-189): the nine ISO/IEC/IEEE 29148 individual-requirement quality characteristics, each `covered` (with the deterministic checks that cover it via `covers_29148`), an open `heuristic_gap`, or `out_of_scope` with a stated reason. Characteristics no local deterministic heuristic can honestly decide — Complete, Feasible, Correct, Necessary — are declared out of scope rather than simulated. The block also lists `verifiability_findings`: requirement statements (including well-formed EARS ones) that carry no measurable or observable acceptance anchor. Use it as an auditability lens against the standard, not a gate.
- If BA/Product intentionally proceeds despite `/validate`, use `--override PATH` with cited `decisions[]` in `DEC-*` shape. Sentinel writes the rationale to `06_traceability/gate_overrides/` but keeps the structural `VALID` / `INVALID` result unchanged.

## Adaptive Decision Ladder (coaching posture)

When `/health` returns findings, present the remediation as numbered rungs — *use this when…* plus the *why* — instead of a single instruction. The owning command, never a hand-edit, is always the route. (Posture: the Adaptive Decision Ladder, Peters.)

1. **Regenerate the artifact through its owning command** — use this when a finding is traceability drift, knowledge staleness, or an out-of-CLI edit mismatch. Why: the finding is a derived-state mismatch; only the governed command rebuilds it correctly, and editing the file back hides the drift instead of fixing its cause.
2. **Add context upstream and `/reindex`** — use this when the finding is `needs_context` or stale domain context. Why: the gap is missing input, not a broken artifact — proceeding anyway ships an under-grounded handoff.
3. **Record a cited override** — use this when BA/Product deliberately accepts a `/validate` `INVALID` or a warning and wants to proceed. Use `--override PATH` with `DEC-*` decisions. Why: the decision may be legitimate but must be auditable; the override records the rationale without faking a clean verdict.
4. **Treat the non-blocking blocks as a maturity lens, not a gate** — use this when `semantic_quality`, `cross_artifact_consistency`, Mom-Test, or `iso29148_coverage` warn but structure is `VALID`. Why: these advise on content maturity; report the layer and suggested command, don't block handoff on them.

Recommend a rung and say why; the BA decides whether the workspace is ready for the next governed step.
