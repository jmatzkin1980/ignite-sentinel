"""Versioning and release checks (IMP-282).

    python tools/release.py check [--tag vX.Y.Z] [--require-tagged]
    python tools/release.py notes X.Y.Z
    python tools/release.py zip [--out dist]

``check``: one version everywhere, ``pyproject.toml`` (the source),
``sentinel/__init__.py`` and every ``plugins/*/.claude-plugin/plugin.json``.
With ``--tag`` the tag must be ``v`` + that version (a tag without a bump fails)
and CHANGELOG must have a dated ``## [X.Y.Z]`` section. With
``--require-tagged`` (``main``) the version must already have its ``vX.Y.Z``
tag (a bump without a tag fails); tags come from ``git tag``.

``notes``: prints the CHANGELOG section of a version (release notes).

``zip``: one reproducible ``<plugin>-vX.Y.Z.zip`` per generated plugin, with the
plugin one folder down, plus ``SHA256SUMS``. That is the input of an ``archive``
plugin source (``url`` + ``sha256``), which installs without git.

Stdlib only. Exit code 1 lists every problem.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = "pyproject.toml"
PACKAGE_INIT = "sentinel/__init__.py"
PLUGINS_DIR = "plugins"
CHANGELOG = "CHANGELOG.md"
TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")
ZIP_EPOCH_FLOOR = 315_532_800  # 1980-01-01, the earliest time a zip entry can carry


def _pyproject_version(root: Path) -> str:
    text = (root / PYPROJECT).read_text(encoding="utf-8")
    project = re.search(r"^\[project\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    match = re.search(r'^version\s*=\s*"([^"]+)"', project.group(1) if project else "", re.M)
    return match.group(1) if match else ""


def _package_version(root: Path) -> str:
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', (root / PACKAGE_INIT).read_text(encoding="utf-8"), re.M)
    return match.group(1) if match else ""


def _plugin_manifests(root: Path) -> list[Path]:
    return sorted((root / PLUGINS_DIR).glob("*/.claude-plugin/plugin.json"))


def version_sources(root: Path) -> dict[str, str]:
    """Every place that states the version, keyed by repo-relative path."""
    versions = {PYPROJECT: _pyproject_version(root), PACKAGE_INIT: _package_version(root)}
    for manifest in _plugin_manifests(root):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        versions[manifest.relative_to(root).as_posix()] = str(data.get("version", ""))
    return versions


def changelog_section(root: Path, version: str) -> str | None:
    """Body of the dated `## [version] — YYYY-MM-DD` section, or None."""
    text = (root / CHANGELOG).read_text(encoding="utf-8")
    heading = re.compile(rf"^## \[{re.escape(version)}\] [—-] \d{{4}}-\d{{2}}-\d{{2}}\s*$", re.M)
    match = heading.search(text)
    if not match:
        return None
    rest = text[match.end():]
    following = re.search(r"^## \[", rest, re.M)
    return (rest[: following.start()] if following else rest).strip() + "\n"


def git_tags(root: Path) -> list[str]:
    result = subprocess.run(["git", "tag", "--list", "v*"], cwd=root, capture_output=True, text=True, check=True)
    return result.stdout.split()


def check(root: Path, *, tag: str | None = None, tags: list[str] | None = None, require_tagged: bool = False) -> list[str]:
    issues: list[str] = []
    versions = version_sources(root)
    version = versions[PYPROJECT]
    if not version:
        return [f"{PYPROJECT}: no [project] version"]
    for source, found in versions.items():
        if found != version:
            issues.append(f"{source}: version {found or '(none)'} differs from {PYPROJECT} {version}")
    if tag is not None:
        match = TAG_RE.match(tag)
        if not match:
            issues.append(f"tag {tag}: release tags are vX.Y.Z")
        elif match.group(1) != version:
            issues.append(f"tag {tag}: tag without a bump, {PYPROJECT} says {version}")
        if changelog_section(root, version) is None:
            issues.append(f"{CHANGELOG}: no dated section '## [{version}] — YYYY-MM-DD'")
    if require_tagged:
        known = tags if tags is not None else git_tags(root)
        if f"v{version}" not in known:
            issues.append(f"version {version}: bump without a tag, push tag v{version} on this commit")
    return issues


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def release_plan(root: Path) -> dict:
    """What `main` needs so the current version is tagged (no bump stays untagged).

    The tag goes on the first-parent commit that introduced the version in
    `pyproject.toml` (the bump's merge commit). It is published as a release only
    when that commit is HEAD; an older commit (catching up a version released
    before this workflow existed) is only tagged.
    """
    version = _pyproject_version(root)
    tag = f"v{version}"
    plan = {"version": version, "tag": tag, "commit": "", "create_tag": False, "publish": False, "issues": []}
    plan["issues"] = check(root)
    if plan["issues"] or tag in git_tags(root):
        return plan
    if changelog_section(root, version) is None:
        plan["issues"].append(f"{CHANGELOG}: version {version} is untagged and has no dated section '## [{version}] — YYYY-MM-DD'")
        return plan
    found = _git(root, "log", "--first-parent", "--format=%H", f'-Sversion = "{version}"', "--", PYPROJECT).split()
    if not found:
        plan["issues"].append(f"{PYPROJECT}: no commit on the first-parent history introduces version {version}")
        return plan
    plan["commit"] = found[-1]
    plan["create_tag"] = True
    plan["publish"] = plan["commit"] == _git(root, "rev-parse", "HEAD")
    return plan


def format_outputs(plan: dict) -> list[str]:
    """`key=value` lines for $GITHUB_OUTPUT."""
    return [
        f"{key}={str(value).lower() if isinstance(value, bool) else value}"
        for key, value in plan.items()
        if key != "issues"
    ]


def _archive_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    return data if b"\0" in data else data.replace(b"\r\n", b"\n")


def build_archives(root: Path, out: Path, *, epoch: int | None = None) -> list[Path]:
    """Write `<plugin>-v<version>.zip` per plugin and SHA256SUMS into `out`."""
    version = _pyproject_version(root)
    if epoch is None:
        epoch = int(os.environ.get("SOURCE_DATE_EPOCH", ZIP_EPOCH_FLOOR))
    stamp = time.gmtime(max(epoch, ZIP_EPOCH_FLOOR))[:6]
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for manifest in _plugin_manifests(root):
        plugin = manifest.parents[1]
        target = out / f"{plugin.name}-v{version}.zip"
        files = sorted(
            item for item in plugin.rglob("*")
            if item.is_file() and "__pycache__" not in item.parts and item.suffix != ".pyc"
        )
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in files:
                info = zipfile.ZipInfo(f"{plugin.name}/{item.relative_to(plugin).as_posix()}", date_time=stamp)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, _archive_bytes(item))
        written.append(target)
    sums = out / "SHA256SUMS"
    sums.write_text(
        "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in written),
        encoding="utf-8",
        newline="\n",
    )
    return [*written, sums]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    check_cmd = commands.add_parser("check")
    check_cmd.add_argument("--tag")
    check_cmd.add_argument("--require-tagged", action="store_true")
    notes_cmd = commands.add_parser("notes")
    notes_cmd.add_argument("version")
    plan_cmd = commands.add_parser("plan")
    plan_cmd.add_argument("--github-output", type=Path, help="append key=value lines here ($GITHUB_OUTPUT)")
    zip_cmd = commands.add_parser("zip")
    zip_cmd.add_argument("--out", type=Path, default=Path("dist"))
    args = parser.parse_args(argv)
    root = args.root.resolve()

    if args.command == "check":
        issues = check(root, tag=args.tag, require_tagged=args.require_tagged)
        for issue in issues:
            print(f"release check: {issue}", file=sys.stderr)
        if not issues:
            print(f"release check: OK ({_pyproject_version(root)})")
        return 1 if issues else 0
    if args.command == "plan":
        plan = release_plan(root)
        for issue in plan["issues"]:
            print(f"release plan: {issue}", file=sys.stderr)
        lines = format_outputs(plan)
        print("\n".join(lines))
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as handle:
                handle.write("".join(f"{line}\n" for line in lines))
        return 1 if plan["issues"] else 0
    if args.command == "notes":
        section = changelog_section(root, args.version.removeprefix("v"))
        if section is None:
            print(f"{CHANGELOG}: no dated section for {args.version}", file=sys.stderr)
            return 1
        sys.stdout.write(section)
        return 0
    for path in build_archives(root, args.out):
        print(path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
