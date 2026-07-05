---
name: sentinel-privacy-local-first
description: "Use whenever Ignite Sentinel project data, client documents, code, memory, retrieval, or exports are involved and the local-only privacy rules must hold: no remote MCP, external vector databases, or external embedding services for client content; export only through audited commands. Trigger on sharing, sending, uploading, or exporting anything derived from a workspace."
---

# Sentinel Privacy Local First

Use this skill whenever project data, client documents, code, memory, or exports are involved.

## Rules

- Source of truth stays in versionable files under `workspaces/PROJECT_ID/`.
- Retrieval memory is local under `workspaces/PROJECT_ID/memory.lancedb/`.
- Do not use remote MCP, remote vector databases, external embedding APIs, or unapproved external services for client/project content.
- LanceDB is local retrieval only; source files win if memory disagrees.
- Use deterministic local hash embeddings as fallback.
- Export only through audited commands such as:

```powershell
python -m sentinel /export PROJECT_ID --artifact gaps --format md
python -m sentinel /export PROJECT_ID --artifact brief --format md
```

- Do not store sensitive client input outside `workspaces/PROJECT_ID/` or repo `input/`.
