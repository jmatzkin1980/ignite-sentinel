"""IMP-267b (H17a): derivations by release, `--release rN`.

PRD, specs, backlog, slice plan, `/quality`, `/view`, `/validate`, `/trace`, `/story-status`,
`/status` and `/next` accept a release of a confirmed series. The compilers are not
forked: the command runs unchanged inside a mirror workspace whose brief is the
release brief, and its outputs are mirrored back:

* mirror: `workspaces/<P>/.series_work/<rN>/workspaces/<P>/` (the command sees it
  as the project, so every path the pipeline knows stays the same);
* input: `02_requirements/<rN>/project-brief.md` as the mirror's brief. Raw input,
  discovery, settings and config come from the project. The EARS rows of
  `requirements.md` are emptied: the release brief is the input, the whole-project
  requirements would leak every release into every other;
* outputs: `03_specs/<rN>/`, `04_backlog/<rN>/`, `06_traceability/<rN>/` and
  `08_context_packs/<rN>/`, with the paths inside the text rewritten to them;
* state: the release keeps its own lifecycle (phase, stories, gates, acceptance
  criteria freezes, fingerprints) in the mirror; the project's `state.json` is not
  touched. The acceptance criteria freeze applies per release when its stories go
  to construction;
* the readiness verdict knows the release it covers.

Without `--release` nothing changes: same paths, same outputs (the invariant).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
from pathlib import Path
from typing import Any, Iterator

from .release_split import ReleaseSplitError
from .split_proposal import RELEASE_ID_RE

WORK_DIR = ".series_work"
MIRRORED = ("03_specs", "04_backlog", "05_quality", "06_traceability", "08_context_packs")
# 07_changes is input (the source log the brief's `sources` citations resolve to); it is not mirrored back
NOT_COPIED = {*MIRRORED, "memory.lancedb", WORK_DIR, "state.json"}
TEXT_SUFFIXES = {".md", ".html", ".json", ".txt", ".mdx", ".csv"}
# what the release's own pipeline writes into state: kept in the mirror, never taken from the project
RELEASE_STATE_KEYS = {
    "phase", "health", "readiness_stage", "metrics", "prd_section_readiness", "specs_gate", "specs_gate_warnings",
    "story_lifecycle", "story_gates", "acceptance_criteria_freezes", "stale_spec_units", "derived_source_fingerprints",
    "artifact_hashes", "command_log", "last_command", "last_command_at",
}
PATH_OPTIONS = ("--evidence", "--override", "--source", "--theme")
RELEASE_COMMANDS = ("specs", "backlog", "quality", "story-status", "view", "validate", "trace", "status", "next")
_ACTIVE: dict[str, str] = {}


def active_release() -> str | None:
    """The release the current command runs for, or None outside a release scope."""
    return _ACTIVE.get("release")


def active_main() -> Path | None:
    """The project workspace behind the current release scope (IMP-269: its partition says what is closed)."""
    return Path(_ACTIVE["main"]) if _ACTIVE.get("main") else None


def release_verdict(project_id: str, rid: str) -> dict[str, Any] | None:
    """A release's own readiness verdict, read from its mirror as it is (nothing refreshed). None if not derived."""
    from .core.paths import repo_root
    from .readiness_verdict import build_readiness_verdict

    root = repo_root().resolve()
    mirror_root = root / "workspaces" / project_id / WORK_DIR / rid
    if not (mirror_root / "workspaces" / project_id / "state.json").is_file():
        return None
    _ACTIVE.update(release=rid, main=str(root / "workspaces" / project_id))
    try:
        with _in_dir(mirror_root):
            return build_readiness_verdict(project_id)
    finally:
        _ACTIVE.pop("release", None)
        _ACTIVE.pop("main", None)


def _series_releases(base: Path) -> list[str]:
    from .core.io import read_json

    partition = read_json(base / "02_requirements" / "series" / "partition.json", None)
    if not isinstance(partition, dict) or partition.get("status") != "confirmed":
        raise ReleaseSplitError("--release needs a confirmed release series; run /split --confirm first")
    series = read_json(base / "02_requirements" / "series" / "series_map.json", None)
    return list((series or {}).get("releases") or []) if isinstance(series, dict) else []


