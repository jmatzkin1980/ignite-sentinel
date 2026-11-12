---
description: Release series of a brief v2: assess whether to split, validate and store an agent-written series proposal, validate the partition, confirm it and compile the series, and move units later.
agent: sentinel-discovery
---

# Ignite Split

Parse `PROJECT_ID` and the mode from:

```text
/split PROJECT_ID --assess
/split PROJECT_ID --propose --source PROPOSAL.json
/split PROJECT_ID --confirm --ba NAME --tech TEAM
/split PROJECT_ID --move --unit UNIT --from rA --to rB --reason TEXT [--finding ID] [--criterion Cn] --ba NAME --tech TEAM
```

`--assess` (IMP-263) reads the compiled brief v2 and the release split model (`sentinel/templates/release_split_model.json`). Each of the 7 split signals and 5 no-split signals is `lit` (with the brief lines that anchor it), `off`, `undetermined` (the places it reads are still pending) or `on_proposal` (it judges a proposed release and is checked on the proposal). There is no numeric threshold. The recommendation is `split`, `no_split` or `cannot_decide`, each with its reasons, plus the step 0 questions.

`--propose` (IMP-265) takes the proposal JSON written with the `sentinel-release-split` skill: core and variations, cut criteria written before cutting (C1 leads, C14 never alone), the base with its negative list, the releases (type, wave, pattern, goal, units of the brief as `{place, quote}` or `{item: C-NN}`, edges, needs), conditionals with their open gap, spikes (1-3 questions and a time-box), interleaved `r<N>.<M>`, sketches, inheritance of each open gap to the first release that needs it, and the integrator's consumption table. Every anchor must be verbatim in its place. A refused proposal lists every finding with its code and stores nothing; a valid one is stored in `02_requirements/series/proposal.json` as a proposal. Nothing is compiled.

`--confirm` (IMP-266) validates the partition of the stored proposal deterministically: shared contracts as graph nodes (each hard edge names its why and the contract it consumes), symmetric `depends_on`/`enables` pairs, cycles (a cycle is a missing contract), waves (a hard dependency points to an earlier wave), coverage n of n of the §6.1 scope lines, the `C-NN` of §9 and the screens `P-N` (exactly one release or sketch each), a single owner per contract with a cross note and merge order when two or more siblings extend it, contracts frozen by hash (a later change needs an audited delta), relaxed rules (never legal, regulatory or Must, always `restored_in`), the validated anti-patterns, pending with tentacles (a conditional's gap repeated in siblings is a defect; a gap holding back 75 % or more of the releases is a transversal readiness signal) and the integrator's premise against its consumption table. Only when it is green it writes `02_requirements/series/partition.json` with who confirmed (the BA and the technical team); the client's confirmation opens `GAP-SPLIT-CLIENT`. Nothing is compiled.

The confirmation compiles the series (IMP-267a): `02_requirements/series/index.md` (the project in one page, the series table, waves, frozen contracts, the id map, sketches and sync findings) and one self-contained `02_requirements/r<N>/project-brief.md` per release. Each release brief is the whole brief where every unit another release owns becomes a tombstone ("➡ lives in rN"), a moved unit says REATRIBUIDO, build items `C-NN` get local ids mapped in the index, and §0.1 declares the release in the series. The SAD and the prototype are not split. Integrity and anchors run on each release. A later command that changes the brief recompiles the series; a v1 brief blocks it.

`--move` (IMP-268) moves one unit (`C-NN`, `P-N` or a quote of the brief) of a confirmed series from one release to another, or to a sketch (`--to sketch:<name>`). The partition validation must stay green and the BA and the technical team confirm it again; the series recompiles (REATRIBUIDO tombstones) and the touched releases with derivations come back as `stale_derivations`. Every move is dated with its reason and finding in `02_requirements/series/scope_changes.md`. Moving to a sketch closes no gap. A round trip (A→B→A) is refused and opens `GAP-SPLIT-CRITERION` until `--criterion Cn` names the written criterion that decides it.

Run from the repository root:

```powershell
python -m sentinel /split PROJECT_ID --assess
python -m sentinel /split PROJECT_ID --propose --source PROPOSAL.json
python -m sentinel /split PROJECT_ID --confirm --ba NAME --tech TEAM
python -m sentinel /split PROJECT_ID --move --unit UNIT --from rA --to rB --reason TEXT --ba NAME --tech TEAM
```

The runtime writes `01_discovery/split_assessment.md` and `.json` (with the brief sha256) and never touches the brief. A later command that changes the brief re-runs an existing assessment. A v1 brief is rejected: a series does not mix v1 and v2. Report the recommendation with its reasons, the lit signals with their anchors and the undetermined ones.
