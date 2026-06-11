# Discovery Eval Fixtures (IMP-016, IMP-027)

Synthetic client requirements with deliberate, cataloged omissions. All content is invented; no real client data. They serve as the answer-key benchmark for discovery gap-detection and project-brief coverage (run by `tests/evals/run_discovery_evals.py`, IMP-020/IMP-027).

Each fixture folder contains:

- `requirement.md` — the synthetic raw client requirement.
- `answer_key.json` — the expected detection behavior:
  - `must_fire`: gaps the current engine must detect (regression guard).
  - `must_not_fire`: information explicitly covered in the text; firing one is a false positive.
  - `known_false_positives`: documented current engine bugs (fire today, should not). When fixed, move them out and update the key.
  - `target_fire`: gaps an inquisitive/semantic engine should detect but the current keyword-suppression logic misses. `target_recall` is the progress metric (IMP-015, then IMP-021): 0.00 at baseline, should grow.
  - `brief` (IMP-027): brief-coverage answer key.
    - `target_populated`: narrative brief sections (1-6) that have confirmed evidence in the requirement and the IMP-024 brief compiler must populate with citations. `brief_target_coverage` is the progress metric: 0.00 at baseline (the template renderer leaves them as TBD), should reach 1.00 once compiled.
    - `rationale`: why those sections are expected and which stay `[PENDING INPUT]`.

The runner runs `init → ingest → brief` per fixture and classifies each section 1-6 as `populated` (no template marker) or `pending`.

The keyword ceiling, made explicit by `expense-approval`: a single token present in the text suppresses a whole gap even when the substance is missing (`success` suppresses GAP-ACCEPTANCE, `compliance`/`security` suppress governance/NFR, `rule` suppresses business rules, `quality` suppresses quality). Such reassuring-but-empty requirements drive `target_recall` to 0.00 — the gap an agentic semantic pass (IMP-021 `/annotate`) must close.

When adding a fixture: write the requirement with explicit coverage of some areas and deliberate omission of others, run the eval harness, inspect what fires and which brief sections populate, and record the key empirically. Keep one fixture per domain pattern (dashboard, integration, portal, approval-workflow, ...) and at least one non-English fixture.
