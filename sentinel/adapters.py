"""Single-source adapter generator (IMP-019).

`sentinel/templates/commands_manifest.json` is the canonical definition of every
chat command. The Kilo (`.kilo/commands/`) and Claude (`.claude/commands/`)
adapters are generated from it; editing those files by hand will be flagged by
the sync test. Regenerate with:

    python -m sentinel.adapters
"""
from __future__ import annotations

import json
from pathlib import Path

from .resources import read_package_json

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
    return f"---\ndescription: {entry['description']}\n---\n\n{body}\n"


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
            kilo_target.write_text(kilo_text, encoding="utf-8")
            written["kilo"] += 1
        if not claude_target.exists() or normalized(claude_target.read_text(encoding="utf-8-sig")) != normalized(claude_text):
            claude_target.write_text(claude_text, encoding="utf-8")
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


CANONICAL_SKILLS_DIR = ".codex/skills"
SKILL_TARGET_DIRS = (".agents/skills", ".claude/skills")


def skill_files(root: Path) -> list[Path]:
    base = root / CANONICAL_SKILLS_DIR
    return [item for item in sorted(base.rglob("*")) if item.is_file()]


def regenerate_skills(root: Path | None = None) -> dict[str, int]:
    """Materialize the canonical skills into the Agent Skills standard directories (IMP-018).

    `.codex/skills/` is the canonical source. `.agents/skills/` (Codex, Cursor,
    Gemini CLI and other standard readers) and `.claude/skills/` (Claude Code)
    are generated copies; edit the canonical source and regenerate.
    """
    root = root or Path.cwd()
    base = root / CANONICAL_SKILLS_DIR
    written = {target: 0 for target in SKILL_TARGET_DIRS}
    for item in skill_files(root):
        relative = item.relative_to(base)
        content = item.read_bytes()
        for target in SKILL_TARGET_DIRS:
            destination = root / target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists() or destination.read_bytes() != content:
                destination.write_bytes(content)
                written[target] += 1
    return written


def skills_out_of_sync(root: Path | None = None) -> list[str]:
    root = root or Path.cwd()
    base = root / CANONICAL_SKILLS_DIR
    issues: list[str] = []
    for item in skill_files(root):
        relative = item.relative_to(base)
        for target in SKILL_TARGET_DIRS:
            destination = root / target / relative
            if not destination.exists():
                issues.append(f"{target}: missing {relative.as_posix()}")
            elif destination.read_bytes() != item.read_bytes():
                issues.append(f"{target}: {relative.as_posix()} differs from canonical source")
    return issues


if __name__ == "__main__":
    result = regenerate()
    skills_result = regenerate_skills()
    print(
        json.dumps(
            {
                "regenerated_commands": result,
                "regenerated_skills": skills_result,
                "out_of_sync": out_of_sync() + skills_out_of_sync(),
            },
            indent=2,
        )
    )
