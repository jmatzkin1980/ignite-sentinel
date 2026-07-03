# Ignite Verifier Hook (IMP-146) — opt-in

Read-only verification of governed artifacts after a `Write`/`Edit`, run by the
`ignite-verifier` subagent (`.claude/agents/ignite-verifier.md`) with an
**isolated context**: the verifier did not produce the artifact and does not
inherit the reasoning that generated it.

**It is opt-in by design.** Nothing in this folder activates automatically:
adopters who do not use Claude Code — or who do not want the hook — are not
affected. To enable it, copy the `hooks` block from
[`verify-governed-artifact.example.json`](verify-governed-artifact.example.json)
into your local, non-versioned `.claude/settings.local.json`.

## What it does

- Triggers on `PostToolUse` for `Write`/`Edit` whose target is a governed
  artifact: `workspaces/*/02_requirements/project-brief.md`,
  `workspaces/*/03_specs/*.md`, `workspaces/*/04_backlog/*.md`.
- Spawns the `ignite-verifier` agent (tools restricted to `Read, Grep, Glob`;
  explicit denylist of `Write/Edit/Bash/Agent` in its definition — read-only by
  design, not just by allowlist).
- The verifier checks the change against local cited evidence (no invention,
  criterion continuity, governed mutation channel) and reports `VERIFIED` or
  `BLOCKED: …` with cited findings into the main agent's context. It never
  auto-corrects; the BA/main agent decides.

## Why PostToolUse and not a hard guarantee

Hooks can be bypassed by writes that never go through the `Write`/`Edit` tools
(e.g. shell redirects). This hook is one layer; the deterministic complement is
the generated-artifact checksum check (IMP-147) and the phase-close
self-correction inside the runtime (IMP-145), which do not depend on the editor.

## Requirements and fallback

Agent-type hooks require a Claude Code version with Agent-hook support. If your
version only supports command hooks, skip this hook and run the equivalent
verification manually through the governed channel:

```powershell
python -m sentinel /self-review PROJECT_ID --source input\interactions\self-review.json
```

## Manual smoke test (hooks do not run under unittest)

1. Copy the example block into `.claude/settings.local.json`.
2. In a scratch workspace, edit `workspaces/<ID>/02_requirements/project-brief.md`
   introducing a claim with no citation, assumption, or pending marker.
3. The hook must spawn `ignite-verifier` and the report must flag the uncited
   claim (`BLOCKED: …`) recommending the governed command.
4. Repeat with a legitimate regeneration via `/brief`: the report must be
   `VERIFIED: …` and add no friction.
