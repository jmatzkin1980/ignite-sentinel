# Discovery Eval Fixtures (IMP-016)

Synthetic client requirements with deliberate, cataloged omissions. All content is invented; no real client data. They serve as the answer-key benchmark for discovery gap-detection quality (run by `tests/evals/run_discovery_evals.py`, IMP-020).

Each fixture folder contains:

- `requirement.md` — the synthetic raw client requirement.
- `answer_key.json` — the expected detection behavior:
  - `must_fire`: gaps the current engine must detect (regression guard).
  - `must_not_fire`: information explicitly covered in the text; firing one is a false positive.
  - `known_false_positives`: documented current engine bugs (fire today, should not). When fixed, move them out and update the key.
  - `target_fire`: gaps an inquisitive engine (IMP-015) should detect but the current keyword-suppression logic misses. `target_recall` is the IMP-015 progress metric: 0.00 at baseline, should grow.

When adding a fixture: write the requirement with explicit coverage of some areas and deliberate omission of others, run the eval harness, inspect what fires, and record the key empirically. Keep one fixture per domain pattern (dashboard, integration, portal, ...) and at least one non-English fixture.
