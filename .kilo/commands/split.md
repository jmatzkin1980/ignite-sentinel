---
description: Release series of a brief v2: assess whether to split, then validate and store an agent-written series proposal.
agent: sentinel-discovery
---

# Ignite Split

Parse `PROJECT_ID` and the mode from:

```text
/split PROJECT_ID --assess
/split PROJECT_ID --propose --source PROPOSAL.json
```

`--assess` (IMP-263) reads the compiled brief v2 and the release split model (`sentinel/templates/release_split_model.json`). Each of the 7 split signals and 5 no-split signals is `lit` (with the brief lines that anchor it), `off`, `undetermined` (the places it reads are still pending) or `on_proposal` (it judges a proposed release and is checked on the proposal). There is no numeric threshold. The recommendation is `split`, `no_split` or `cannot_decide`, each with its reasons, plus the step 0 questions.

`--propose` (IMP-265) takes the proposal JSON written with the `sentinel-release-split` skill: core and variations, cut criteria written before cutting (C1 leads, C14 never alone), the base with its negative list, the releases (type, wave, pattern, goal, units of the brief as `{place, quote}` or `{item: C-NN}`, edges, needs), conditionals with their open gap, spikes (1-3 questions and a time-box), interleaved `r<N>.<M>`, sketches, inheritance of each open gap to the first release that needs it, and the integrator's consumption table. Every anchor must be verbatim in its place. A refused proposal lists every finding with its code and stores nothing; a valid one is stored in `02_requirements/series/proposal.json` as a proposal. Nothing is compiled.

Run from the repository root:

```powershell
python -m sentinel /split PROJECT_ID --assess
python -m sentinel /split PROJECT_ID --propose --source PROPOSAL.json
```

The runtime writes `01_discovery/split_assessment.md` and `.json` (with the brief sha256) and never touches the brief. A later command that changes the brief re-runs an existing assessment. A v1 brief is rejected: a series does not mix v1 and v2. Report the recommendation with its reasons, the lit signals with their anchors and the undetermined ones.
