---
name: sentinel-domain-request
description: "Use when Technology, Design, Quality, Frontend, or Backend must deepen analysis from an Ignite Sentinel project brief: /context-request per domain generates a cited request pack under 08_context_packs/requests. Trigger on 'ask Technology for context', domain deep-dive needs, or missing domain evidence blocking a story or spec."
---

# Sentinel Domain Request

Use this skill to generate a domain-specific request after discovery has enough signal.

## Workflow

```powershell
python -m sentinel /context-request PROJECT_ID --domain technology
python -m sentinel /context-request PROJECT_ID --domain design
python -m sentinel /context-request PROJECT_ID --domain quality
python -m sentinel /context-request PROJECT_ID --domain frontend
python -m sentinel /context-request PROJECT_ID --domain backend
```

Outputs live in:

```text
workspaces/PROJECT_ID/08_context_packs/requests/
```

## Domain Focus

- Technology: repos/components, endpoints/events, architecture, source of truth, risks, NFRs.
- Design: journeys, screens, prototype scope, states, copy, accessibility, visual references.
- Frontend: affected surfaces, components, UI states, API bindings, validations, analytics.
- Backend: capabilities, integrations, persistence, contracts, security, observability, failure behavior.
- Quality: critical flows, edge cases, regression risk, test data, automation strategy, evidence.

## Rules

- Context requests ask domains to deepen analysis; they do not fabricate that analysis.
- Cite `project-brief.md`, `gaps.md`, and trace IDs.
- Keep all generated requests inside the project workspace.
