---
description: Validate Ignite workspace structure, graph integrity, semantic quality, and cross-artifact consistency.
agent: sentinel-health
---

# Ignite Validate

Parse `PROJECT_ID` and optional `--override PATH` from:

```text
/validate PROJECT_ID
/validate PROJECT_ID --override PATH
```

Run:

```powershell
python -m sentinel /validate PROJECT_ID
python -m sentinel /validate PROJECT_ID --override PATH
```

Report whether the workspace is structurally valid. Also summarize non-blocking `semantic_quality` and `cross_artifact_consistency` warnings, naming the affected layer, artifact, and suggested corrective command when present. `cross_artifact_consistency` now also checks handoff fidelity from confirmed `SPEC-U-*` statements into backlog acceptance criteria, so call out any `spec_unit->story` warning explicitly. It also reports ISO/IEC/IEEE 29148 requirement-quality coverage under `iso29148_coverage`: each of the nine individual-requirement characteristics is marked `covered` (with the checks that cover it), an open `heuristic_gap`, or `out_of_scope` with a reason (characteristics like Complete, Feasible, and Correct that no local deterministic heuristic can decide are declared out of scope, never simulated), plus any `verifiability_findings` for requirement statements that carry no measurable acceptance anchor. If a human intentionally proceeds despite the validate result, `--override PATH` accepts cited `decisions[]` in `DEC-*` shape and records an exportable rationale under `06_traceability/gate_overrides/` without changing the underlying `VALID` / `INVALID` verdict or exit code.
