# Skill Authoring Checklist

A checklist for writing and reviewing Ignite Sentinel skills (`.codex/skills/<name>/SKILL.md`, mirrored byte for byte to `.agents/skills/` and `.claude/skills/`, and copied to the Claude Code plugin's `plugins/ignite-sentinel/skills/` with each `python -m sentinel` line rewritten to the plugin's launcher). It is a contributor/maintainer reference: it codifies the writing criteria that keep our skills discoverable, honest about the lifecycle, and cheap to load. Several items are enforced deterministically by `/doctor`; the rest are review discipline.

The canonical source is always `.codex/skills/`. Edit there and regenerate the copies (`python -m sentinel.adapters`); never hand-edit `.agents/skills/`, `.claude/skills/` or `plugins/ignite-sentinel/skills/`. Write runtime calls as `python -m sentinel ...` in the source: that is the line the plugin copy rewrites, and the source must never carry the plugin's form.

## 1. Leading words (anchor consistency)

A skill's `description` is the only signal a model sees when deciding whether to load it. Lead with the same **anchor word(s)** you use in the body heading and in the user guide, so the three surfaces reinforce each other instead of drifting.

- [ ] The `description` opens with the concrete anchor (the artifact or action the skill owns), not throat-clearing.
- [ ] The `name` frontmatter matches the directory exactly, and the body `#` heading names the same concept.
- [ ] The description is **agent-neutral** — do not name a specific agent (e.g. "Codex"); the same text reaches every surface.

Enforced by `/doctor` (`skill_metadata_checks`, IMP-163): missing/unparseable `name`/`description` or a `name` that does not match the directory FAILs; a description naming a specific agent WARNs.

## 2. Split by sequence (no premature completion)

Skills describe a phased lifecycle. Exposing later steps inside an earlier skill tempts the model to "complete" work that is gated downstream.

- [ ] The skill covers **its** phase only; it routes to the next command/skill instead of performing it.
- [ ] It respects the gates (a skill never instructs bypassing a `maturity`/`health` gate; it explains the block and the correct prior step).
- [ ] Missing inputs surface as `GAP-*`, `[PENDING INPUT]`, or `[PENDING DOMAIN CONTEXT]` — never invented to appear "done".

## 3. Context load vs cognitive load

- [ ] The body is as short as it can be while remaining unambiguous; move rarely-needed depth to a `references/` file linked from the body, not inline.
- [ ] Rules are stated once, imperatively; no restating what `AGENTS.md`/`CLAUDE.md` already make always-on.
- [ ] Examples are minimal and runnable (prefer one correct `python -m sentinel /...` invocation over prose).

## 4. Invocation policy (human-only opt-in)

Skills auto-load by default. A skill should be marked **human-only** only when auto-invocation adds no value and deliberate human invocation is the right posture.

- [ ] Default is auto-invocation — do **not** add the flag unless there is a clear reason.
- [ ] To opt out, add `disable-model-invocation: true` to the canonical frontmatter and regenerate the mirrors so the flag propagates byte-identically.
- [ ] Add the skill to `EXPECTED_HUMAN_ONLY_SKILLS` in `sentinel/doctor.py`, and keep the frontmatter, body, and this registry in agreement (leading-words applied to the invocation policy).

Current human-only skills: `sentinel-privacy-local-first` — in a clone its non-negotiable rules are always-on in `AGENTS.md`/`CLAUDE.md`, so auto-loading the skill adds nothing; it is a deliberate deep reference. The plugin ships neither file; there the runtime enforces the core rules and the skills that touch client material carry their own local-first line.

Enforced by `/doctor` (`skill_invocation_checks`, IMP-200): the set of flagged skills must equal `EXPECTED_HUMAN_ONLY_SKILLS` (a flag that creeps onto an unlisted skill or drops off a listed one FAILs), and the flag must be coherent between the canonical source and the `.agents/skills/` and `.claude/skills/` mirrors. The plugin copy is guarded separately: `/doctor` fails when `plugins/` differs from a fresh regeneration.

## 5. Before you commit

- [ ] A new (or renamed) skill is listed in `REQUIRED_CODEX_SKILLS` in `sentinel/doctor.py`. Without that entry `/doctor` never checks its existence, metadata or invocation flag.
- [ ] The skill count in the user guide still matches (it is written as a number in the skills catalog, the README and the surface pages).
- [ ] Regenerated mirrors: `python -m sentinel.adapters` reports `out_of_sync: []`.
- [ ] `/doctor` is green for the skill (`python -m sentinel /doctor`).
- [ ] The full suite passes: `python -m unittest discover -s tests`.
