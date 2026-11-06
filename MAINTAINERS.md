# Maintaining & Evolving Ignite Sentinel

This document is for **contributors who evolve the framework itself**. If you just want to **use** Ignite to mature requirements in your own project, you don't need anything here — the [README](README.md) and the [User Guide](user_guide/00-user-guide.md) are enough, and **none of these conventions constrain your own repository or data**.

The rules below exist because, in this repository, the framework and its trial projects share one public home. They are repository conventions and maintainer hygiene — not product behavior.

## Repository conventions (this framework repo)

- **Keep `main` a clean framework branch.** Real project workspaces, client data, and test outputs don't belong on `main`. Run framework trials in project branches (e.g. `project/ACME_DASHBOARD`) and merge only framework improvements back. *When you use Ignite in your own repo, organize branches however you like — `main` for your project is perfectly fine.*
- **Change via branch + PR.** Don't assume direct push to `main`.
- **`workspaces/` has two audiences (IMP-212).** The root `.gitignore` ignores `workspaces/*` wholesale here so this public framework repo never ships real or test client data — that is the maintainer-scope default, not a claim that workspaces aren't versionable. They are: for a *user's own* (typically private) project repo, the matured workspace is the versionable source of truth (as `AGENTS.md`/`CLAUDE.md` state). Every workspace `/init` creates carries its own `.gitignore` (from `WORKSPACE_GITIGNORE` in `sentinel/workspace.py`) that the user controls; a user un-ignores their project with `!workspaces/<ID>/`. Never relax the blanket rule in a way that lets a maintainer commit real client data to this public repo.
- **Evolve surfaces together.** When you change behavior, update runtime (`sentinel/`), tests, skills (`.codex/skills/`, mirrored to `.agents/skills/` and `.claude/skills/`), command adapters (regenerated via `python -m sentinel.adapters`, never by hand), the MCP server (`sentinel/mcp.py`), docs (`README.md`, `user_guide/`), and `/doctor` together, so the cloned-repo experience stays coherent.
- **Write to the source, never to a mirror.** `.codex/skills/` is a canonical authoring location that *no agent discovers*: Codex reads `.agents/skills`, Claude Code reads `.claude/skills/`, and Kilo Code loads `.agents/skills/` by default. Both mirrors are generated and byte-identical by design — one SKILL.md, one behaviour on three surfaces — and skills have no per-surface rendering, so a surface name written into a skill is a leak, not a variant. The per-surface discovery table lives next to `SKILL_TARGET_DIRS` in `sentinel/adapters.py`.
- **Verify before pushing.** `.\verify.ps1` (unit suite + `/doctor` + evals) must be green; smoke-test the lifecycle on a `tests/fixtures/evals/` fixture when runtime changed. Don't push while tests or `/doctor` fail.
- **Tune project domains and maturity gates** in `sentinel.config.yaml`.
- **Keep the checkout lean.** Eval reports under `tests/evals/reports/` keep only the newest `SENTINEL_EVAL_KEEP_REPORTS` (default 5) per kind; `SENTINEL_EVAL_REPORTS=0` skips writing them (CI). `python tools/clean_local.py` lists regenerable local residue (git-ignored caches and build output, old reports, leftover test tempdirs) as a dry-run; `--apply` deletes it. It never touches tracked files, `.venv/`, `docs/` or `*.local.*`, and offers `workspaces/*` only with `--include-workspaces` plus a typed per-workspace confirmation. Tests must clean what they create: prefer `tempfile.TemporaryDirectory` with `addCleanup` over a bare `mkdtemp()`.

## Semantic verification is portable; the automation is not

Two layers check that a governed artifact still matches its cited evidence, and only one of them is portable:

- **`/self-review` is the portable channel.** It is runtime, so it runs identically on Codex, Kilo Code, Claude Code and the bare CLI: it validates skeptical PRD/spec findings and hard-to-reverse `DEC-*` decisions against verbatim local citations, writes `03_specs/self_review/`, merges cited gaps as `origin: self-review`, and never rewrites artifacts by itself.
- **`ignite-verifier` is surface convenience, not an exclusive capability.** The read-only subagent in `.claude/agents/` plus its opt-in `PostToolUse` hook apply the same doctrine *automatically* after a `Write`/`Edit` on a governed artifact, and only in Claude Code. What a Codex or Kilo user lacks is the automatic trigger, not the verification.

The practical rule when evolving the framework: **no doctrine, gate, or artifact contract may depend on `ignite-verifier` existing.** If a rule matters, it belongs in the runtime — the CLI is the only layer all three surfaces share. The deterministic prohibition on hand-editing governed artifacts is a good model of that: the decision logic lives once in `sentinel/hooks_logic.py` and is enforced by code we ship on the two surfaces that support hooks (the Claude `PreToolUse` hook and the Codex pre-tool-use policy), never by a subagent.

Kilo is the instructive exception, and IMP-235 is why this paragraph is worded carefully. It used to claim the prohibition was enforced on **all three** surfaces via `deny` globs in `kilo.jsonc`. It was not: that file carried a top-level `permissions` key Kilo does not recognize, so the whole block was discarded for seven weeks while `/doctor` stayed green — our checks validated a shape we had invented rather than the one Kilo publishes. The rule is now declared in Kilo's real shape (`permission.edit` with `deny`), but it is **vendor config, not our code**: we can assert it is declared, not that it is honoured. Read the general rule from this: an enforcement claim about a third-party surface is only as good as the behaviour someone observed, so verify it in the tool with auto-approve off before writing it down.

## Surface contracts are verified in the tool, not in the suite

A **surface contract** is any file or directory in this repo that a third-party agent reads as its own configuration: `kilo.jsonc`, `.claude/settings.json`, `.claude/commands/`, `.agents/skills/`, `.codex/hooks/`, `AGENTS.md`, and the rest. They are the only part of the repo whose behavior belongs to somebody else's software.

The unit suite cannot cross that boundary. Nothing in it invokes Kilo Code, Claude Code or Codex — and nothing can, a unittest does not open VS Code — so every assertion we make about those paths has the form *"our file says what we believe"*, and none has the form *"the tool did what the file says"*. Assuming the second follows from the first is what `kilo.jsonc` cost us: it carried a top-level `permissions` key Kilo does not recognize from 2026-06-03 to 2026-07-26, four items were built on top of it, `/doctor` stayed green throughout, and one minimal manual check in Kilo found it in a minute. The pattern generalizes — every contract that ever had a live observation survived; the only one that never had one rotted.

So, when evolving the framework:

- **Any item that touches a surface contract declares how it is checked live**, and a horizon does not close until somebody observed that behavior in the tool, with auto-approve off. A green suite does not close an item of this kind.
- **The declaration goes in `SURFACE_CONTRACTS` in `sentinel/doctor.py`** — path → which surfaces read it, the procedure that proves it, and the date it was last observed. `/doctor` warns when a contract exists in the repo and is missing from that registry, so adding a surface file without saying how it is verified is visible immediately. A Markdown table of the same thing rots by itself; a constant a check guards does not.
- **Read the registry honestly.** The check verifies every contract *has* an entry — it cannot verify that an `observed` date is true. That part is a person's word, and an entry with an empty date means "nobody ever watched this work", not "verified and undated".
- **Declare the vendor's `$schema` where the vendor publishes one.** `kilo.jsonc` and `.claude/settings.json` do; it costs one line and turns "unrecognized key, silent for seven weeks" into a squiggle in the editor while you type it. Find out whether one exists by looking at the installed tool, never by assuming the shape.

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
