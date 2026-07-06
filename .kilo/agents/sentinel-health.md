---
name: sentinel-health
description: Audit workspace health before or after downstream work — traceability, blocking gaps, unbacked metrics, memory indexing, staleness, and structural validity.
mode: primary
---

# Sentinel Health

Run:

```powershell
python -m sentinel /health PROJECT_ID
python -m sentinel /validate PROJECT_ID
python -m sentinel /trace PROJECT_ID
```

Rules:

- Use `/health` + `/validate` before handoff. Source workspace files are authoritative; memory indexes never override versionable artifacts.
- `/health` catches blocking gaps, unbacked metrics, orphan trace nodes, missing memory indexing, knowledge staleness, and story/epic linkage issues.
- A checksum mismatch (IMP-147) means an artifact was changed outside the CLI: recommend regenerating it through its owning command rather than re-saving it by hand.
- On a soft `needs_context` gate, recommend `/retrieve --write-pack` (a focus pack) before deep analysis instead of reading `00_raw/` whole.
- If domain context changed after backlog generation, treat the backlog as stale and run `/reindex PROJECT_ID` + `/backlog PROJECT_ID` before implementation handoff.
- `/validate` confirms required semantic artifacts exist (specs context packs, backlog readiness audit, story execution contracts, retrieval plans, implementation readiness pack). Depth lives in `user_guide/`.
