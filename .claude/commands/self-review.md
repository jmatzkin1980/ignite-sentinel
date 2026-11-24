---
description: Run skeptical self-review over generated PRD/specs and register cited gaps plus hard-to-reverse decisions.
argument-hint: PROJECT_ID --source PATH [--sufficiency|--crosses] | PROJECT_ID --crosses --change CHG-NNN (--source PATH | --skip --reason TEXT)
---

# Ignite Self Review

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` and `--source PATH` from:

```text
/self-review PROJECT_ID --source PATH
```

The `--source` file is JSON with optional `gaps[]` and `decisions[]`. Gaps follow the governed cited shape (`id`, `lens`, `severity`, `question`, and verbatim `evidence`) and are validated against generated PRD/spec artifacts, then merged as `origin: self-review`. Decisions declare `id` (`DEC-*`), `title`, `lens`, `risk`, `reversibility`, `decision`, and verbatim `evidence`. ADR-grade optional fields (backwards-compatible, no migration): `consequences[]` (trade-offs; a decision with no trade-off is an anti-pattern), `considered_options[]` (each `{option, evidence}` cited verbatim), and `supersedes` (a prior `DEC-*` this one immutably replaces — the superseded entry stays intact).

Run from the repository root:

```powershell
python -m sentinel /self-review PROJECT_ID --source PATH
```

The runtime archives the source under `03_specs/self_review/`, writes `self_review_report.md` and `decision_register.md`, records traceability, and does not rewrite PRD/specs automatically. Summarize merged gaps, skipped duplicates, registered decisions, and generated paths.

`--sufficiency` (IMP-259) runs on a brief v2 alone: a clean-context reader classifies each place and §9 item as covered, missing, ambiguous or contradictory, with verbatim quotes and one question each (see the `sentinel-self-review` skill). Accepted obstacles open `GAP-SUF-*` gaps; repeat rounds until only covered remains.

`--crosses` (IMP-260b) reports semantic crosses of a brief v2 against `templates/semantic_crosses.json` (lens crosses A-D and the judgment exit checks): `conflict` quotes both places, `missing` quotes one and names where the counterpart should be. Accepted crosses open `GAP-XRV-*` gaps.

`--crosses --change CHG-NNN` (IMP-410) reads the lens view of a change (`01_discovery/CHG-NNN/coherence/view.md`: its request, border and decided surfaces placed at the places of a brief v2) against the same rules; it is available once the change's cross-reads are done. Without `--source` or `--skip` it only refreshes the view and reports the deterministic checks. With `--source PATH` it records the semantic crosses the BA confirmed (`{"crosses": [...]}`, as above; an empty list means the view was read and nothing was found): every quote is checked word for word and a rejected cross rejects the whole file. With `--skip --reason TEXT` it waives the reading. Questions opened by a cross (`GAP-XRV-*`) are checked against what the change already decided before they reach the BA. Transcribe, never draft.
