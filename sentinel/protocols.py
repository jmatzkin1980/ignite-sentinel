from __future__ import annotations

from .errors import GateRefusal, InputError  # IMP-302: typed errors

import sys
from pathlib import Path
from typing import Any

from .workspace import load_config, read_json, state_path, update_state, utc_now, workspace_path
from .core.hashing import file_content_hash, hash_matches
from .core.io import copy_file, remove, write_text
from .governed_artifacts import WORKSPACE_GLOBS

# IMP-127: default volume above which a project is considered to "need context"
# (focused retrieval) rather than whole-artifact reading.
NEEDS_CONTEXT_MIN_CHUNKS = 12

# IMP-147: governed artifacts whose bytes may only change through a Sentinel
# command. Their checksum is snapshotted after every mutating command, so a
# later mismatch means the file was edited outside the CLI. IMP-343: the list
# lives in sentinel.governed_artifacts, shared with the deny hook.
GOVERNED_ARTIFACT_GLOBS = WORKSPACE_GLOBS
# IMP-332: where a hand edit is copied before a mutating command may change it.
HAND_EDITS_DIR = ".sentinel/hand_edits"


def snapshot_governed_artifact_hashes(project_id: str) -> dict[str, str]:
    """Deterministic sha256 registry of governed artifacts (IMP-147)."""
    base = workspace_path(project_id)
    hashes: dict[str, str] = {}
    for pattern in GOVERNED_ARTIFACT_GLOBS:
        for path in sorted(base.glob(pattern)):
            if path.is_file():
                hashes[path.relative_to(base).as_posix()] = file_content_hash(path)  # IMP-291
    return hashes


def hand_edited_artifacts(project_id: str) -> list[str]:
    """IMP-147: governed artifacts whose bytes differ from the last command-produced hash."""
    state = read_json(state_path(project_id), {})
    registered = state.get("artifact_hashes", {})
    if not isinstance(registered, dict) or not registered:
        return []
    root = workspace_path(project_id)
    return sorted(
        rel
        for rel, digest in registered.items()
        if (root / rel).is_file() and not hash_matches(digest, (root / rel).read_bytes())  # IMP-291
    )


# IMP-332: governed hashes taken by preflight, so postflight can tell which
# artifacts the command itself wrote. Keyed by project id; one command per
# workspace at a time (IMP-299 lock).
_PRE_COMMAND: dict[str, dict[str, Any]] = {}


def keep_hand_edits(project_id: str, command: str) -> Path | None:
    """IMP-332: copy every hand-edited governed artifact before a mutating command runs.

    The command may regenerate the file; the copy guarantees the BA's text is
    never lost. Returns the folder holding the copies, or None when nothing was edited.
    """
    edited = hand_edited_artifacts(project_id)
    if not edited:
        return None
    base = workspace_path(project_id)
    stamp = utc_now().replace(":", "").replace("+0000", "Z").replace("+", "_")
    folder = base / HAND_EDITS_DIR / f"{stamp}-{command}"
    suffix = 2
    while folder.exists():
        folder = base / HAND_EDITS_DIR / f"{stamp}-{command}-{suffix}"
        suffix += 1
    for rel in edited:
        copy_file(base / rel, folder / rel)
    return folder


def kept_hand_edits(project_id: str) -> list[tuple[str, str]]:
    """IMP-332: (artifact, copy) pairs whose kept text is no longer in the artifact.

    A copy equal to the current file is not listed: the edit is still in place
    and the out-of-CLI warning already names it.
    """
    base = workspace_path(project_id)
    root = base / HAND_EDITS_DIR
    if not root.is_dir():
        return []
    kept: list[tuple[str, str]] = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        for copy in sorted(p for p in folder.rglob("*") if p.is_file()):
            rel = copy.relative_to(folder).as_posix()
            current = base / rel
            if current.is_file() and current.read_bytes() == copy.read_bytes():
                continue
            kept.append((rel, copy.relative_to(base).as_posix()))
    return kept


