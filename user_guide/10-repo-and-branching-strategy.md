# Repo And Branching Strategy

This guide defines how to keep Ignite Sentinel portable, clean, and safe to download in secured environments.

## Principle

`main` is the framework branch. It should contain only:

- Sentinel runtime code;
- Codex skills;
- Kilo Code agents;
- user guides;
- installers and adapter config;
- empty scaffolding such as `input/` and `workspaces/_template/`.

`main` should not contain:

- client documents;
- generated project workspaces;
- workflow test outputs;
- meeting transcripts, email exports, Slack exports, screenshots, architecture files, or design files from a real project.

## Project Branches

Create a dedicated branch when running a real client/project workflow or a workflow test with realistic data.

```powershell
git switch main
git pull
git switch -c project/PROJECT_ID
```

Examples:

```powershell
git switch -c project/ACME_DASHBOARD
git switch -c test/backlog-readiness-fixture
```

Use `project/` for real client execution and `test/` for disposable workflow experiments.

## Project Intake Folder Contract

Use `input/` as the local staging area for raw evidence before ingestion:

```text
input/
  client_requirement/     Initial synchronization guide or raw requirement
  business_context/       Business rules, glossary, policies, operating model
  technology_context/     Architecture docs, repo URLs, API notes, integration notes
  design_context/         Snapshots, sketches, design-system references, UX notes
  quality_context/        QA risks, known defects, acceptance expectations
  interactions/           Meeting notes, transcripts, email, Slack excerpts
```

These folders are staging conventions. The source of truth after ingestion lives under the project workspace.

## Workspace Contract

Each project workspace is created under:

```text
workspaces/PROJECT_ID/
```

The repo includes `workspaces/_template/` so a fresh clone already shows the expected structure.

Raw evidence should be organized by source type:

```text
workspaces/PROJECT_ID/00_raw/
  00_client_requirement/
  01_business_context/
  02_technology_context/
  03_design_context/
  04_quality_context/
  05_interactions/
```

New information after the initial discovery should be treated as a controlled change:

```text
workspaces/PROJECT_ID/07_changes/
  00_client_responses/
  01_meetings/
  02_mail_slack/
  03_domain_updates/
```

## Merge Rules

Merge into `main` only when the change improves the framework itself.

Good candidates to merge:

- new CLI behavior;
- better validators;
- improved templates;
- improved Codex/Kilo instructions;
- user guide improvements;
- generic fixtures that contain no client data.

Do not merge:

- generated `workspaces/PROJECT_ID/` data from a real project;
- client-specific raw input;
- project-specific PRDs, backlog, traceability graphs, or memory indexes;
- workflow experiments that exist only to test one client scenario.

## Recommended Lifecycle

1. Start from clean `main`.
2. Create `project/PROJECT_ID`.
3. Stage raw documents in `input/`.
4. Run `/init`, `/ingest`, and `/maturity`.
5. Use gaps as the conversation contract with the client and POD domains.
6. Ingest answers, meeting notes, and domain updates with `/sync`.
7. Generate `/specs` and `/backlog` only when maturity is no longer blocked.
8. Run `/trace`, `/health`, and `/validate`.
9. Keep the project branch separate unless there is an explicit reason to preserve or share it.

## Clean Download Check

Before publishing or merging framework changes:

```powershell
git status --short
python -m sentinel /doctor
python -m unittest discover -s tests
```

On Windows machines without a valid `python` command, use:

```powershell
.\installers\sentinel.ps1 /doctor
```

Confirm no real project workspace is staged.

## Line Endings And Local Files Policy

- `.gitattributes` normalizes line endings (`* text=auto`, LF in the repository). If `git status` ever shows mass "modified" files with no content changes, run `git add --renormalize .` in a dedicated commit with no functional changes mixed in.
- Archives (`*.7z`, `*.zip`) and local tooling residue (such as `.sentinel_doctor_write_test`) are git-ignored and must never be committed. If a launcher or binary genuinely belongs in the repo, add an explicit negation rule and justify it in the PR.
- Personal handoff or context documents live outside the repository (in your personal folders). Evolution/operational memory lives in the local `docs/` folder, which is git-ignored and never published to the public repository.

## Command Adapter Source Of Truth

Chat command definitions live in `sentinel/templates/commands_manifest.json`. The `.kilo/commands/` and `.claude/commands/` files are generated from it:

```powershell
python -m sentinel.adapters
```

Never edit the generated files directly: change the manifest and regenerate. The unit suite fails if any adapter file drifts from the manifest, and `/doctor` verifies the manifest exists. When adding a lifecycle command, update the manifest, regenerate, and review the Codex command-router skill, which routes by pattern and does not need per-command files.
