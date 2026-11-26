---
description: Merge validated agent-authored backlog refinement proposals with verbatim local citations.
agent: sentinel-backlog
---

# Ignite Refine Backlog

Parse `PROJECT_ID` and `--source PATH` from:

```text
/refine-backlog PROJECT_ID --source PATH
/refine-backlog PROJECT_ID --source PATH --change CHG-NNN
```

The `--source` file is JSON with `proposals[]`. Each proposal declares a kind (`reslice`, `split-story`, `merge-stories`, `missing-story`, or `enabler-candidate`), target stories or source units as applicable, a recommendation, rationale, and verbatim `citations[]` from local source-of-truth evidence. Optional `discarded_alternative` may capture `{ "option": "...", "reason": "..." }` when the proposal considered and rejected another option. `enabler-candidate` proposals must also declare enabled stories, supported boundary, concrete `enabled_capability`, measurable `verification_method`, risk reduced, and objective evidence.

Run from the repository root:

```powershell
python -m sentinel /refine-backlog PROJECT_ID --source PATH
python -m sentinel /refine-backlog PROJECT_ID --source PATH --change CHG-NNN
```

The runtime validates story/unit existence, rejects pending units, checks every citation verbatim, archives the source under `04_backlog/refinements/`, merges valid proposals with `origin: agent`, renders a governed refinement section in the backlog, and reports rejected proposals with reasons. Summarize accepted/rejected proposal IDs and the refinement report path.

`--change CHG-NNN` (IMP-433) refines the stories of that change, with no `EPIC-001` needed: `target_stories` are stories of the change, `source_units` are units the change owns (those of the change and of its releases), and citations are verbatim lines of the change's own text (request, brief, specs, stories, context packs). The source is archived and reported under `04_backlog/CHG-NNN/refinements/`, the proposals are rendered in the epic of the change, and its quality audit goes stale (`/quality PROJECT_ID --change CHG-NNN` again). A story or unit of the project or of another change is refused, and so is a backlog of the change that is missing or behind its units (next `/backlog PROJECT_ID --change CHG-NNN`). `/refine-backlog PROJECT_ID` without `--change` leaves the stories of a change alone; in a workspace that only has changes it refuses (no `EPIC-001`, health not clean). `--release` is not accepted.
