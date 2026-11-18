---
name: sentinel-health
description: "Use when auditing an Ignite Sentinel workspace before or after downstream work: /health findings (traceability, blocking gaps, unbacked metrics, memory indexing, staleness), /validate structural verdict plus non-blocking semantic-quality and cross-artifact consistency warnings, and gate overrides with cited DEC-* decisions. Trigger on 'is the workspace healthy', a DIRTY verdict, validation warnings, or the final pre-handoff check. Not for deciding whether the requirement is mature enough for specs or backlog (use sentinel-maturity)."
---

# Sentinel Health

Use this skill as the final gate for any Sentinel workflow.

## Workflow

1. Run `sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py" /health PROJECT_ID`.
2. Review `workspaces/PROJECT_ID/06_traceability/health_report.md`.
3. If verdict is `DIRTY`, fix each finding **by running the governed command that owns the artifact** and rerun health. Health findings are never fixed by editing artifacts.
4. Use `sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py" /trace PROJECT_ID` when findings mention traceability.

## Rules

- Health is based on versionable artifacts and deterministic checks.
- LanceDB or fallback memory cannot override source files.
- Metrics without explicit source or baseline are findings. A metric in a raw source (`00_raw/`) stops counting once every `GAP-METRIC-SOURCE*` gap is `CLOSED`: the raw file never changes, so the closed gap is what settles it.
- **Out-of-CLI edit detection (IMP-147, IMP-332):** a mutating command snapshots the sha256 only of the governed artifacts it wrote into `state.json#artifact_hashes`; `/health` recomputes and compares. A mismatch means someone hand-edited a governed artifact, and it keeps warning until the file is regenerated on purpose — an unrelated command does not clear it. Before a mutating command runs, each hand-edited file is copied to `.sentinel/hand_edits/<timestamp>-<command>/`. If the command overwrote the edit, a `sentinel warning:` on stderr names the copy, and `/health` warns about the kept copy until it is deleted; recover the text from there. Recommend regenerating through the owning Sentinel command; never "fix" the mismatch by editing the file back or touching `state.json`.
- **`DIRTY` is recomputed, not cleared (IMP-332):** when a command would leave health `CLEAN` while the last health report says `DIRTY`, the runtime re-runs `/health` and the current findings win. Running `/maturity` or `/specs` never makes a `DIRTY` workspace clean; only fixing the cause does.
- **Knowledge staleness:** after a change moves knowledge units, `state.json#knowledge_staleness` lists the downstream artifacts now stale. The finding clears only when those artifacts are regenerated via their commands (`/health` compares each artifact's mtime against the marker's `recorded_at`); unrelated passes do not clear it.
- **Semantic change review (IMP-369):** a `/sync` whose note reads like a change of meaning ("now", "instead", "out of scope"...) flags its trace links: "Semantic change may invalidate downstream trace links for CHG-NNN". Two governed exits: regenerate what it feeds (`/brief`, `/specs`, `/backlog`, in that order), or, when the BA has read the targets and nothing downstream changes, record the review with `/trace PROJECT_ID --reviewed CHG-NNN --reason "..."`. A later neutral `/sync` does not clear it.
- **One classification for the next step (IMP-369):** the `/backlog` refusal and `/next` list each finding with its fix, in order (`/reindex`, a GAP-CHG decision or `/resolve-gaps`, implementation feedback, `/story-status ... --set Draft` for Stale stories, then the regeneration chain ending in `/backlog`). Relay that list as given.
- **`needs_context` gate:** when workspace memory has too little indexed context for reliable downstream retrieval, `/health` raises it — as a warning by default, as a blocking finding in strict mode. The remediation is upstream: add/ingest domain context and `/reindex`, not proceed anyway.
- Domain context freshness: if domain context files changed after specs/backlog generation, health flags the stale derivation — regenerate via `/reindex` + the owning command before handoff.
- `/validate` also emits a non-blocking `semantic_quality` block (IMP-006): per-artifact score and classification (`evidence-backed` / `mixed` / `scaffolding`) for brief, PRD, and specs, plus `warnings`. Use it to decide whether downstream handoff content is mature, separate from structural validity.
- `/validate` also emits non-blocking `cross_artifact_consistency` warnings (IMP-045/IMP-134): brief->PRD continuity, confirmed `REQ-EARS-*` coverage in specs/spec units, FR extraction coverage, resolvable spec-unit source pointers, orphan EARS references, lost `SPEC-U-*` statements between specs and backlog acceptance criteria, and (IMP-344, `build_items_to_stories`) each brief v2 build item `C-NN` that no story covers; for that one, tell the BA that only confirmed answers written in EARS become stories. Report the layer, artifact, and suggested corrective command without treating the warning as a failed structural verdict.
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
