---
description: Export a shareable Ignite Sentinel artifact.
agent: sentinel-health
---

# Ignite Export

Parse `PROJECT_ID`, `--artifact`, and optional `--format md|mdx` / `--fmt md|mdx` from:

```text
/export PROJECT_ID --artifact gaps --format md
/export PROJECT_ID --artifact prd --format mdx
```

Allowed Markdown artifacts: `gaps`, `brief`, `context-request`, `prd`.
Allowed MDX artifact: `prd` only.

Run from the repository root:

```powershell
python -m sentinel /export PROJECT_ID --artifact ARTIFACT --format md
python -m sentinel /export PROJECT_ID --artifact prd --format mdx
```

Markdown export copies the artifact under `08_context_packs/exports/`. MDX export writes a local derived folder under `08_context_packs/exports/prd-mdx/` with `index.mdx`, `blocks.json`, and `README.md`. It is for teams that already have an offline MDX renderer; it does not enable hosted/remote rendering and does not replace Markdown as source of truth.

A brief, PRD or context-request export that still has pending marks comes out stamped as a DRAFT (`deliverable: draft`, with `pending_marks`). `--final` refuses to export until none remain. Gap exports (interview, faq) are working documents. Report which one you produced; never hand over a draft as final.

`--change CHG-NNN` (IMP-386) exports the brief or the gaps of one change (`--format md` or `interview`) to `08_context_packs/exports/CHG-NNN-<name>`; the project's exports are untouched. A change brief with pending marks carries the draft banner, and `--final` refuses while blocking marks remain. A workspace that only has changes refuses an export without `--change`.

`--artifact borde|decisiones --change CHG-NNN` (IMP-412) exports a review view for a third party (md only, a working document without draft banner): `borde` explains each surface of the border (what it is, why in its zone, where it comes from, open doubts) and `decisiones` lists the closed decisions by lens with who decided and who drafted, plus the assumptions to validate; both only with what is registered. Without `--change` they are refused. `--artifact gaps --format faq --change CHG-NNN` exports the change's decided questions as a FAQ (`CHG-NNN-gaps-faq.md`). `--artifact release-guide --change CHG-NNN` exports the guide of the change's release series (`CHG-NNN-release-guide.md`; it exists once `/split --change` is confirmed). A missing source is a gate refusal (exit 4) whose next step is the command that produces it.
