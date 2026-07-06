---
name: sentinel-sync
description: Ingest stakeholder feedback, meeting notes, or client changes and turn them into governed, traceable impact analysis.
mode: primary
---

# Sentinel Sync

Run:

```powershell
python -m sentinel /sync PROJECT_ID
python -m sentinel /sync PROJECT_ID --source PATH --note "source and intent"
python -m sentinel /retrieve PROJECT_ID --query "change topic" --workflow sync --write-pack
python -m sentinel /reindex PROJECT_ID
python -m sentinel /health PROJECT_ID
```

Rules:

- Treat new information as a `CHG` event. Prefer `/sync PROJECT_ID` for autonomous detection of new or modified inputs (matched by content hash).
- Review the impact report before considering the workspace healthy.
- Governed mutation only: `/sync` reports impact and recommends which owning command to re-run (`/specs`, `/backlog`, ...); regenerate through those commands. Never hand-edit downstream artifacts — changes made outside the CLI are flagged by `/health` (IMP-147 checksum mismatch) and never propagate.
- A change can invalidate assumptions: `/sync` moves the affected `ASM-*` through the ledger (INVALIDATED + supersession) and raises `origin: sync` gaps; regeneration then marks impacted stories `Stale` (knowledge staleness).
- `/reindex` only re-syncs memory to changed *sources*; it does not legitimize hand-edits of generated artifacts.
- Depth on change management and governed regeneration lives in `user_guide/`.
