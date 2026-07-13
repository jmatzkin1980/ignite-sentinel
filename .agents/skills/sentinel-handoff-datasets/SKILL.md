---
name: sentinel-handoff-datasets
description: "Use when a developer handoff needs realistic sample data to exercise the specs/stories — generate synthetic datasets (CSV/JSON/SQL) from the governed specs and user stories, write them under 08_context_packs/synthetic/ marked 'SYNTHETIC — not evidence', git-ignored and disposable. This data is invented by design: it is never governed, never cited, never traced. Trigger on 'generate sample/test/seed data for the handoff', 'dummy datasets for developers', or 'fixtures from the specs'."
---

# Sentinel Handoff Datasets

Use this skill to generate **synthetic sample data** — CSV, JSON, or SQL fixtures — that lets developers exercise the specs and user stories during a handoff. You read the governed specs/stories and produce realistic but **invented** rows that match the declared data models, so downstream engineers have something concrete to run against before real data exists.

This data is **synthetic by design**, so it is deliberately **outside governance**: it is not evidence, not part of the SSoT, and not traceable. It lives under `08_context_packs/synthetic/`, is git-ignored and disposable, and is regenerated on demand. It never feeds discovery, ingest, or any citation. Generation is a skill (the coding agent produces better fixtures with the spec in front) — there is **no runtime command** and no governed artifact.

## When to use / when not

- **Use** when specs/stories exist and a developer handoff needs sample data to demonstrate flows, seed a local database, or write example requests — realistic shapes derived from the governed data models.
- **Do not use** to create evidence, requirements, or anything a downstream artifact will cite. Synthetic data answers "what could a row look like", never "what did the client say". If you need real domain facts, that is discovery/ingest — not this skill. And never present synthetic data as observed reality.

## Workflow

1. **Read the governed source, don't invent the schema.** Take the data models, entities, and field constraints from the specs (`03_specs/`) and user stories (`04_backlog/`). The *shape* is grounded in governed artifacts; only the *values* are invented.
2. **Generate into the synthetic area.** Write every file under `08_context_packs/synthetic/` (a sibling of `exports`/`requests`, outside the governed lifecycle tree `00_raw..07_changes`). Use `.csv`, `.json`, or `.sql` as fits the handoff.
3. **Mark every file `SYNTHETIC — not evidence`.** Put the marker in a header comment (CSV/SQL) or a top-level field (JSON), and in a `README.md` manifest for the folder. A reader must never be able to mistake generated rows for cited evidence.
4. **Make the folder self-ignoring.** Write a `.gitignore` inside `08_context_packs/synthetic/` containing `*` and `!.gitignore` so the whole area is git-ignored and never committed in any repo — synthetic data is disposable and reproducible, never versioned.
5. **Keep values plausible but clearly fake.** Respect types, ranges, and referential integrity implied by the models (matching foreign keys, valid enums) so the data actually runs, while using obviously non-real names/values — never copy or approximate real client data.
6. **Hand off without governing.** Point developers at the folder as a runnable seed. Do not ingest it, do not reference it from any governed artifact, and do not update traceability — it stays outside the SSoT entirely.

## Output

A set of files under `08_context_packs/synthetic/` — the datasets (`.csv`/`.json`/`.sql`), a `README.md` manifest that carries the `SYNTHETIC — not evidence` marker and lists which specs/stories each dataset exercises, and a self-ignoring `.gitignore`. None of it is a governed artifact; it is disposable handoff scaffolding regenerated whenever specs change.

## Rules

- **Synthetic is not evidence — the hard invariant.** These files are never cited, never traced, never ingested, and never inform discovery. No governed artifact (anything under `00_raw..07_changes`, PRD, specs, stories, traceability) may reference `08_context_packs/synthetic/`. `/validate` enforces this with a `no_synthetic_citation` guard; a citation to the synthetic area is a defect, not a shortcut.
- **Marked, git-ignored, disposable.** Every file carries `SYNTHETIC — not evidence`; the folder self-ignores via its own `.gitignore`; the data is reproducible from the specs, so it is never committed and never treated as a source of truth.
- **Shape from governance, values invented.** Field names, types, and relationships come from the governed specs/stories; the actual rows are fabricated. Do not smuggle a real requirement in through a "sample" row.
- **Privacy, local-first — non-negotiable.** Generate on the machine from local specs; never send specs or generated data to an external service, and never derive fixtures from real client data. See `sentinel-privacy-local-first`.
- **No runtime change.** There is no Sentinel command for this and no new governed state; generation is entirely in this skill, and governed downstream artifacts are still mutated only via Sentinel commands.

## Anti-patterns

Each row is a mistake this skill exists to prevent, with the correction:

- **Citing synthetic data as evidence** — a spec/story/traceability row pointing at `08_context_packs/synthetic/`. → Synthetic data is never a source; cite governed evidence, and let `/validate`'s `no_synthetic_citation` guard catch the slip.
- **Committing the fixtures** — checking `08_context_packs/synthetic/` into version control. → It is disposable and reproducible from the specs; keep the self-ignoring `.gitignore` so it stays out of the repo.
- **Unmarked generated file** — a dataset with no `SYNTHETIC — not evidence` marker. → Mark every file and the manifest; an unmarked fixture reads as real data downstream.
- **Inventing the schema** — fabricating fields the specs never declared. → Take the shape from `03_specs/`/`04_backlog/`; only the values are invented.
- **Passing fake rows off as real** — presenting a synthetic row as an observed fact or client-provided sample. → It is `SYNTHETIC — not evidence`; if you need real data, that is discovery, not this skill.
