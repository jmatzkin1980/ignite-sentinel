---
description: Assess whether a brief v2 should be split into a release series, with deterministic signals and their anchors.
argument-hint: PROJECT_ID --assess
---

# Ignite Split

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` and the mode from:

```text
/split PROJECT_ID --assess
```

`--assess` (IMP-263) reads the compiled brief v2 and the release split model (`sentinel/templates/release_split_model.json`). Each of the 7 split signals and 5 no-split signals is `lit` (with the brief lines that anchor it), `off`, `undetermined` (the places it reads are still pending) or `on_proposal` (it judges a proposed release and is checked on the proposal). There is no numeric threshold. The recommendation is `split`, `no_split` or `cannot_decide`, each with its reasons, plus the step 0 questions.

Run from the repository root:

```powershell
python -m sentinel /split PROJECT_ID --assess
```

The runtime writes `01_discovery/split_assessment.md` and `.json` (with the brief sha256) and never touches the brief. A later command that changes the brief re-runs an existing assessment. A v1 brief is rejected: a series does not mix v1 and v2. Report the recommendation with its reasons, the lit signals with their anchors and the undetermined ones.
