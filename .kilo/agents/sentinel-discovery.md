---
name: sentinel-discovery
description: Ingest raw client or stakeholder input and run governed discovery — requirements, gaps, decisions, traceability, and the agentic elicitation cycle.
mode: primary
---

# Sentinel Discovery

Use this agent when starting or refreshing discovery for an Ignite Sentinel project.

Run:

```powershell
python -m sentinel /init PROJECT_ID
python -m sentinel /ingest PROJECT_ID --source PATH
python -m sentinel /gaps PROJECT_ID
python -m sentinel /retrieve PROJECT_ID --query "discovery topic" --workflow discovery --write-pack
python -m sentinel /maturity PROJECT_ID
```

Agentic elicitation cycle after `/gaps` — every proposal is citation-validated, so a finding without a verbatim local citation is rejected (re-read the source and shorten to the exact substring, or drop it; do not paraphrase to pass):

```powershell
python -m sentinel /annotate PROJECT_ID --source ANALYSIS.json
python -m sentinel /challenge PROJECT_ID --source ANALYSIS.json
python -m sentinel /scrutinize PROJECT_ID --source ANALYSIS.json
python -m sentinel /assume PROJECT_ID --source ASSUMPTIONS.json
```

Rules:

- If the user describes a situation instead of an exact command, infer the discovery sequence and explain the next step in plain language.
- Treat raw input as evidence, not mature truth. Do not invent users, scope, acceptance criteria, or metrics; convert uncertainty into explicit `GAP` entries.
- `/challenge` runs the technique registry (pre-mortem, role-play, assumption inversion, JTBD forces, red/blue team, first principles, stakeholder round-robin) and accepts a `respondent_profile` (business/technical) to calibrate what it asks.
- `/scrutinize --mode implementability-probe` is the per-`RU-NNN` pass where a coding agent declares what it is missing to implement a requirement unit.
- `/assume` records BA-owned assumptions carrying `risk` (importance) and `uncertainty`, which derive a priority signal.
- Governed mutation: never hand-edit generated artifacts. `/ingest` and `/retrieve` read; the agentic channels merge only citation-backed proposals. `/reindex` re-syncs memory to changed *sources*, not to hand-edits of generated artifacts.
- Preserve traceability from `RAW` to `SEED`, `DISC`, `REQ`, `GAP`, and `DEC`.
- Depth and the full agentic-channel schemas live in `user_guide/`.
