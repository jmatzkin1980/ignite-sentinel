"""Measure a trial from its Claude Code transcript (tools/trial_audit.py, IMP-408).

    python tools/trial_audit.py TRANSCRIPT.jsonl [--out DIR]

Reports which skills were invoked against the skill each command expected, which
runtime files under lib/sentinel the agent read, and which commands the CLI
refused for format (exit 3). Stdlib plus ``sentinel`` (repo root on sys.path).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from sentinel.commands import COMMANDS, skill_for_command  # noqa: E402

RUNTIME_PATH = re.compile(r"lib[\\/]+sentinel[\\/]+(?P<rel>[\w./\\-]+?\.(?:py|json))")
COMMAND_RE = re.compile(
    r"(?:launcher\.py[\"']?|-m\s+sentinel|\bsentinel(?:\.ps1)?|\bignite)\s+/?(?P<verb>[a-z][a-z-]*)(?P<rest>[^\n;&|]*)"
)
EXIT_RE = re.compile(r"^Exit code (\d+)")


def _rel(raw: str) -> str:
    return "sentinel/" + re.sub(r"[\\/]+", "/", raw)


def _result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def read_events(path: Path) -> tuple[list[dict], int]:
    """The ordered events of a transcript and the count of lines that are not JSON."""
    events: list[dict] = []
    unparsed = 0
    by_id: dict[str, dict] = {}
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except ValueError:
            unparsed += 1
            continue
        if not isinstance(record, dict):
            unparsed += 1
            continue
        message = record.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        kind = record.get("type")
        for block in content:
            if not isinstance(block, dict):
                continue
            if kind == "assistant" and block.get("type") == "tool_use":
                name = block.get("name")
                data = block.get("input") or {}
                if name == "Skill":
                    events.append({"kind": "skill", "skill": str(data.get("skill", "")).split(":")[-1], "line": number})
                elif name == "Bash":
                    command = str(data.get("command", ""))
                    for found in COMMAND_RE.finditer(command):
                        verb = found.group("verb")
                        if verb not in COMMANDS:
                            continue
                        event = {
                            "kind": "command",
                            "verb": verb,
                            "command": f"/{verb}{found.group('rest')}",
                            "id": block.get("id"),
                            "line": number,
                        }
                        events.append(event)
                        by_id[block.get("id")] = event
                    for found in RUNTIME_PATH.finditer(command):
                        events.append({"kind": "runtime_read", "rel": _rel(found.group("rel")), "line": number})
                elif name in ("Read", "Grep", "Glob"):
                    target = " ".join(str(data.get(key, "")) for key in ("file_path", "path", "pattern"))
                    for found in RUNTIME_PATH.finditer(target):
                        events.append({"kind": "runtime_read", "rel": _rel(found.group("rel")), "line": number})
            elif kind == "user" and block.get("type") == "tool_result":
                event = by_id.get(block.get("tool_use_id"))
                if event is None:
                    continue
                body = _result_text(block.get("content"))
                lines = body.splitlines()
                match = EXIT_RE.match(lines[0]) if lines else None
                event["exit"] = int(match.group(1)) if match else 0
                for line in lines:
                    if line.startswith("sentinel error:"):
                        event["error"] = line
                        break
    return events, unparsed


def audit(path: Path) -> dict:
    events, unparsed = read_events(Path(path))
    skills: dict[str, int] = {}
    commands: list[dict] = []
    reads: dict[str, int] = {}
    rejections: list[dict] = []
    seen_skills: list[tuple[int, str]] = []
    for event in events:
        if event["kind"] == "skill":
            skills[event["skill"]] = skills.get(event["skill"], 0) + 1
            seen_skills.append((event["line"], event["skill"]))
        elif event["kind"] == "runtime_read":
            reads[event["rel"]] = reads.get(event["rel"], 0) + 1
        else:
            expected = skill_for_command(event["command"])
            base = expected.split(" §")[0]
            before = bool(base) and any(line < event["line"] and name == base for line, name in seen_skills)
            commands.append(
                {
                    "verb": event["verb"],
                    "line": event["line"],
                    "exit": event.get("exit", 0),
                    "expected_skill": expected,
                    "skill_before": before,
                }
            )
            if event.get("error") and event.get("exit", 0) == 3:
                rejections.append({"verb": event["verb"], "line": event["line"], "error": event["error"]})
    expected_all = {c["expected_skill"].split(" §")[0] for c in commands if c["expected_skill"]}
    missing = sorted(expected_all - set(skills))
    late = sum(1 for c in commands if not c["skill_before"] and c["expected_skill"])
    return {
        "transcript": str(path),
        "unparsed_lines": unparsed,
        "skills_invoked": skills,
        "commands": commands,
        "expected_missing": missing,
        "late_skills": late,
        "runtime_reads": reads,
        "format_rejections": rejections,
        "summary": {
            "skills": len(skills),
            "commands": len(commands),
            "runtime_reads": sum(reads.values()),
            "format_rejections": len(rejections),
            "missing_skills": len(missing),
        },
    }


def _mark(flag: bool) -> str:
    return "✓" if flag else "✗"


def render_markdown(report: dict) -> str:
    s = report["summary"]
    out = ["# Trial audit", "", f"Transcript: `{report['transcript']}`", "", "## Summary", ""]
    out += [
        f"- Skills invoked: {s['skills']}",
        f"- Commands: {s['commands']}",
        f"- Runtime reads: {s['runtime_reads']}",
        f"- Format rejections: {s['format_rejections']}",
        f"- Expected skills never loaded: {s['missing_skills']}",
        f"- Late skills (command before its skill): {report['late_skills']}",
        f"- Unparsed lines: {report['unparsed_lines']}",
        "",
        "## Skills",
        "",
    ]
    out += [f"- {name}: {n}" for name, n in sorted(report["skills_invoked"].items())] or ["- none"]
    out += ["", "## Commands and expected skills", "", "| verb | exit | expected skill | loaded before |", "| --- | --- | --- | --- |"]
    for c in report["commands"]:
        out.append(f"| {c['verb']} | {c['exit']} | {c['expected_skill'] or '-'} | {'yes' if c['skill_before'] else 'no'} |")
    if report["expected_missing"]:
        out += ["", "Never loaded: " + ", ".join(report["expected_missing"])]
    out += ["", "## Runtime reads", ""]
    out += [f"- {rel}: {n}" for rel, n in sorted(report["runtime_reads"].items())] or ["- none"]
    out += ["", "## Format rejections", ""]
    out += [f"- line {r['line']} /{r['verb']}: {r['error']}" for r in report["format_rejections"]] or ["- none"]
    all_loaded = report["late_skills"] == 0 and s["missing_skills"] == 0
    out += [
        "",
        "## Targets",
        "",
        f"- {_mark(s['runtime_reads'] == 0)} zero runtime reads",
        f"- {_mark(s['format_rejections'] == 0)} zero format retries",
        f"- {_mark(all_loaded)} every expected skill loaded before its command",
        "",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trial_audit.py", description="Audit a trial transcript.")
    parser.add_argument("transcript")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    path = Path(args.transcript)
    if not path.is_file():
        print(f"trial_audit: transcript not found: {path}", file=sys.stderr)
        return 2
    report = audit(path)
    markdown = render_markdown(report)
    print(markdown)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "trial_audit.md").write_text(markdown, encoding="utf-8")
        (out / "trial_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
