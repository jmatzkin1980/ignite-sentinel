# Maintaining & Evolving Ignite Sentinel

This document is for **contributors who evolve the framework itself**. If you just want to **use** Ignite to mature requirements in your own project, you don't need anything here — the [README](README.md) and the [User Guide](user_guide/00-user-guide.md) are enough, and **none of these conventions constrain your own repository or data**.

The rules below exist because, in this repository, the framework and its trial projects share one public home. They are repository conventions and maintainer hygiene — not product behavior.

## Repository conventions (this framework repo)

- **Keep `main` a clean framework branch.** Real project workspaces, client data, and test outputs don't belong on `main`. Run framework trials in project branches (e.g. `project/ACME_DASHBOARD`) and merge only framework improvements back. *When you use Ignite in your own repo, organize branches however you like — `main` for your project is perfectly fine.*
- **Change via branch + PR.** Don't assume direct push to `main`.
- **`workspaces/` has two audiences (IMP-212).** The root `.gitignore` ignores `workspaces/*` wholesale here so this public framework repo never ships real or test client data — that is the maintainer-scope default, not a claim that workspaces aren't versionable. They are: for a *user's own* (typically private) project repo, the matured workspace is the versionable source of truth (as `AGENTS.md`/`CLAUDE.md` state). Every workspace `/init` creates carries its own `.gitignore` (from `WORKSPACE_GITIGNORE` in `sentinel/workspace.py`) that the user controls; a user un-ignores their project with `!workspaces/<ID>/`. Never relax the blanket rule in a way that lets a maintainer commit real client data to this public repo.
- **Evolve surfaces together.** When you change behavior, update runtime (`sentinel/`), tests, skills (`.codex/skills/`, mirrored to `.agents/skills/` and `.claude/skills/`), command adapters (regenerated via `python -m sentinel.adapters`, never by hand), the MCP server (`sentinel/mcp.py`), docs (`README.md`, `user_guide/`), and `/doctor` together, so the cloned-repo experience stays coherent.
- **Verify before pushing.** `.\verify.ps1` (unit suite + `/doctor` + evals) must be green; smoke-test the lifecycle on a `tests/fixtures/evals/` fixture when runtime changed. Don't push while tests or `/doctor` fail.
- **Tune project domains and maturity gates** in `sentinel.config.yaml`.

## Working with examples and confidential material

The eval harness is **100% synthetic** (`tests/fixtures/evals/` — *"all content is invented; no real client data"*), so evolving and verifying the framework **never requires real data**. Keep it that way:

- Build new fixtures from invented requirements with deliberate, cataloged omissions — never from real client material.
- When extracting lessons from chats, prior drafts, external research, or confidential files, persist only **generalized framework rules**. Never write client names, system names, source paths, URLs, endpoints, account IDs, raw payloads, or identifying wording into repo artifacts.
- Before pushing, inspect staged files and scan diffs for sensitive terms.

> These are precautions for *this public framework repo*. An end user working in their **own private project repo** has no such constraint — their project data is legitimate there, and the optional backlog privacy scan is configurable for exactly that reason.

## External inspiration

Treat previous drafts, external research, examples, or other frameworks as **inspiration only**: extract reusable workflow intent, templates, validation ideas, and cognitive patterns, then translate them into agnostic Sentinel rules expressed through the framework's own lenses and artifacts. Don't import a parallel vocabulary.

## Internal evolution memory

`docs/evolution/` (git-ignored) holds the local roadmap, the improvement backlog (`02-backlog-mejoras.md`), and the phase proposals. It is operational memory for maintainers, not part of the published product.

## Language

Generated human artifacts follow the project's detected or configured language. This repo's own narrative docs are often authored in Spanish by the maintainers — that's a maintainer preference, not a product requirement.
