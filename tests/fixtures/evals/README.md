# Discovery Eval Fixtures (IMP-016, IMP-027, IMP-038)

Synthetic client requirements with deliberate, cataloged omissions. All content is invented; no real client data. They serve as the answer-key benchmark for discovery gap detection, project-brief coverage, PRD coverage, specs scaffolding, backlog derivation, and retrieval.

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
  - `golden_queries` (IMP-032, hardened IMP-120): retrieval answer key. Each query declares `query`, `workflow`, `expected_section` (the specific artifact **section** that must be retrieved, matched against the chunk `section_path` — e.g. `GAP-METRIC-SOURCE`), optional `expected_artifacts`, `kind` (`same-language` or `cross-lingual`), and `rationale`. Section-level targets (not whole documents) plus the shared distractor corpus keep recall from saturating at 1.0.
  - `backlog` (IMP-061): backlog answer key with expected story count, expected `US-*` IDs, expected `SPEC-U-*` source units, no-invention checks, expected slicing pattern by source unit, and optional future checks for story-specific anchors/context.

The runner executes `init -> ingest -> resolve-gaps (when gap_responses.md or gap_response_rounds/*.md exist) -> brief -> specs -> backlog` per fixture. It classifies brief sections 1-6 and PRD sections 1-13 as `populated` or `pending`, counts fixed scaffolding IDs in `specs.md` (`JTBD-001`, `CAP-001..003`, `US-001..005`, `ASM-001/002`), and checks backlog behavior against the `backlog` answer key. Backlog metrics include derivation coverage, no-invention rate, slicing-pattern accuracy, anchor validity, and story-context distinctness. The anchor/context checks are opt-in so IMP-057/058 can turn them into hard gates when those runtime capabilities exist. IMP-038 intentionally recorded a low PRD baseline and high specs scaffolding baseline so IMP-039/042 could move them with falsifiable evidence; IMP-048 added story derivation, and IMP-061 makes backlog falsability explicit across fixtures.

IMP-110 extends the discovery report from baseline smoke to benchmark signals. Each fixture now includes `gap_benchmark` with precision, recall, F1, required-gap recall, semantic target recall, false-positive counts, and recall by lens over the answer-key-labeled universe (`must_fire + target_fire` positives, `must_not_fire` negatives). The existing pass/fail behavior is unchanged: known false positives remain visible in metrics but do not fail the baseline unless they are new. Set `SENTINEL_EVAL_REPEAT=N` before running `python tests/evals/run_discovery_evals.py` to repeat deterministic fixture runs and record precision/recall/F1 variance in the JSON report; the default is one run.

`tests/test_evals_retrieval.py` runs `init -> ingest` per fixture, seeds the shared multi-domain distractor corpus (`tests/fixtures/evals/_distractors/<domain>/`) into the workspace context folders, reindexes, then scores the section-level golden queries with recall@5 and MRR over the active backend and embedder. It writes `tests/evals/reports/retrieval_eval_<date>.json` with per-fixture metadata plus `summary.by_backend` **and** `summary.by_embedder` so `json-hybrid`/`lancedb-hybrid` and hash/semantic runs can be compared without making LanceDB or a local model mandatory. Hardened by IMP-120 to be falsifiable and discriminant: golden queries target a specific section (not a whole document), the distractor corpus competes for the same slots (`distractor_in_top5_rate`, `discrimination_rate`), so hash-mode same-language recall falls from the old universal 1.0 to a recalibrated, non-saturated baseline, cross-lingual recall sits at ~0 in hash (the falsifiable gate IMP-121's semantic embedder must lift), and the test stays green as a non-regression floor. The `_distractors/` folder has no `answer_key.json`, so it is skipped as a fixture and only used as retrieval noise.

The keyword ceiling, made explicit by `expense-approval`: a single token present in the text suppresses a whole gap even when the substance is missing (`success` suppresses GAP-ACCEPTANCE, `compliance`/`security` suppress governance/NFR, `rule` suppresses business rules, `quality` suppresses quality). Such reassuring-but-empty requirements drive `target_recall` to 0.00 until the agentic semantic pass (`/annotate`) contributes validated gaps.

When adding a fixture: write the requirement with explicit coverage of some areas and deliberate omission of others, run the eval harness, inspect what fires, which brief/PRD sections populate, which specs scaffolding remains, whether backlog emits Spec Unit stories or a pending stub, which slicing pattern is assigned, and which retrieval queries hit, then record the key empirically. Keep one fixture per domain pattern and at least one non-English fixture.