def settle_governed_hashes(project_id: str, command: str) -> dict[str, str]:
    """IMP-332: re-snapshot only the governed artifacts this command wrote.

    An artifact the command left untouched keeps its last command-produced hash,
    so a hand edit stays flagged by /health. A newly created artifact is
    registered. Copies kept by preflight whose text is still in the file are
    dropped as redundant.
    """
    pre = _PRE_COMMAND.pop(project_id, None)
    current = snapshot_governed_artifact_hashes(project_id)
    registered = read_json(state_path(project_id), {}).get("artifact_hashes", {})
    if pre is None or not isinstance(registered, dict) or not registered:
        settled = current
    else:
        before = pre["hashes"]
        settled = {
            rel: digest if rel not in registered or before.get(rel) != digest else registered[rel]
            for rel, digest in current.items()
        }
    folder = pre.get("kept") if pre else None
    if folder is not None and folder.is_dir():
        base = workspace_path(project_id)
        for copy in sorted(p for p in folder.rglob("*") if p.is_file()):
            target = base / copy.relative_to(folder)
            if target.is_file() and target.read_bytes() == copy.read_bytes():
                remove(copy)
        for directory in sorted((d for d in folder.rglob("*") if d.is_dir()), key=lambda d: len(d.parts), reverse=True):
            if not any(directory.iterdir()):
                remove(directory)
        if not any(folder.iterdir()):
            remove(folder)
        else:
            changed = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
            print(
                f"sentinel warning: /{command} changed hand-edited "
                + ", ".join(changed)
                + f"; the edited text is kept in {folder.relative_to(base).as_posix()}/. "
                "Carry the change through the owning command or /sync, then delete the copy.",
                file=sys.stderr,
            )
    return settled


def reconcile_health(project_id: str) -> None:
    """IMP-332: a command may not clear a /health DIRTY verdict whose cause remains.

    Commands set `health` on their own criteria. When one leaves it CLEAN while
    the last /health report was DIRTY, recompute /health from the current
    findings; its verdict wins.
    """
    state = read_json(state_path(project_id), {})
    if str(state.get("health", "")).upper() != "CLEAN":
        return
    report = read_json(workspace_path(project_id) / "06_traceability" / "health_report.json", {})
    if not isinstance(report, dict) or report.get("verdict") != "DIRTY":
        return
    from .health import run_health

    run_health(project_id)

# IMP-244: every command is read-only, mutating or exempt with its reason, exactly once.
# IMP-303: the sets come from the single command registry (sentinel/commands.py).
from .commands import MUTATING_COMMANDS, PROTOCOL_EXEMPT_COMMANDS, READ_ONLY_COMMANDS  # noqa: E402

PROJECT_COMMANDS = READ_ONLY_COMMANDS | MUTATING_COMMANDS


def preflight_command(command: str, project_id: str | None) -> None:
    if command not in PROJECT_COMMANDS:
        return
    if not project_id:
        raise InputError(f"{command} requires PROJECT_ID.")

    base = workspace_path(project_id)
    if not base.exists():
        raise GateRefusal(f"Workspace not found: {project_id}. Run /init {project_id} first.")

    from .core.state import load_durable_state

    # IMP-331: a missing or broken state.json stops every project command before it writes.
    state = load_durable_state(project_id, require=True) or {}
    health = str(state.get("health", "UNKNOWN")).upper()
    phase = str(state.get("phase", "unknown"))

    if command in {"specs", "backlog"} and phase == "initialized":
        raise GateRefusal("Cannot generate downstream artifacts before /ingest creates discovery artifacts.")

    if command in {"backlog", "quality", "refine-backlog"} and health == "DIRTY":
        refuse_dirty_health(command, project_id)

    if command in {"backlog", "backlog-status", "quality", "refine-backlog", "implementation-feedback", "story-status"}:
        from .backlog.hooks import assert_backlog_privacy_clean

        assert_backlog_privacy_clean(project_id)

    if command == "quality":
        from .core.graph import load_graph

        if not any(node.get("type") == "user_story" for node in load_graph(project_id).get("nodes", [])):
            raise GateRefusal("Cannot generate quality artifacts without backlog user stories.")

    if command in MUTATING_COMMANDS:
        # IMP-332: remember what the governed artifacts looked like before the
        # command, and keep a copy of any hand edit it might overwrite.
        _PRE_COMMAND[project_id] = {
            "hashes": snapshot_governed_artifact_hashes(project_id),
            "kept": keep_hand_edits(project_id, command),
        }


