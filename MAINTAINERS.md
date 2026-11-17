# Maintaining & Evolving Ignite Sentinel

This document is for **contributors who evolve the framework itself**. If you just want to **use** Ignite to mature requirements in your own project, you don't need anything here — the [README](README.md) and the [User Guide](user_guide/00-user-guide.md) are enough, and **none of these conventions constrain your own repository or data**.

The rules below exist because, in this repository, the framework and its trial projects share one public home. They are repository conventions and maintainer hygiene — not product behavior.

## Repository conventions (this framework repo)

- **Keep `main` a clean framework branch.** Real project workspaces, client data, and test outputs don't belong on `main`. Run framework trials in project branches (e.g. `project/ACME_DASHBOARD`) and merge only framework improvements back. *When you use Ignite in your own repo, organize branches however you like — `main` for your project is perfectly fine.*
- **Change via branch + PR.** Don't assume direct push to `main`.
- **`workspaces/` has two audiences (IMP-212).** The root `.gitignore` ignores `workspaces/*` wholesale here so this public framework repo never ships real or test client data — that is the maintainer-scope default, not a claim that workspaces aren't versionable. They are: for a *user's own* (typically private) project repo, the matured workspace is the versionable source of truth (as `AGENTS.md`/`CLAUDE.md` state). Every workspace `/init` creates carries its own `.gitignore` (from `WORKSPACE_GITIGNORE` in `sentinel/workspace.py`) that the user controls; a user un-ignores their project with `!workspaces/<ID>/`. Never relax the blanket rule in a way that lets a maintainer commit real client data to this public repo.
- **Evolve surfaces together.** When you change behavior, update runtime (`sentinel/`), tests, skills (`.codex/skills/`, mirrored to `.agents/skills/` and `.claude/skills/`), command adapters (regenerated via `python -m sentinel.adapters`, never by hand), the MCP server (`sentinel/mcp.py`), docs (`README.md`, `user_guide/`), and `/doctor` together, so the cloned-repo experience stays coherent.
- **Write to the source, never to a mirror.** `.codex/skills/` is a canonical authoring location that *no agent discovers*: Codex reads `.agents/skills`, Claude Code reads `.claude/skills/`, and Kilo Code loads `.agents/skills/` by default. Both mirrors are generated and byte-identical by design — one SKILL.md, one behaviour on three surfaces — and skills have no per-surface rendering, so a surface name written into a skill is a leak, not a variant. The per-surface discovery table lives next to `SKILL_TARGET_DIRS` in `sentinel/adapters.py`.
- **Verify before pushing.** `.\verify.ps1` (unit suite + `/doctor` + evals) must be green; smoke-test the lifecycle on a `tests/fixtures/evals/` fixture when runtime changed. Don't push while tests or `/doctor` fail. Slow tests (wheel install, future CI-only checks) run only with `SENTINEL_SLOW=1`; run them before a PR that touches packaging. On Linux/macOS use `./verify.sh` (same steps, `--skip-evals`).
- **CI runs in two tiers (IMP-246).**
  - `ci-fast` runs on every push, in under 5 minutes. It covers the unit suite without `tests/slow_modules.txt`, `/doctor` and the faithfulness eval.
  - `ci-full` runs on every pull request. It covers the whole suite, `/doctor`, the discovery and faithfulness evals, the wheel in a clean venv, and a small matrix: Windows/Linux × 3.10/3.13 × with/without LanceDB × `mcp` 1/2.
  - The slow list is explicit, picked from `python tools/time_tests.py`. Re-measure it when the suite grows.
  - Actions are pinned by commit SHA and workflows run with read-only permissions.
  - A workflow is a surface contract: it is only proven by a run observed on GitHub.
- **Supply chain (IMP-289).**
  - Each optional extra has a hash-pinned lock in `constraints/<extra>.txt`; `python tools/check_constraints.py` fails on a dependency without `==` or a hash. Regenerate a lock with the `uv pip compile` command in its header (two-week `--exclude-newer` cooldown).
  - `security` runs dependency review on PRs, CodeQL (Python), `pip-audit` over every lock and a `--require-hashes` install. Dependabot bumps the SHA-pinned actions.
  - `python tools/sbom.py -o <file>` writes the CycloneDX SBOM. On a `v*` tag, `release-attest` builds the wheel and the SBOM and attests their provenance (`gh attestation verify <file> --repo jmatzkin1980/ignite-sentinel`).