def _strip_ears(text: str) -> str:
    out, skipping = [], False
    for line in text.splitlines():
        if line.strip().startswith("## "):
            skipping = line.strip() == "## Normalized Requirements (EARS)"
            if skipping:
                out += [line, "", "Release scope: the release brief is the input; whole-project EARS rows are not carried.", ""]
                continue
        if not skipping:
            out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _release_compile_report(report: Any, brief_text: str) -> Any:
    """The project's compile report with the fill sites of the marks the release brief keeps."""
    from .brief_model import V2_PENDING_RE, parse_brief

    if not isinstance(report, dict):
        return report
    model = parse_brief(brief_text)
    sites = []
    for number, line in enumerate(brief_text.splitlines(), start=1):
        for match in V2_PENDING_RE.finditer(line):
            place = model.section_id_at_line(number)
            sites.append({"id": f"{place}/release-{number}", "gap": (match.group("gap") or "").strip()})
    return {**report, "fill_sites": sites}


def _sync_graph(main_graph: dict[str, Any], mirror_graph: dict[str, Any], main_ws: str, mirror_ws: str) -> dict[str, Any]:
    """Project input nodes (raw, discovery, requirements) re-rooted, plus the release's own derived nodes."""
    inputs = []
    for node in main_graph.get("nodes", []):
        path = str(node.get("path", "")).replace("\\", "/")
        relative = path[len(main_ws) + 1:] if path.startswith(main_ws + "/") else ""
        top = relative.split("/")[0]
        if top in ("00_raw", "01_discovery") or (top == "02_requirements" and relative.count("/") == 1):
            inputs.append({**node, "path": f"{mirror_ws}/{relative}"})
    input_ids = {n.get("id") for n in inputs}
    derived = [n for n in mirror_graph.get("nodes", []) if n.get("id") not in input_ids]
    ids = input_ids | {n.get("id") for n in derived}
    edges, seen = [], set()
    for edge in [*main_graph.get("edges", []), *mirror_graph.get("edges", [])]:
        key = json.dumps(edge, sort_keys=True)
        if key not in seen and edge.get("from") in ids and edge.get("to") in ids:
            seen.add(key)
            edges.append(edge)
    return {**mirror_graph, "nodes": inputs + derived, "edges": edges}


def _copy_tree(src: Path, dst: Path) -> None:
    from .core.io import copy_file

    if src.is_dir():
        for path in sorted(p for p in src.rglob("*") if p.is_file()):
            copy_file(path, dst / path.relative_to(src))
    elif src.is_file():
        copy_file(src, dst)


def prepare_mirror(project_id: str, rid: str, root: Path) -> Path:
    """Refresh the release mirror from the project; return the mirror root (the cwd to run in)."""
    from .core.io import read_json, write_json, write_text

    main = root / "workspaces" / project_id
    if not RELEASE_ID_RE.match(rid):
        raise ReleaseSplitError(f"{rid!r} is not a release id (r<N> or r<N>.<M>)")
    if rid not in _series_releases(main):
        raise ReleaseSplitError(f"{rid} is not a release of the confirmed series")
    brief = main / "02_requirements" / rid / "project-brief.md"
    if not brief.is_file():
        raise ReleaseSplitError(f"{brief.as_posix()} is missing; the series compiles at /split --confirm")
    mirror_root = main / WORK_DIR / rid
    mirror = mirror_root / "workspaces" / project_id
    previous_state = read_json(mirror / "state.json", {}) if (mirror / "state.json").exists() else {}
    for child in sorted(main.iterdir()):
        if child.name in NOT_COPIED or child.name == "02_requirements":
            continue
        _copy_tree(child, mirror / child.name)
    requirements = main / "02_requirements"
    for child in sorted(requirements.iterdir()):
        if child.is_file() and child.name != "project-brief.md":
            _copy_tree(child, mirror / "02_requirements" / child.name)
    brief_text = brief.read_text(encoding="utf-8")
    write_text(mirror / "02_requirements" / "project-brief.md", brief_text)
    req = mirror / "02_requirements" / "requirements.md"
    if req.is_file():
        write_text(req, _strip_ears(req.read_text(encoding="utf-8")))
    report = mirror / "02_requirements" / "brief_compile_report.json"
    if report.is_file():
        write_json(report, _release_compile_report(read_json(report, None), brief_text))
    for stale in ("split_assessment.json", "split_assessment.md"):
        if (mirror / "01_discovery" / stale).exists():
            (mirror / "01_discovery" / stale).unlink()  # the mirror's own copy; the project keeps its assessment
    main_state = read_json(main / "state.json", {}) or {}
    state = {k: v for k, v in main_state.items() if k not in RELEASE_STATE_KEYS}
    state.update({k: v for k, v in previous_state.items() if k in RELEASE_STATE_KEYS or k not in main_state})
    state["release_scope"] = rid
    write_json(mirror / "state.json", state)
    main_ws, mirror_ws = main.resolve().as_posix(), mirror.resolve().as_posix()
    graph = mirror / "06_traceability" / "traceability_graph.json"
    main_graph = read_json(main / "06_traceability" / "traceability_graph.json", {"nodes": [], "edges": []})
    mirror_graph = read_json(graph, {"nodes": [], "edges": []}) if graph.exists() else {"nodes": [], "edges": []}
    write_json(graph, _sync_graph(main_graph, mirror_graph, main_ws, mirror_ws))
    return mirror_root


