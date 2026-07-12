---
description: Register or list project stakeholders and route elicitation gaps by owner.
---

# Ignite Stakeholders

Arguments received from the user invocation: `$ARGUMENTS`

Register or list the governed stakeholder registry. Parse `PROJECT_ID`; to add an owner pass `--add` with fields:

```text
/stakeholders PROJECT_ID
/stakeholders PROJECT_ID --add --name "Ops Lead" --domain product --profile business --topic "queue risk"
```

Run from the repository root:

```powershell
python -m sentinel /stakeholders PROJECT_ID
python -m sentinel /stakeholders PROJECT_ID --add --name NAME --domain LENS [--id STK-00N] [--profile business|technical] [--topic TEXT] [--notes TEXT]
```

The registry lives at `01_discovery/stakeholders.md` and is a GENERATED artifact — mutate it only through this command, never by hand. Each owner governs a `--domain` (a lens such as product, technical, business, design, quality); the interview-script export (IMP-183) groups open gaps by their owner ("these questions go to Operations; these to Technology"). A gap whose lens has no registered owner is listed under an explicit "unassigned" heading — never an invented owner. `respondent_profile` reuses IMP-142 (`business` | `technical`) to calibrate phrasing; an unrecognized profile is dropped, not invented. Power-by-Interest scoring and communication plans are out of scope (delivery, not discovery).
