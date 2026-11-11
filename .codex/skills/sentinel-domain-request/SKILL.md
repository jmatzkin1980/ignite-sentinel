---
name: sentinel-domain-request
description: "Use when Technology, Design, Quality, Frontend, or Backend must deepen analysis from an Ignite Sentinel project brief: /context-request per domain generates a cited request pack under 08_context_packs/requests. Trigger on 'ask Technology for context', domain deep-dive needs, or missing domain evidence blocking a story or spec. Not for questions the client must answer (those are gaps, use sentinel-gap-response)."
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

## Packs Are Deliverables (IMP-272)

- The generated request carries `when_to_read:` frontmatter. Ask the domain team to do the same in every file they deliver, and to give each fact **one** owner (`Owner: <one person or role>`).
- `/validate` warns about delivered files without `when_to_read:` or with a shared owner. Relay those warnings to the owner; do not fix their files by hand.
- An `/export` that still has pending marks is a **draft**, and says so. Use `--final` only when nothing is pending, and never present a draft as final.