- **Tune project domains and maturity gates** in `sentinel.config.yaml`.
- **Keep the checkout lean.** Eval reports under `tests/evals/reports/` keep only the newest `SENTINEL_EVAL_KEEP_REPORTS` (default 5) per kind; `SENTINEL_EVAL_REPORTS=0` skips writing them (CI). `python tools/clean_local.py` lists regenerable local residue (git-ignored caches and build output, old reports, leftover test tempdirs) as a dry-run; `--apply` deletes it. It never touches tracked files, `.venv/`, `docs/` or `*.local.*`, and offers `workspaces/*` only with `--include-workspaces` plus a typed per-workspace confirmation. Tests must clean what they create: prefer `tempfile.TemporaryDirectory` with `addCleanup` over a bare `mkdtemp()`.

## Generated surfaces: adapters, skill mirrors and plugins

Never edit a generated file by hand. Change the source and regenerate:

| Generated | Source | Command |
|---|---|---|
| `.claude/commands/`, `.kilo/commands/` | `sentinel/templates/commands_manifest.json` | `python -m sentinel.adapters` |
| `.agents/skills/`, `.claude/skills/` | `.codex/skills/` | `python -m sentinel.adapters` |
| `plugins/`, `.claude-plugin/marketplace.json` | `.codex/skills/` (with the `claude-plugin` overlay, which only changes the runtime invocation), `sentinel/`, `pyproject.toml` | `python -m sentinel.adapters --plugin` |

- `plugins/*/lib/sentinel/` is a byte-for-byte copy of `sentinel/`; the plugin version comes from `pyproject.toml`.
- The unit suite fails when an adapter or mirror drifts from its source, and `/doctor` → `claude_plugin_check` fails on plugin drift and on the manifest mistakes `claude plugin validate` rejects (`..` in a source, entry name different from manifest name, version in the entry, a `homepage` that is not a URL, reserved names, a top-level `bin/`, `hooks.json` without its `"hooks"` wrapper).
- CI → `plugin-validate` runs Claude Code's own `claude plugin validate --strict` on the marketplace and both plugins.
- When you add a lifecycle command, update the registry (`sentinel/commands.py`) and the manifest, regenerate, and review the command-router skill, which routes by pattern and needs no per-command file.

## Cutting a release

The version lives in `pyproject.toml`. `sentinel/__init__.py` and both `plugin.json` repeat it, and `python tools/release.py check` fails when any of them differs (CI → `release-check`).

1. On a branch, bump `version` in `pyproject.toml` and `__version__` in `sentinel/__init__.py`, then run `python -m sentinel.adapters --plugin`.
2. Bump the pinned ref in `user_guide/20-admin-guide.md` and `user_guide/references/managed-settings.json` by hand: the release tooling does not update them.
3. In `CHANGELOG.md`, rename `## [Unreleased]` to `## [X.Y.Z] — YYYY-MM-DD` and open a new, empty `## [Unreleased]` above it.
4. Merge the PR. Nobody tags by hand: `release-check` on `main` tags `vX.Y.Z` on the merge commit that introduced the version, then calls `release-attest`, which:
   - fails on a tag that is not the version ("tag without a bump") or that has no dated CHANGELOG section;
   - builds the wheel, the SBOM and the two plugin zips, and validates each zip;
   - attests all of them and creates the GitHub release with the CHANGELOG section as notes, plus `SHA256SUMS` for the zips;
   - fast-forwards `stable` to the tag.
5. Verify the release: download the assets, check `SHA256SUMS`, and run `gh attestation verify <file> --repo jmatzkin1980/ignite-sentinel` on each.

`release-check` on `main` also fails when the version is untagged and CHANGELOG has no dated section for it, or when the version sources disagree. A tag pushed by hand (`git push origin vX.Y.Z`) runs the same `release-attest`. `python tools/release.py zip --out dist` builds the same zips locally and reproducibly (same commit, same bytes: `SOURCE_DATE_EPOCH`, sorted entries, LF endings). The `.pyz` zipapp is built locally (`python -m sentinel.build`) and is not a release asset.

## Clean-clone check

Run this end to end on a new machine, or after a change that touches the runtime, to confirm a fresh clone works:

1. Clone into a fresh folder and run `python -m sentinel /doctor` (on Windows without a working `python`, use `.\installers\sentinel.ps1 /doctor`).
2. Run `.\verify.ps1` (or `./verify.sh`): the parallel unit suite, `/doctor` and the evals. Stage your changes first (`git add -A`): `/doctor` only scans tracked files. If a change added a command or a skill, run `python -m sentinel.adapters` before.
3. Smoke the lifecycle on a synthetic input, never client data: `/init SMOKE`, `/ingest SMOKE --source <synthetic note>`, `/status SMOKE` (expect discovery and open gaps), `/specs SMOKE` (expect a gate refusal, exit 4).
4. Open the folder in your agent and confirm it sees its adapter: `.claude/` and `CLAUDE.md`, `.agents/skills/` and `AGENTS.md`, `.kilo/`.
5. Delete the smoke workspace before committing anything.