def refuse_dirty_health(command: str, project_id: str) -> None:
    """IMP-360: the DIRTY gate of /backlog, /quality and /refine-backlog.

    The findings come from /health (computed, not written). /backlog may run
    when every finding is one it clears itself (the knowledge change left only
    the backlog artifacts stale); otherwise each command is refused with what to
    do next. /quality and /refine-backlog consume the backlog, so they wait.
    """
    from .health import STALE_ARTIFACT_OWNERS, collect_health, pending_stale_artifacts

    collected = collect_health(project_id)
    findings = collected["findings"]
    prefix = f"Cannot run /{command} while project health is DIRTY"
    if not findings:
        # DIRTY was set by another command's own criteria; /health recomputes it.
        raise GateRefusal(
            f"{prefix}. Run /health to recompute project health, then run /{command} again.",
            "Run /health.",
        )
    others = [finding for finding in findings if finding not in collected["remediated_by_backlog"]]
    if command == "backlog" and not others:
        return
    if all(finding in collected["knowledge_staleness"] for finding in findings):
        # Only the knowledge change keeps health DIRTY: name the commands that
        # regenerate what it left stale, in order, ending with /backlog.
        pending = pending_stale_artifacts(project_id)
        steps = list(dict.fromkeys(STALE_ARTIFACT_OWNERS.get(rel, "/backlog") for rel in pending))
        steps = [step for step in steps if step != "/backlog"] + ["/backlog"]
        if command != "backlog":
            steps.append(f"/{command}")
        chain = ", then ".join(steps)
        stale = ", ".join(rel.rsplit("/", 1)[-1] for rel in pending)
        verb = "was" if len(pending) == 1 else "were"
        raise GateRefusal(
            f"{prefix}: knowledge changed after {stale} {verb} generated. Run {chain}.",
            f"Run {chain}.",
        )
    more = f" ({len(others) - 1} more finding(s))" if len(others) > 1 else ""
    next_step = f"Run /health to see every finding, fix them, then run /{command} again."
    raise GateRefusal(f"{prefix}: {others[0]}{more} {next_step}", next_step)


def postflight_command(command: str, project_id: str | None, result: Any) -> None:
    if command not in PROJECT_COMMANDS or not project_id:
        return

    has_override = isinstance(result, dict) and bool(result.get("override"))
    if command in MUTATING_COMMANDS or (command == "validate" and has_override):
        from .traceability import write_mermaid_graph, write_traceability_matrix

        write_traceability_matrix(project_id)
        write_mermaid_graph(project_id)

    from .core.state import append_command_log, read_command_log

    if command in MUTATING_COMMANDS and command != "split":
        # IMP-263 [A45]: a command that changed the brief (a spike or measurer
        # closed, a gap answered) re-runs an existing split assessment.
        from .split import refresh_if_stale

        refresh_if_stale(project_id)
        # IMP-267a: recompiling is the synchronization; a confirmed series follows the brief.
        from .release_series import refresh_series_if_stale

        refresh_series_if_stale(project_id)
    if command in MUTATING_COMMANDS:
        # IMP-147: a mutating command is the only sanctioned writer of governed
        # artifacts. IMP-332: refresh the checksum of the artifacts it wrote only,
        # so /health keeps flagging a hand edit the command did not touch.
        update_state(project_id, artifact_hashes=settle_governed_hashes(project_id, command))
        # IMP-332: health follows the current findings, not the last writer.
        reconcile_health(project_id)

    state = read_json(state_path(project_id), {})
    entry = {
        "timestamp": utc_now(),
        "command": command,
        "phase": state.get("phase", "unknown"),
        "health": state.get("health", "UNKNOWN"),
        "summary": summarize_result(result),
    }
    append_command_log(project_id, entry)  # IMP-300: .sentinel/command_log.jsonl, append-only
    command_log = read_command_log(project_id, limit=25)
    state_updates: dict[str, Any] = {
        "last_command": command,
        "last_command_at": entry["timestamp"],
    }
    update_state(project_id, **state_updates)
    write_command_protocol_log(project_id, command_log)


