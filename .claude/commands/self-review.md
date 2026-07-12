---
description: Run skeptical self-review over generated PRD/specs and register cited gaps plus hard-to-reverse decisions.
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
