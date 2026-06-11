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

MANIFEST_PATH = Path(__file__).parent / "templates" / "commands_manifest.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def manifest_command_names() -> list[str]:
    return [entry["name"] for entry in load_manifest()["commands"]]


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


if __name__ == "__main__":
    result = regenerate()
    print(json.dumps({"regenerated": result, "out_of_sync": out_of_sync()}, indent=2))
