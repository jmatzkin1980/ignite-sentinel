---
name: sentinel-gap-response
description: "Use when a client or domain owner returns answers to Ignite Sentinel discovery gaps: run /resolve-gaps, apply the governed closure rules (substantive + confirmed closes; vague or pending answers stay open), prefer EARS reformulations for functional gaps, then re-check /maturity and /status. Trigger on 'the client answered', an answered gaps.md, or gap closure questions."
---

# Sentinel Gap Response

Use this skill after a client or domain owner returns an answered `gaps.md` or equivalent Markdown file.

## Workflow

1. Keep the response file under `input/interactions/` or `workspaces/PROJECT_ID/00_raw/05_interactions/` when possible.
2. Run:

```powershell
python -m sentinel /resolve-gaps PROJECT_ID --source PATH
```

3. Review `workspaces/PROJECT_ID/07_changes/00_client_responses/*_gap_resolution_report.md`.
4. Review `workspaces/PROJECT_ID/01_discovery/gap_resolution_log.md`.
5. Run:

```powershell
python -m sentinel /maturity PROJECT_ID
python -m sentinel /status PROJECT_ID
```

## Rules

- Auto-close only applies when a `GAP-ID` block has a non-empty `Answer` or `Respuesta` and `Decision status` is `confirmed`, `not applicable`, `confirmado`, or `no aplica`.
- A non-empty answer with pending or unclear decision status becomes `PARTIALLY_CLOSED`.
- Do not rewrite client answers into confirmed seeds unless the response is structurally confirmed.
- New information that is not mapped to an existing gap should be handled as follow-up input with `/sync` or a new explicit gap.
- Preserve `CHG`, `SEED`, and `DEC` trace links created by the command.
- Gap closure nuances (IMP-010): a substantive answer with `pending` decision becomes `ANSWERED` (awaiting confirmation, still blocking when severe); a vague/deferred answer (`TBD`, `depende`, short non-answers) never closes a gap even if marked `confirmed` — it stays `PARTIALLY_CLOSED` with a `resolution_note` asking for specifics. Only substantive + confirmed/not-applicable closes. Explain these states to the user when summarizing /resolve-gaps.
- EARS guidance (IMP-047): for functional or business-rule gaps (`GAP-ACCEPTANCE`, `GAP-BUSINESS-RULES`, `GAP-PRD-FR-AC`), prefer an answer that includes a confirmed EARS statement (`When/If/While/Where/The system shall...` or Spanish variants). If the client answered in prose, do not rewrite it silently; propose a separate EARS reformulation for BA confirmation. The runtime normalizes only confirmed answers that already pass `classify_ears`; confirmed prose is marked `EARS-eligible, not normalized` and counted in `/status`.
