---
name: sentinel-privacy-local-first
description: "Use when you want the full Ignite Sentinel local-first privacy rule set or an export checklist (a deliberate, human-invoked reference): source of truth in versionable workspace files, no remote MCP / external vector databases / external embedding services for client content, and export only through audited commands. Not needed for routine work: the non-negotiable rules are always on in AGENTS.md and CLAUDE.md."
disable-model-invocation: true
---

# Sentinel Privacy Local First

Invoke this skill deliberately whenever project data, client documents, code, memory, or exports are involved.

## Invocation

This skill is **human-only** (`disable-model-invocation: true`): the model does not auto-load it. That is intentional — the privacy non-negotiables are always-on in `AGENTS.md` and `CLAUDE.md`, so enforcement never depends on a skill firing. This deeper reference is invoked deliberately (by a human, or on explicit request) when the full rule set or an export checklist is needed. See `user_guide/references/skill-authoring-checklist.md` for the human-only convention.

## Rules

- Source of truth stays in versionable files under `workspaces/PROJECT_ID/`.
- Retrieval memory is local under `workspaces/PROJECT_ID/memory.lancedb/`.
- Do not use remote MCP, remote vector databases, external embedding APIs, or unapproved external services for client/project content.
- LanceDB is local retrieval only; source files win if memory disagrees.
- Use deterministic local hash embeddings as fallback.
- Export only through audited commands such as:

```powershell
sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py" /export PROJECT_ID --artifact gaps --format md
sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py" /export PROJECT_ID --artifact brief --format md
```

- Do not store sensitive client input outside `workspaces/PROJECT_ID/` or repo `input/`.