`python -m unittest -b tests.test_build_pyz` builds `sentinel.pyz`, copies the framework without `.git`, `.venv` or `dist`, and runs `/doctor` from the `.pyz` against that copy.

## Framework branches and merges

- Merge into `main` only what improves the framework: CLI behaviour, validators, templates, agent instructions, user-guide improvements, synthetic fixtures.
- Never merge generated workspaces from a real project, client raw input, project-specific PRDs, backlogs, graphs or memory indexes, or experiments that exist only for one client scenario. Run framework trials in project branches (`project/<ID>`) and keep them apart.
- `.gitattributes` normalizes line endings (`* text=auto`, LF in the repository). If `git status` shows mass "modified" files with no content change, run `git add --renormalize .` in a commit of its own.
- Archives (`*.7z`, `*.zip`) and local tool residue are git-ignored and never committed; a binary that genuinely belongs in the repo needs an explicit negation rule justified in the PR.

## Lens knowledge base (`sentinel/lenses/`)

What each lens scrutinizes, with which severity, which tokens close it and which question it asks is declarative data, one JSON file per lens (`business`, `product`, `quality`, `technical`, `compliance`, `delivery`, `design`). The discovery engine (`detect_gaps`) and the per-domain context requests read the same files, so they never diverge.

Each entry of a lens's `checks` array declares:

- `id`: a stable `GAP-*` identifier; `severity`: `critical | high | medium | low`; `description`: what is missing (in English, like the artifacts).
- `rule`, one of:
  - `absent_tokens`: fires when none of the `tokens` appears in the evidence;
  - `mention_without_counterpart`: a surface-level inquisitive check that fires unless a `counterparts` term appears (the optional `trigger` only supplies the quote);
  - `mention_requires_counterpart`: fires only when the concept is named (`triggers`) and its counterpart is missing; severity `medium`, anchored to the quoted mention;
  - `metric_without_source`: fires on a quantitative metric with none of the `suppressors` (source or baseline words).
- `evidence_scope`: `source | technical | design | quality | frontend | all`.
- `weak_word_smell`: fires on a phrase from `sentinel/smells/*.json` used as weak wording (a review signal, not a block), referenced with `catalog` and `categories`.
- `why` (optional): the field experience behind the check, shown in the context request.

A reassuring token should not close a question when it brings no detail a PRD can use (a goal is not persona detail; a target without a measurement method and window is not a KPI).

To add a check: add the object to the lens file, then run `python tests/evals/run_discovery_evals.py` and the suite. For PRD-grade checks, also update `tests/fixtures/evals/*/answer_key.json` (`must_fire`, `target_fire`, `must_not_fire`, `distractors`) and, when a fixture must pass real gates to `/specs`, add a synthetic answer to its `gap_responses.md`. The eval report includes `gap_benchmark` (precision, recall, F1, per-lens recall, distractor false-positive rate); expect zero new false positives. Backlog changes use the `backlog` block of the same answer keys. The lens model is the team's own knowledge: put field experience here for review in a PR, not generic checklists copied from elsewhere.

## Semantic verification is portable; the automation is not

Two layers check that a governed artifact still matches its cited evidence, and only one of them is portable:

- **`/self-review` is the portable channel.** It is runtime, so it runs identically on Codex, Kilo Code, Claude Code and the bare CLI: it validates skeptical PRD/spec findings and hard-to-reverse `DEC-*` decisions against verbatim local citations, writes `03_specs/self_review/`, merges cited gaps as `origin: self-review`, and never rewrites artifacts by itself.
- **`ignite-verifier` is surface convenience, not an exclusive capability.** The read-only subagent in `.claude/agents/` plus its opt-in `PostToolUse` hook apply the same doctrine *automatically* after a `Write`/`Edit` on a governed artifact, and only in Claude Code. What a Codex or Kilo user lacks is the automatic trigger, not the verification.

The practical rule when evolving the framework: **no doctrine, gate, or artifact contract may depend on `ignite-verifier` existing.** If a rule matters, it belongs in the runtime — the CLI is the only layer all three surfaces share. The deterministic prohibition on hand-editing governed artifacts is a good model of that: the list of governed files lives once in `sentinel/governed_artifacts.py` (shared with `/health`'s hand-edit hashes and the `kilo.jsonc` check), the decision logic once in `sentinel/hooks_logic.py`, and both are enforced by code we ship on the two surfaces that support hooks (the Claude `PreToolUse` hook and the Codex pre-tool-use policy), never by a subagent.

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
