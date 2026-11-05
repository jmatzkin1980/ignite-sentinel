"""Safe local cleanup for a framework checkout (maintainer tool, stdlib only).

Dry-run by default: lists what would be removed, its size, and why. With
``--apply`` it deletes only:

* git-ignored, untracked build/cache residue in the repo: ``__pycache__/``,
  ``dist/``, ``build/``, ``*.egg-info/``, root ``*.pyz``, ``dashboard.html``,
  ``PATHFINDER-*/`` (each path is re-checked with ``git check-ignore`` and must
  hold no tracked file);
* eval reports beyond the retention window (``tests/evals/report_store.py``);
* leftover test tempdirs older than ``--min-age-hours`` that match the exact
  shapes the suite creates (``tmp*``/``sentinel_*`` holding only workspace
  folders, or only ``01_discovery/gaps.md``).

Never touched: tracked files, ``.venv/``, ``.git/``, ``docs/``, ``*.local.*``,
and ``workspaces/*`` — the latter only with ``--include-workspaces`` plus an
interactive per-workspace confirmation (typing the workspace id). ``git gc`` is
suggested, never run.

Usage:
  python tools/clean_local.py                 # dry-run
  python tools/clean_local.py --apply
  python tools/clean_local.py --apply --include-workspaces
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests" / "evals"))
import report_store  # noqa: E402

PROTECTED_PARTS = {".venv", ".git", "docs", "node_modules"}
ROOT_DIR_PATTERNS = ("dist", "build", "*.egg-info", "PATHFINDER-*")
ROOT_FILE_PATTERNS = ("*.pyz", "dashboard.html")
TEMP_PREFIXES = ("tmp", "sentinel_")
_REPORT_NAME = re.compile(r"^(?P<kind>.+)_\d{4}-\d{2}-\d{2}\.json$")


@dataclass
class Candidate:
    path: Path
    size: int
    reason: str
    group: str  # repo | reports | temp | workspace


@dataclass
class PlanResult:
    candidates: list[Candidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for dirpath, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(dirpath) / name).stat().st_size
            except OSError:
                pass
    return total


def _git(repo: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args], input=stdin, capture_output=True, text=True, check=False
        )
    except OSError:
        return None


def _is_git_repo(repo: Path) -> bool:
    proc = _git(repo, "rev-parse", "--show-toplevel")
    return bool(proc and proc.returncode == 0 and Path(proc.stdout.strip()).resolve() == repo.resolve())


def _ignored(repo: Path, paths: list[Path]) -> set[Path]:
    """Paths git considers ignored (tracked paths are never reported as ignored)."""
    if not paths:
        return set()
    rels = [p.relative_to(repo).as_posix() + ("/" if p.is_dir() else "") for p in paths]
    # NUL-separated bytes: text-mode stdin on Windows would turn "\n" into
    # "\r\n" and git would then match "<path>\r", i.e. nothing.
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "check-ignore", "-z", "--stdin"],
            input=("\0".join(rels) + "\0").encode("utf-8"),
            capture_output=True,
            check=False,
        )
    except OSError:
        return set()
    if proc.returncode not in (0, 1):
        return set()
    hits = {item.decode("utf-8").rstrip("/") for item in proc.stdout.split(b"\0") if item}
    return {p for p, rel in zip(paths, rels) if rel.rstrip("/") in hits}


def _tracked_among(repo: Path, paths: list[Path]) -> set[Path] | None:
    """Candidates that are, or contain, a tracked file (one git call). None = unknown."""
    if not paths:
        return set()
    rels = [p.relative_to(repo).as_posix() for p in paths]
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "-z", "--", *rels], capture_output=True, check=False
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    tracked = [item.decode("utf-8") for item in proc.stdout.split(b"\0") if item]
    return {p for p, rel in zip(paths, rels) if any(t == rel or t.startswith(rel + "/") for t in tracked)}


def _protected(repo: Path, path: Path) -> bool:
    parts = path.relative_to(repo).parts
    return bool(PROTECTED_PARTS.intersection(parts)) or any(".local" in part for part in parts) or (
        parts and parts[0] == "workspaces"
    )


def repo_candidates(repo: Path) -> PlanResult:
    result = PlanResult()
    if not _is_git_repo(repo):
        result.warnings.append(f"{repo} is not the top of a git repository: repo residue is not listed (safety).")
        return result
    found: list[tuple[Path, str]] = []
    for dirpath, dirnames, _files in os.walk(repo):
        current = Path(dirpath)
        if current != repo and _protected(repo, current):
            dirnames[:] = []
            continue
        if "__pycache__" in dirnames:
            found.append((current / "__pycache__", "python bytecode cache"))
            dirnames.remove("__pycache__")
        dirnames[:] = [d for d in dirnames if d not in PROTECTED_PARTS]
    for pattern in ROOT_DIR_PATTERNS:
        found.extend((p, "build/tool output") for p in repo.glob(pattern) if p.is_dir() and not p.is_symlink())
    for pattern in ROOT_FILE_PATTERNS:
        found.extend((p, "generated file") for p in repo.glob(pattern) if p.is_file() and not p.is_symlink())
    ignored = _ignored(repo, [p for p, _ in found])
    tracked = _tracked_among(repo, sorted(ignored))
    if tracked is None:
        result.warnings.append("git ls-files failed: repo residue is not listed (safety).")
        return result
    for path, reason in sorted(found):
        if path in ignored and path not in tracked and not _protected(repo, path):
            result.candidates.append(Candidate(path, _size(path), reason, "repo"))
    return result


def report_candidates(reports_dir: Path, keep: int) -> list[Candidate]:
    if not reports_dir.is_dir():
        return []
    kinds = sorted({m["kind"] for p in reports_dir.iterdir() if (m := _REPORT_NAME.match(p.name))})
    out: list[Candidate] = []
    for kind in kinds:
        for path in report_store.prune(kind, reports_dir=reports_dir, keep=keep, dry_run=True):
            out.append(Candidate(path, _size(path), f"eval report beyond the newest {keep}", "reports"))
    return out


def _is_workspace_leftover(path: Path) -> bool:
    workspaces = path / "workspaces"
    if not workspaces.is_dir():
        return False
    others = [child for child in path.iterdir() if child.name != "workspaces"]
    if any(child.is_dir() for child in others):
        return False
    projects = list(workspaces.iterdir())
    return bool(projects) and all(
        p.is_dir() and (p / "00_raw").is_dir() and (p / "01_discovery").is_dir() for p in projects
    )


def _is_gaps_only_leftover(path: Path) -> bool:
    children = list(path.iterdir())
    if len(children) != 1 or children[0].name != "01_discovery" or not children[0].is_dir():
        return False
    return [c.name for c in children[0].iterdir()] in ([], ["gaps.md"])


def temp_candidates(temp_root: Path, *, min_age_hours: float, now: float | None = None) -> list[Candidate]:
    now = time.time() if now is None else now
    out: list[Candidate] = []
    if not temp_root.is_dir():
        return out
    for path in sorted(temp_root.iterdir()):
        if not path.name.startswith(TEMP_PREFIXES) or not path.is_dir() or path.is_symlink():
            continue
        try:
            if now - path.stat().st_mtime < min_age_hours * 3600:
                continue
            if _is_workspace_leftover(path):
                out.append(Candidate(path, _size(path), "leftover test workspace tempdir", "temp"))
            elif _is_gaps_only_leftover(path):
                out.append(Candidate(path, _size(path), "leftover test gaps tempdir", "temp"))
        except OSError:
            continue  # unreadable (e.g. permission denied): leave it alone
    return out


def workspace_candidates(repo: Path) -> list[Candidate]:
    root = repo / "workspaces"
    if not root.is_dir():
        return []
    return [
        Candidate(p, _size(p), "user workspace (needs confirmation)", "workspace")
        for p in sorted(root.iterdir())
        if p.is_dir() and not p.is_symlink() and p.name != "_template"
    ]


def plan(
    repo: Path,
    *,
    temp_root: Path | None = None,
    keep_reports: int | None = None,
    include_workspaces: bool = False,
    include_temp: bool = True,
    min_age_hours: float = 24,
) -> PlanResult:
    repo = repo.resolve()
    keep = report_store.default_keep() if keep_reports is None else keep_reports
    result = repo_candidates(repo)
    if keep > 0:
        result.candidates.extend(report_candidates(repo / "tests" / "evals" / "reports", keep))
    if include_temp:
        root = Path(tempfile.gettempdir()) if temp_root is None else temp_root
        result.candidates.extend(temp_candidates(root, min_age_hours=min_age_hours))
    if include_workspaces:
        result.candidates.extend(workspace_candidates(repo))
    return result


def _interactive_confirm(candidate: Candidate) -> bool:
    if not sys.stdin or not sys.stdin.isatty():
        print(f"  skip {candidate.path.name}: confirmation needs an interactive terminal")
        return False
    try:
        answer = input(f"  Delete workspace {candidate.path.name}? Type its id to confirm: ")
    except EOFError:
        return False
    return answer.strip() == candidate.path.name


def apply(
    candidates: list[Candidate], *, confirm: Callable[[Candidate], bool] = _interactive_confirm
) -> tuple[list[Candidate], list[tuple[Candidate, str]]]:
    deleted: list[Candidate] = []
    failed: list[tuple[Candidate, str]] = []
    for candidate in candidates:
        if candidate.group == "workspace" and not confirm(candidate):
            continue
        try:
            if candidate.path.is_dir() and not candidate.path.is_symlink():
                shutil.rmtree(candidate.path)
            else:
                candidate.path.unlink()
            deleted.append(candidate)
        except OSError as exc:
            failed.append((candidate, str(exc)))
    return deleted, failed


def _mb(size: int) -> str:
    return f"{size / 2**20:8.2f} MB"


def format_plan(result: PlanResult, *, apply: bool) -> str:
    lines = [f"Local cleanup ({'apply' if apply else 'dry-run: nothing is deleted; use --apply'})"]
    for group in ("repo", "reports", "temp", "workspace"):
        items = [c for c in result.candidates if c.group == group]
        if not items:
            continue
        lines.append(f"\n[{group}] {len(items)} item(s), {_mb(sum(c.size for c in items)).strip()}")
        lines.extend(f"  {_mb(c.size)}  {c.path}  ({c.reason})" for c in items)
    lines.append(f"\nTotal: {len(result.candidates)} item(s), {_mb(sum(c.size for c in result.candidates)).strip()}")
    lines.extend(f"WARN: {w}" for w in result.warnings)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="delete the listed items (default: dry-run)")
    parser.add_argument("--keep-reports", type=int, default=None, help="eval reports kept per kind (default 5)")
    parser.add_argument("--include-workspaces", action="store_true", help="also offer workspaces/* (confirmed one by one)")
    parser.add_argument("--no-temp", action="store_true", help="do not scan the system temp directory")
    parser.add_argument("--temp-root", type=Path, default=None, help="temp directory to scan (default: system temp)")
    parser.add_argument("--min-age-hours", type=float, default=24, help="minimum age of temp leftovers (default 24)")
    args = parser.parse_args(argv)

    result = plan(
        REPO_ROOT,
        temp_root=args.temp_root,
        keep_reports=args.keep_reports,
        include_workspaces=args.include_workspaces,
        include_temp=not args.no_temp,
        min_age_hours=args.min_age_hours,
    )
    print(format_plan(result, apply=args.apply))
    if args.apply:
        deleted, failed = apply(result.candidates)
        print(f"\nDeleted {len(deleted)} item(s), {_mb(sum(c.size for c in deleted)).strip()}.")
        for candidate, error in failed:
            print(f"FAILED {candidate.path}: {error}")
        if failed:
            return 1
    print("\nTip: `git count-objects -vH` shows loose objects; `git gc` compacts them (not run by this tool).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
