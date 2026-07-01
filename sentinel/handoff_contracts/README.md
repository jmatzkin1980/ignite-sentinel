# Handoff contracts

This registry is intentionally small. The spike behind `IMP-141` found that most
downstream handoff edges already have executable coverage:

- `brief->prd`, `requirements->specs`, `prd->specs`, spec pointers, and expected
  evidence are checked in `sentinel.validation`.
- `spec_unit->story` is covered by `spec_unit_story_handoff`.
- `backlog->implementation` already emits `08_context_packs/implementation_readiness.json`.

The marginal gap is the upstream `discovery->brief` edge: a brief can exist while
omitting declared discovery facts that later specs assume are present. The
`discovery_to_brief_minimum` contract declares only those minimum fields. Edges
with existing executable checks should reference the check instead of declaring
duplicate fields.
