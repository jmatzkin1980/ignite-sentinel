# Ignite Sentinel governed-artifact hooks

Governed artifacts — `workspaces/*/02_requirements/project-brief.md`,
`workspaces/*/03_specs/*.md`, `workspaces/*/04_backlog/*.md` — are regenerated
only through their owning command (`/brief`, `/specs`, `/backlog`). Invariant #1:
mutate only via the CLI. Two complementary layers enforce this in the editor,
plus deterministic runtime backstops.

## Tier 1 — deterministic deny (IMP-179, versioned default, all surfaces)

A `PreToolUse` **command** hook, [`deny-governed-artifact-write.py`](deny-governed-artifact-write.py),
denies a hand `Write`/`Edit` of a governed artifact **before** it happens and
points at the owning command. It is stdlib-only, <100ms, and works in **any**
Claude Code version (no Agent-hook support required). It is wired **by default**
in the versioned [`.claude/settings.json`](../settings.json) — the executable
encoding of invariant #1. A BA who needs a deliberate bypass has the CLI.

The decision logic lives once in `sentinel/hooks_logic.py` and is enforced on
**every surface** (per the "keep surfaces aligned" invariant):

- **Claude Code** — this PreToolUse command hook (`permissionDecision: deny`).
- **Codex** — `.codex/hooks/pre_tool_use_policy.py` returns `decision: block`.
- **Kilo Code** — `kilo.jsonc` `permissions.file.deny` globs.

It blocks only *illegitimate* hand-edits; the CLI regenerates governed artifacts
through the command channel, which the hook never sees. Reads are never blocked.

## Tier 3 — deep verification (IMP-146, opt-in)

The `ignite-verifier` subagent (`.claude/agents/ignite-verifier.md`) runs
**read-only** in an **isolated context** after a `Write`/`Edit` (`PostToolUse`),
checking the change against local cited evidence (no invention, criterion
continuity, governed mutation channel) and reporting `VERIFIED` or `BLOCKED: …`.
It never auto-corrects; the BA/main agent decides.

**It is opt-in by design** and requires a Claude Code version with Agent-hook
support. To enable it, copy the `hooks` block from
[`verify-governed-artifact.example.json`](verify-governed-artifact.example.json)
into your local, non-versioned `.claude/settings.local.json`. If your version
supports only command hooks, skip it and run the equivalent verification through
the governed channel:

```powershell
python -m sentinel /self-review PROJECT_ID --source input\interactions\self-review.json
```

## Why hooks are not the whole story

Hooks can be bypassed by writes that never go through the `Write`/`Edit` tools
(e.g. shell redirects). They are enforcement layers, not guarantees; the
deterministic backstops that do not depend on the editor are the generated-artifact
checksum check (IMP-147) and the phase-close self-correction inside the runtime
(IMP-145).

## Manual smoke test (hooks do not run under unittest)

Tier 1 (deny), in a session opened at the repo root:

1. In a scratch workspace, try to `Edit` `workspaces/<ID>/03_specs/prd.md` by hand.
2. The `PreToolUse` hook must **deny** the edit with a message pointing at `/specs`.
3. Regenerating via `/specs` still works (the CLI is not a `Write`/`Edit` tool).

Tier 3 (verifier):

1. Copy the example block into `.claude/settings.local.json`.
2. Edit `workspaces/<ID>/02_requirements/project-brief.md` introducing a claim with
   no citation, assumption, or pending marker.
3. The hook must spawn `ignite-verifier` and the report must flag the uncited
   claim (`BLOCKED: …`) recommending the governed command.
4. Repeat with a legitimate regeneration via `/brief`: the report must be
   `VERIFIED: …` and add no friction.
