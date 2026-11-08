"""Single-source adapter generator (IMP-019).

`sentinel/templates/commands_manifest.json` is the canonical definition of every
chat command. The Kilo (`.kilo/commands/`) and Claude (`.claude/commands/`)
adapters are generated from it; editing those files by hand will be flagged by
the sync test. Regenerate with:

    python -m sentinel.adapters
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .resources import read_package_json
from .core.io import write_bytes, write_text

_DEFAULT_MANIFEST_PATH = Path(__file__).parent / "templates" / "commands_manifest.json"
MANIFEST_PATH = _DEFAULT_MANIFEST_PATH


def load_manifest() -> dict:
    if MANIFEST_PATH == _DEFAULT_MANIFEST_PATH:
        return read_package_json("templates", "commands_manifest.json")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def manifest_command_names() -> list[str]:
    return [entry["name"] for entry in load_manifest()["commands"]]


def runtime_command_names() -> list[str]:
    from .cli import COMMANDS

    return sorted(COMMANDS)


def render_kilo_command(entry: dict) -> str:
    front = [f"description: {entry['description']}"]
    if entry.get("kilo_agent"):
        front.append(f"agent: {entry['kilo_agent']}")
    front_text = "\n".join(front)
    return f"---\n{front_text}\n---\n\n{entry['body']}\n"


def render_claude_command(entry: dict) -> str:
    # IMP-225 (H12): `argument-hint` is the Claude Code convention for showing the
    # expected signature in the autocomplete. It is display-only — the body still
    # receives the arguments through the `$ARGUMENTS` line injected below, which
    # is the single channel and must not change. Kilo has no such field, so
    # `render_kilo_command` stays as it is.
    body_lines = entry["body"].splitlines()
    out_lines: list[str] = []
    inserted = False
    for line in body_lines:
        out_lines.append(line)
        if not inserted and line.startswith("# "):
            out_lines.append("")
            out_lines.append("Arguments received from the user invocation: `$ARGUMENTS`")
            inserted = True
    body = "\n".join(out_lines).strip("\n")
    front = [f"description: {entry['description']}"]
    if entry.get("argument_hint"):
        front.append(f"argument-hint: {entry['argument_hint']}")
    front_text = "\n".join(front)
    return f"---\n{front_text}\n---\n\n{body}\n"


def normalized(text: str) -> str:
    return text.lstrip("﻿").replace("\r\n", "\n").strip() + "\n"


def regenerate(root: Path | None = None) -> dict[str, int]:
    root = root or Path.cwd()
    manifest = load_manifest()
    written = {"kilo": 0, "claude": 0}
    kilo_dir = root / ".kilo" / "commands"
    claude_dir = root / ".claude" / "commands"
    kilo_dir.mkdir(parents=True, exist_ok=True)
    claude_dir.mkdir(parents=True, exist_ok=True)
    for entry in manifest["commands"]:
        kilo_target = kilo_dir / f"{entry['name']}.md"
        claude_target = claude_dir / f"{entry['name']}.md"
        kilo_text = render_kilo_command(entry)
        claude_text = render_claude_command(entry)
        if not kilo_target.exists() or normalized(kilo_target.read_text(encoding="utf-8-sig")) != normalized(kilo_text):
            write_text(kilo_target, kilo_text, root=root)
            written["kilo"] += 1
        if not claude_target.exists() or normalized(claude_target.read_text(encoding="utf-8-sig")) != normalized(claude_text):
            write_text(claude_target, claude_text, root=root)
            written["claude"] += 1
    return written


def out_of_sync(root: Path | None = None) -> list[str]:
    """Return adapter files whose content differs from the manifest rendering."""
    root = root or Path.cwd()
    issues: list[str] = []
    for entry in load_manifest()["commands"]:
        for surface, directory, renderer in (
            ("kilo", root / ".kilo" / "commands", render_kilo_command),
            ("claude", root / ".claude" / "commands", render_claude_command),
        ):
            target = directory / f"{entry['name']}.md"
            if not target.exists():
                issues.append(f"{surface}: missing {target.name}")
            elif normalized(target.read_text(encoding="utf-8-sig")) != normalized(renderer(entry)):
                issues.append(f"{surface}: {target.name} differs from manifest")
    return issues


# IMP-233 (H12): `.codex/skills` is this repo's canonical *authoring* location and
# is NOT a discovery path for any surface — not even Codex, whose name it carries
# for historical reasons. What each agent actually reads (verified against each
# product's official documentation, 2026-07-26):
#
#   | Surface     | Skill discovery directories                                    |
#   |-------------|----------------------------------------------------------------|
#   | Codex       | `.agents/skills` (cwd → parent dirs → repo root),               |
#   |             | `$HOME/.agents/skills`, `/etc/codex/skills`                     |
#   | Claude Code | `.claude/skills/` (plus user-level and plugin skills)           |
#   | Kilo Code   | `.kilo/skills/`, `~/.kilo/skills/`, `.agents/skills/` (compat,   |
#   |             | loaded by default), `.claude/skills/` (only with "Claude Code    |
#   |             | Compatibility" enabled), plus `skills.paths`/`skills.urls`       |
#
# So every surface is served through `SKILL_TARGET_DIRS`, and the mirrors are
# byte-identical **by design**: one SKILL.md, one behaviour, three surfaces. That
# identity is enforced by `skills_out_of_sync`, so a per-surface divergence is not
# a matter of editing one mirror. Since IMP-278 the only per-surface variation is
# a *distribution* overlay (`render_skill`): it rewrites the runtime invocation
# line and nothing else, and the clone overlay is the identity. Writing the
# surface name into a skill body is still a leak, not a variant.
CANONICAL_SKILLS_DIR = ".codex/skills"
AGENTS_SKILLS_DIR = ".agents/skills"
CLAUDE_SKILLS_DIR = ".claude/skills"
SKILL_TARGET_DIRS = (AGENTS_SKILLS_DIR, CLAUDE_SKILLS_DIR)

# IMP-231 (H12): the skill directories Kilo discovers *by default*. Kilo also
# reads `.kilo/skills/` and `~/.kilo/skills/`, and `.claude/skills/` only when
# "Claude Code Compatibility" is enabled — an opt-in this repo does not require,
# and one that would double-load the same 24 skills, so the Claude mirror stays
# out on purpose.
#
# IMP-235 corrected what used to be written here: this constant claimed the
# directories had to be covered by a `permissions.file.read` allowlist in
# `kilo.jsonc` or progressive disclosure would fall to `ask`/deny. That key does
# not exist in Kilo's schema, so no allowlist ever applied — reads are open by
# default and the `references/*.md` layer loads without any entry. Confirmed live
# on Kilo Code 7.4.16 (2026-07-26): the 24 skills load from here and a reference
# file opens without a prompt. See doc 45 §3.2.
KILO_DEFAULT_SKILL_DIRS = (AGENTS_SKILLS_DIR,)


# IMP-278: the runtime invocation is the one line a distribution may change.
# The clone runs the package from the checkout; a plugin ships its own launcher,
# which locates itself by `__file__` (IMP-279). `python -m sentinel.adapters` and
# other submodules are maintainer commands and are never rewritten.
RUNTIME_INVOCATION = "python -m sentinel"
SKILL_OVERLAYS = {
    "clone": RUNTIME_INVOCATION,
    # IMP-290: through the plugin's Python resolver, never a bare `python`.
    "claude-plugin": 'sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py"',
}
_INVOCATION = re.compile(re.escape(RUNTIME_INVOCATION) + r"(?![\w.])")
_RENDERED_SUFFIXES = {".md", ".txt"}


def render_skill(content: bytes, surface: str, suffix: str) -> bytes:
    """Apply a surface overlay to one skill file: only the runtime invocation changes."""
    if surface not in SKILL_OVERLAYS:
        raise ValueError(f"unknown skill surface: {surface} (known: {', '.join(sorted(SKILL_OVERLAYS))})")
    invocation = SKILL_OVERLAYS[surface]
    if invocation == RUNTIME_INVOCATION or suffix.lower() not in _RENDERED_SUFFIXES:
        return content
    text = content.decode("utf-8")
    return _INVOCATION.sub(lambda _match: invocation, text).encode("utf-8")


def render_skills(root: Path, surface: str) -> dict[str, bytes]:
    """Render every canonical skill file for `surface`, keyed by its POSIX path under the source."""
    base = root / CANONICAL_SKILLS_DIR
    return {
        item.relative_to(base).as_posix(): render_skill(item.read_bytes(), surface, item.suffix)
        for item in skill_files(root)
    }


def skill_files(root: Path) -> list[Path]:
    base = root / CANONICAL_SKILLS_DIR
    return [item for item in sorted(base.rglob("*")) if item.is_file()]


def regenerate_skills(root: Path | None = None) -> dict[str, int]:
    """Materialize the canonical skills into the Agent Skills standard directories (IMP-018).

    `.codex/skills/` is the canonical source and no agent reads it: the copies
    under `SKILL_TARGET_DIRS` are what the three surfaces discover (see the
    per-surface discovery table next to that constant). `.agents/skills/` serves
    Codex, Kilo (compat, by default) and other standard readers; `.claude/skills/`
    serves Claude Code. Edit the canonical source and regenerate — never a mirror,
    and never by hand.
    """
    root = root or Path.cwd()
    base = root / CANONICAL_SKILLS_DIR
    written = {target: 0 for target in SKILL_TARGET_DIRS}
    for item in skill_files(root):
        relative = item.relative_to(base)
        content = render_skill(item.read_bytes(), "clone", item.suffix)
        for target in SKILL_TARGET_DIRS:
            destination = root / target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists() or destination.read_bytes() != content:
                write_bytes(destination, content, root=root)
                written[target] += 1
    return written


def skills_out_of_sync(root: Path | None = None) -> list[str]:
    root = root or Path.cwd()
    base = root / CANONICAL_SKILLS_DIR
    issues: list[str] = []
    overlays = [value for value in SKILL_OVERLAYS.values() if value != RUNTIME_INVOCATION]
    for item in skill_files(root):
        relative = item.relative_to(base)
        if item.suffix.lower() in _RENDERED_SUFFIXES:
            text = item.read_bytes().decode("utf-8", errors="replace")
            for overlay in overlays:
                if overlay in text:
                    # IMP-278: the source must stay portable, or the plugin render would not round-trip.
                    issues.append(f"{CANONICAL_SKILLS_DIR}: {relative.as_posix()} carries an overlay invocation ({overlay})")
        for target in SKILL_TARGET_DIRS:
            destination = root / target / relative
            if not destination.exists():
                issues.append(f"{target}: missing {relative.as_posix()}")
            elif destination.read_bytes() != item.read_bytes():
                issues.append(f"{target}: {relative.as_posix()} differs from canonical source")
    # IMP-277: a skill renamed or removed at the source must not linger in a mirror.
    canonical = {item.name for item in base.iterdir() if item.is_dir()} if base.is_dir() else set()
    for target in SKILL_TARGET_DIRS:
        mirror = root / target
        if not mirror.is_dir():
            continue
        for item in sorted(mirror.iterdir()):
            if item.is_dir() and item.name.startswith("sentinel-") and item.name not in canonical:
                issues.append(f"{target}: stale skill {item.name} (not in {CANONICAL_SKILLS_DIR})")
    return issues


if __name__ == "__main__":
    import sys

    from .plugin_package import plugin_out_of_sync, regenerate_plugin

    if "--plugin" in sys.argv[1:]:
        # IMP-279: only the Claude Code marketplace and plugins under plugins/.
        print(json.dumps({"regenerated_plugin": regenerate_plugin(), "out_of_sync": plugin_out_of_sync()}, indent=2))
    else:
        result = regenerate()
        skills_result = regenerate_skills()
        plugin_result = regenerate_plugin()
        print(
            json.dumps(
                {
                    "regenerated_commands": result,
                    "regenerated_skills": skills_result,
                    "regenerated_plugin": plugin_result,
                    "out_of_sync": out_of_sync() + skills_out_of_sync() + plugin_out_of_sync(),
                },
                indent=2,
            )
        )