def evaluate_needs_context(project_id: str, indexed_chunks: int) -> dict[str, Any]:
    """IMP-127: portable, soft "needs-context" gate.

    Warns when a project holds enough indexed memory to warrant focused retrieval
    but has no focus context pack — i.e. a high-volume flow likely read whole
    artifacts instead of consulting focus. The trigger is the *volume of
    retrievable context*, NOT whether LanceDB is present, so it fires identically
    in ``json-hybrid``. Soft by default (a ``/health`` warning); ``strict`` opt-in
    via config ``needs_context_gate.strict`` escalates it to a blocking finding.
    This mirrors the existing ``backlog_gate``/``implementability_gate`` pattern:
    runtime gate, no editor hooks, no new command surface.
    """
    config = load_config(project_id)
    gate = config.get("needs_context_gate", {})
    gate = gate if isinstance(gate, dict) else {}
    strict = bool(gate.get("strict", False))
    threshold = int(gate.get("min_chunks", NEEDS_CONTEXT_MIN_CHUNKS))
    packs_dir = workspace_path(project_id) / "08_context_packs"
    has_focus_pack = packs_dir.exists() and any(packs_dir.glob("*_focus.json"))
    needs_context = indexed_chunks >= threshold and not has_focus_pack
    message = None
    if needs_context:
        message = (
            f"Project holds {indexed_chunks} indexed chunks but no focus context pack; "
            "consult focused retrieval (a *_focus.json pack or /retrieve --write-pack) "
            "instead of reading whole artifacts before downstream work."
        )
    return {
        "needs_context": needs_context,
        "strict": strict,
        "threshold": threshold,
        "indexed_chunks": indexed_chunks,
        "has_focus_pack": has_focus_pack,
        "message": message,
    }


def summarize_result(result: Any) -> str:
    if isinstance(result, dict):
        keys = ("readiness", "verdict", "change_id", "spec_id", "story_id", "count", "processed", "detected")
        parts = [f"{key}={result[key]}" for key in keys if key in result]
        if parts:
            return "; ".join(parts)
        if "changes" in result and isinstance(result["changes"], list):
            return f"changes={len(result['changes'])}"
    return "completed"


def write_command_protocol_log(project_id: str, command_log: list[dict[str, Any]]) -> Path:
    path = workspace_path(project_id) / "06_traceability" / "command_protocol_log.md"
    rows = "\n".join(
        f"| {entry.get('timestamp', '')} | `{entry.get('command', '')}` | {entry.get('phase', '')} | {entry.get('health', '')} | {entry.get('summary', '')} |"
        for entry in command_log
    )
    if not rows:
        rows = "| N/A | N/A | N/A | N/A | N/A |"
    write_text(path, f"""# Command Protocol Log - {project_id}

This log records Sentinel vNext command anchors. It is the repo-local replacement for Roo command sync anchors.

| Timestamp | Command | Phase | Health | Summary |
| --- | --- | --- | --- | --- |
{rows}
""")
    return path