def remap(text: str, project_id: str, rid: str, root: Path) -> str:
    """Mirror paths in a text → the release paths of the project."""
    main = (root / "workspaces" / project_id).resolve()
    mirror = (main / WORK_DIR / rid / "workspaces" / project_id).resolve()
    for src, dst in ((mirror.as_posix(), main.as_posix()), (str(mirror), str(main)),
                     (str(mirror).replace("\\", "\\\\"), str(main).replace("\\", "\\\\"))):
        text = text.replace(src, dst)
    folders = "|".join(MIRRORED)
    text = re.sub(rf"(?<![\w.-])({folders})([/\\]{{1,2}})(?!{re.escape(rid)}[/\\])", rf"\1\2{rid}\2", text)
    text = re.sub(r"(?<![\w.-])02_requirements([/\\]{1,2})project-brief\.md", rf"02_requirements\g<1>{rid}\g<1>project-brief.md", text)
    return text


def mirror_outputs(project_id: str, rid: str, root: Path) -> list[str]:
    """Mirror the release's outputs to `<folder>/<rN>/`, paths inside rewritten. Returns the written files."""
    from .core.io import copy_file, write_text

    main = root / "workspaces" / project_id
    mirror = main / WORK_DIR / rid / "workspaces" / project_id
    written: list[str] = []
    for folder in MIRRORED:
        src, dst = mirror / folder, main / folder / rid
        if not src.is_dir():
            continue
        produced = set()
        for path in sorted(p for p in src.rglob("*") if p.is_file()):
            relative = path.relative_to(src)
            if relative.parts and relative.parts[0] == "memory.lancedb":
                continue
            target = dst / relative
            produced.add(target)
            if path.suffix.lower() in TEXT_SUFFIXES:
                write_text(target, remap(path.read_text(encoding="utf-8", errors="replace"), project_id, rid, root))
            else:
                copy_file(path, target)
            written.append(target.as_posix())
        for old in sorted(p for p in dst.rglob("*") if p.is_file()) if dst.is_dir() else []:
            if old not in produced:
                old.unlink()  # a generated mirror file the release no longer produces
    return written


def scoped_argv(argv: list[str]) -> tuple[str | None, list[str]]:
    """(release, argv without --release and with path options made absolute)."""
    out: list[str] = []
    release = None
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--release" and index + 1 < len(argv):
            release, index = argv[index + 1], index + 2
            continue
        if arg.startswith("--release="):
            release, index = arg.split("=", 1)[1], index + 1
            continue
        if arg in PATH_OPTIONS and index + 1 < len(argv):
            value = argv[index + 1]
            out += [arg, str(Path(value).resolve()) if Path(value).exists() else value]
            index += 2
            continue
        out.append(arg)
        index += 1
    return release, out


@contextlib.contextmanager
def _in_dir(path: Path) -> Iterator[None]:
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def run_release_command(argv: list[str], project_id: str, rid: str) -> int:
    """Run one CLI command for a release, inside its mirror, and mirror the outputs back."""
    import sys

    from .cli import main
    from .core.paths import repo_root

    root = repo_root().resolve()
    mirror_root = prepare_mirror(project_id, rid, root)
    out, err = io.StringIO(), io.StringIO()
    _ACTIVE.update(release=rid, main=str(root / "workspaces" / project_id))
    try:
        with _in_dir(mirror_root), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(argv)
    finally:
        _ACTIVE.pop("release", None)
        _ACTIVE.pop("main", None)
    mirror_outputs(project_id, rid, root)
    sys.stdout.write(remap(out.getvalue(), project_id, rid, root))
    sys.stderr.write(remap(err.getvalue(), project_id, rid, root))
    return code


