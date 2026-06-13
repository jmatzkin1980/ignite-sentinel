# Discovery Eval Fixtures (IMP-016, IMP-027, IMP-038)

Synthetic client requirements with deliberate, cataloged omissions. All content is invented; no real client data. They serve as the answer-key benchmark for discovery gap detection, project-brief coverage, PRD coverage, specs scaffolding, and retrieval.

Each fixture folder contains:

- `requirement.md`: synthetic raw client requirement.
- `gap_responses.md` (optional, IMP-038): synthetic confirmed answers used only to close blocking gaps so the eval can reach `/specs` through the real lifecycle. Do not use these to hide discovery omissions; they are phase-2 enablement data.
- `gap_response_rounds/*.md` (optional, IMP-048): multiple synthetic response rounds applied in sorted order when one fixture needs several confirmed EARS rows and therefore several `SPEC-U-*` units.
- `answer_key.json`: expected detection behavior:
  - `must_fire`: gaps the current engine must detect.
  - `must_not_fire`: information explicitly covered in the text; firing one is a false positive.
  - `known_false_positives`: documented current engine bugs. When fixed, move them out and update the key.
  - `target_fire`: gaps an inquisitive/semantic engine should detect but keyword suppression can miss. `target_recall` is a progress metric.
  - `expected_language`: project language expected after `/ingest`.
  - `expected_gap_details`: selected stable gap metadata (`lens`, `severity`, `origin`).
  - `annotate.expected_gap_details`: metadata expectations only when the fixture runs through `/annotate`.
  - `brief` (IMP-027): brief coverage answer key.
    - `target_populated`: narrative brief sections 1-6 that have confirmed evidence and must populate with citations.
    - `target_pending`: narrative brief sections 1-6 that must stay explicitly pending because evidence is missing.
    - `rationale`: why those sections are expected.
  - `prd` (IMP-038): PRD coverage answer key.
    - `target_populated`: numbered PRD sections that have enough confirmed evidence and should eventually be compiled from evidence by IMP-039.
    - `rationale`: why those PRD sections are expected to become evidence-backed.
  - `golden_queries` (IMP-032): retrieval answer key with query, workflow, expected artifacts, kind, and rationale.
  - `backlog` (IMP-048): backlog derivation answer key with expected story count, expected `SPEC-U-*` source units, and whether every generated story must trace to a Spec Unit.

The runner executes `init -> ingest -> resolve-gaps (when gap_responses.md or gap_response_rounds/*.md exist) -> brief -> specs -> backlog` per fixture. It classifies brief sections 1-6 and PRD sections 1-13 as `populated` or `pending`, counts fixed scaffolding IDs in `specs.md` (`JTBD-001`, `CAP-001..003`, `US-001..005`, `ASM-001/002`), and checks backlog derivation against `SPEC-U-*` answer keys. IMP-038 intentionally recorded a low PRD baseline and high specs scaffolding baseline so IMP-039/042 could move them with falsifiable evidence; IMP-048 adds story derivation coverage.

`tests/test_evals_retrieval.py` runs `init -> ingest` per fixture, scores golden queries with recall@5 and MRR, and writes `tests/evals/reports/retrieval_eval_<date>.json`. The report includes per-fixture backend metadata plus `summary.by_backend` so `json-hybrid` and `lancedb-hybrid` runs can be compared without making LanceDB mandatory.

The keyword ceiling, made explicit by `expense-approval`: a single token present in the text suppresses a whole gap even when the substance is missing (`success` suppresses GAP-ACCEPTANCE, `compliance`/`security` suppress governance/NFR, `rule` suppresses business rules, `quality` suppresses quality). Such reassuring-but-empty requirements drive `target_recall` to 0.00 until the agentic semantic pass (`/annotate`) contributes validated gaps.

When adding a fixture: write the requirement with explicit coverage of some areas and deliberate omission of others, run the eval harness, inspect what fires, which brief/PRD sections populate, which specs scaffolding remains, and which retrieval queries hit, then record the key empirically. Keep one fixture per domain pattern and at least one non-English fixture.
