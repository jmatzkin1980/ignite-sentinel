"""Hash-pinned locks for the optional extras (IMP-289).

    python tools/check_constraints.py [--root PATH]

Every extra in ``[project.optional-dependencies]`` must have a lock in
``constraints/<extra>.txt`` where each requirement is pinned with ``==`` and
carries at least one ``--hash=sha256:<64 hex>``; the lock must name every direct
requirement of its extra, and no lock may exist for an extra that is gone.
Editable installs, direct URLs and index options are refused. Exit code 1 lists
every problem. Stdlib only (``tomllib`` when present, a minimal parser on 3.10).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
STRING_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


@dataclass
class Requirement:
    raw: str
    line: int
    name: str = ""
    version: str = ""
    marker: str = ""
    hashes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _logical_lines(text: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    buffer, start = "", 0
    for number, physical in enumerate(text.splitlines(), start=1):
        stripped = physical.split(" #", 1)[0] if not physical.lstrip().startswith("#") else ""
        if not buffer:
            start = number
        if stripped.rstrip().endswith("\\"):
            buffer += stripped.rstrip()[:-1] + " "
            continue
        buffer += stripped
        if buffer.strip():
            lines.append((start, buffer.strip()))
        buffer = ""
    if buffer.strip():
        lines.append((start, buffer.strip()))
    return lines


def parse_requirements(text: str) -> list[Requirement]:
    entries: list[Requirement] = []
    for number, logical in _logical_lines(text):
        req = Requirement(raw=logical, line=number)
        entries.append(req)
        tokens = logical.split()
        hashes = [t.split("=", 1)[1] for t in tokens if t.startswith("--hash=")]
        req.hashes = hashes
        spec = " ".join(t for t in tokens if not t.startswith("--hash="))
        if spec.startswith("-"):
            req.errors.append(f"option line not allowed: {spec}")
            continue
        if "@" in spec.split(";", 1)[0]:
            req.errors.append("direct URL requirements are not allowed")
        requirement, _, marker = spec.partition(";")
        req.marker = marker.strip()
        match = NAME_RE.match(requirement)
        if not match:
            req.errors.append(f"unreadable requirement: {spec}")
            continue
        req.name = normalize_name(match.group(1).split("[", 1)[0])
        pin = re.fullmatch(r"\s*[A-Za-z0-9._-]+(?:\[[^\]]*\])?\s*==\s*([^\s,;=<>!~]+)\s*", requirement)
        if pin:
            req.version = pin.group(1)
        else:
            req.errors.append("not pinned with ==")
        if not hashes:
            req.errors.append("no --hash (every dependency must be hash-pinned)")
        for value in hashes:
            if not HASH_RE.match(value):
                req.errors.append(f"hash must be sha256:<64 hex>, got {value!r}")
    return entries


def check_file(path: Path) -> list[str]:
    entries = parse_requirements(path.read_text(encoding="utf-8"))
    if not entries:
        return [f"{path.name}: no requirements"]
    errors = []
    for req in entries:
        label = req.name or req.raw
        errors.extend(f"{path.name}:{req.line}: {label}: {problem}" for problem in req.errors)
    return errors


def parse_pyproject_minimal(text: str) -> dict:
    """``name``, ``version`` and ``optional-dependencies`` of ``[project]``, no tomllib needed."""
    meta: dict = {"optional-dependencies": {}}
    section = ""
    pending_key, pending = "", ""
    for physical in text.splitlines():
        line = physical.strip()
        if pending_key:
            pending += " " + line
            if "]" in line:
                meta["optional-dependencies"][pending_key] = STRING_RE.findall(pending)
                pending_key, pending = "", ""
            continue
        if not line or line.startswith("#"):
            continue
        header = re.fullmatch(r"\[([^\]]+)\]", line)
        if header:
            section = header.group(1).strip()
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key, value = key.strip().strip('"'), value.strip()
        if section == "project" and key in ("name", "version", "license"):
            found = STRING_RE.search(value)
            if found:
                meta[key] = found.group(1)
        elif section == "project.optional-dependencies":
            if "]" in value:
                meta["optional-dependencies"][key] = STRING_RE.findall(value)
            else:
                pending_key, pending = key, value
    return meta


def load_project(root: Path) -> dict:
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    try:
        import tomllib
    except ImportError:  # Python 3.10
        return parse_pyproject_minimal(text)
    project = tomllib.loads(text).get("project", {})
    license_value = project.get("license", "")
    if isinstance(license_value, dict):
        license_value = license_value.get("text", "")
    return {
        "name": project.get("name", ""),
        "version": project.get("version", ""),
        "license": license_value,
        "optional-dependencies": project.get("optional-dependencies", {}),
    }


def lock_files(root: Path) -> dict[str, Path]:
    folder = root / "constraints"
    return {path.stem: path for path in sorted(folder.glob("*.txt"))} if folder.is_dir() else {}


def check_repo(root: Path) -> list[str]:
    extras: dict[str, list[str]] = load_project(root).get("optional-dependencies", {})
    locks = lock_files(root)
    errors: list[str] = []
    for extra, requirements in sorted(extras.items()):
        path = locks.get(extra)
        if path is None:
            errors.append(f"extra [{extra}] has no lock: constraints/{extra}.txt")
            continue
        errors.extend(check_file(path))
        pinned = {req.name for req in parse_requirements(path.read_text(encoding="utf-8"))}
        for requirement in requirements:
            match = NAME_RE.match(requirement)
            name = normalize_name(match.group(1)) if match else requirement
            if name not in pinned:
                errors.append(f"{path.name}: direct requirement of [{extra}] not locked: {name}")
    for orphan in sorted(set(locks) - set(extras)):
        errors.append(f"constraints/{orphan}.txt does not match any extra in pyproject.toml")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args(argv)
    errors = check_repo(Path(args.root))
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        print(f"{len(errors)} problem(s) in the extras locks", file=sys.stderr)
        return 1
    print("constraints OK: every extra is hash-pinned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
