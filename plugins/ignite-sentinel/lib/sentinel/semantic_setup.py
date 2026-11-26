"""IMP-425 (H27 inc 7b): `/setup --semantic-memory`, the verified model install.

It runs only when asked, by the person or by their agent at their request in chat; it is
never automatic and never an MCP tool. It fetches a pinned embedding model (through
`setup_download.py`, the only network code, run as a subprocess) or copies it
from `--offline-from DIR`, checks every file's sha256 and size against
`templates/semantic_models.json`, and only then activates it: the folder is
moved into place (the previous install is set aside and comes back on any failure),
`<home>/semantic.json` is written with the pinned revision, and every workspace is
reindexed under its IMP-299 lock. Any mismatch or failure deletes the staging folder
and leaves the previous install, if any, untouched. `semantic_status` rehashes
without network.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from . import memory
from .core import io as core_io
from .core.paths import is_valid_project_id
from .errors import WorkspaceBusy
from .resources import package_resource, read_package_json

CONFIG_FILE = "semantic.json"
PIP_COMMAND = "python -m pip install -c constraints/memory-semantic.txt -e .[memory-semantic]"

# fetch(url, dest, allowed_hosts, max_bytes)
Fetch = Callable[[str, Path, "list[str]", int], None]

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")


class SetupError(Exception):
    pass


def sentinel_home() -> Path:
    override = os.environ.get("SENTINEL_HOME")
    return Path(override) if override else Path.home() / ".ignite-sentinel"


def config_path(home: Path) -> Path:
    return home / CONFIG_FILE


def model_dir(home: Path, model: dict[str, Any]) -> Path:
    return home / "models" / model["id"] / model["revision"][:12]


def load_manifest() -> dict[str, Any]:
    return read_package_json("templates", "semantic_models.json")


def _hosts(manifest: dict[str, Any]) -> list[str]:
    # exact hosts, then ".suffix" entries (the downloader reads a leading dot as "subdomains of")
    return list(manifest.get("allowed_hosts", [])) + list(manifest.get("allowed_host_suffixes", []))


def _plain_name(value: Any, what: str) -> str:
    """A manifest value that becomes one path component: no separators, no `..`, not absolute."""
    if not isinstance(value, str) or not _NAME_RE.match(value) or ".." in value:
        raise SetupError(f"semantic_models.json: {what} {value!r} is not a plain file name")
    return value


def _model(manifest: dict[str, Any]) -> dict[str, Any]:
    default = manifest["default"]
    for model in manifest["models"]:
        if model["id"] == default:
            _plain_name(model["id"], "model id")
            if not isinstance(model.get("revision"), str) or not _REVISION_RE.match(model["revision"]):
                raise SetupError(f"semantic_models.json: revision {model.get('revision')!r} is not a 40-character commit")
            for entry in model["files"]:
                _plain_name(entry["name"], "file name")
            return model
    raise SetupError(f"semantic_models.json: default model {default} is not listed")


def subprocess_fetch(url: str, dest: Path, hosts: list[str], max_bytes: int) -> None:
    """Run the downloader as `python -I <script> ...` (argv list, no shell).

    From a .pyz `__file__` is inside the zip and no interpreter can open it, so the script is
    extracted from the package resources into a private temporary folder, run from there and
    removed afterwards.
    """
    arguments = [url, str(dest), str(max_bytes), *hosts]
    script = Path(__file__).with_name("setup_download.py")
    if script.is_file():
        subprocess.run([sys.executable, "-I", str(script), *arguments], check=True, timeout=3600)
        return
    scratch = Path(tempfile.mkdtemp(prefix="sentinel-setup-"))  # private (0700) on POSIX
    try:
        extracted = scratch / "setup_download.py"
        core_io.write_bytes(extracted, package_resource("setup_download.py").read_bytes(), root=scratch)
        subprocess.run([sys.executable, "-I", str(extracted), *arguments], check=True, timeout=3600)
    finally:
        _clear_dir(scratch, scratch)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:  # raw bytes: core.hashing folds CRLF, wrong for a model file
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_ok(path: Path, entry: dict[str, Any]) -> bool:
    try:
        return path.is_file() and path.stat().st_size == entry["size"] and _sha256(path) == entry["sha256"]
    except OSError:
        return False


def _clear_dir(path: Path, home: Path) -> None:
    if not path.exists():
        return
    for child in path.iterdir():
        core_io.remove(child, root=home)
    core_io.remove(path, root=home)


def _pip_hint(root: Path | None) -> str:
    """The install command for this kind of install (clone, plugin, wheel or .pyz), as /doctor words it."""
    from . import doctor

    detail = f"model2vec is not installed; run {PIP_COMMAND}, then retry."
    if not doctor.is_framework_root((Path(root) if root is not None else Path.cwd()).resolve()):
        detail = doctor.runtime_hint({"detail": detail})["detail"]
    return detail


def install_semantic_memory(
    *,
    home: Path | None = None,
    offline_from: Path | None = None,
    fetch: Fetch = subprocess_fetch,
    manifest: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    home = Path(home) if home is not None else sentinel_home()
    manifest = manifest if manifest is not None else load_manifest()
    model = _model(manifest)
    if model["embedder"] == "model2vec" and importlib.util.find_spec("model2vec") is None:
        raise SetupError(_pip_hint(root))

    staging = core_io.confine(home / "models" / f".staging-{model['id']}", home)
    destination = core_io.confine(model_dir(home, model), home)
    backup = destination.with_name(destination.name + ".previous")
    moved_aside = placed = False
    try:
        _clear_dir(staging, home)
        staging.mkdir(parents=True, exist_ok=True)
        for entry in model["files"]:
            name = entry["name"]
            target = staging / name
            if offline_from is not None:
                source = Path(offline_from) / name
                if not source.is_file():
                    raise SetupError(f"{name} missing in {offline_from}; nothing was activated")
                _check_file(source, entry, name)  # size first, then a streamed hash: nothing is read whole
                core_io.copy_file(source, target, root=home)
            else:
                url = model["url_template"].format(repo=model["repo"], revision=model["revision"], name=name)
                try:
                    fetch(url, target, _hosts(manifest), entry["size"])
                except (OSError, subprocess.SubprocessError) as exc:
                    raise SetupError(f"{name}: download failed ({exc}); nothing was activated") from exc
            if not target.is_file():
                raise SetupError(f"{name} missing in {staging}; nothing was activated")
            _check_file(target, entry, name)

        # Activation: the previous install is moved aside, and comes back if anything below fails.
        destination.parent.mkdir(parents=True, exist_ok=True)
        _clear_dir(backup, home)
        if destination.exists():
            os.replace(destination, backup)
            moved_aside = True
        os.replace(staging, destination)
        placed = True
        core_io.write_json(
            config_path(home),
            {
                "model_id": model["id"],
                "embedder": model["embedder"],
                "revision": model["revision"],
                "path": str(destination),
                "files": {entry["name"]: entry["sha256"] for entry in model["files"]},
            },
            root=home,
        )
    except BaseException:
        if placed:
            _clear_dir(destination, home)
        if moved_aside:
            os.replace(backup, destination)
        raise
    finally:
        _clear_dir(staging, home)
    _clear_dir(backup, home)
    reindexed, warnings = _reindex_all(root)
    result = {"status": "installed", "path": str(destination), "revision": model["revision"], "reindexed": reindexed}
    if warnings:
        result["warnings"] = warnings
    return result


def _check_file(path: Path, entry: dict[str, Any], name: str) -> None:
    size = path.stat().st_size
    if size != entry["size"]:
        raise SetupError(f"{name}: size mismatch (expected {entry['size']}, got {size}); nothing was activated")
    got = _sha256(path)
    if got != entry["sha256"]:
        raise SetupError(f"{name}: sha256 mismatch (expected {entry['sha256']}, got {got}); nothing was activated")


def _reindex_all(root: Path | None) -> tuple[list[str], list[str]]:
    """Every workspace, walked as dashboard.py walks them, with a full rebuild."""
    root_path = (Path(root) if root is not None else Path.cwd()).resolve()
    workspaces = root_path / "workspaces"
    if not workspaces.is_dir():
        return [], []
    done: list[str] = []
    warnings: list[str] = []
    from .core.lock import command_scope

    old_cwd = Path.cwd()
    os.chdir(root_path)
    try:
        for candidate in sorted(workspaces.iterdir(), key=lambda item: item.name.lower()):
            if candidate.name == "_template" or not candidate.is_dir() or not (candidate / "state.json").exists():
                continue
            if not is_valid_project_id(candidate.name):
                continue
            try:
                # IMP-299: one command at a time per workspace; /setup has no project, so it locks each one here.
                with command_scope("setup", candidate):
                    memory.reindex_workspace(candidate.name, full=True)
            except WorkspaceBusy as exc:
                warnings.append(
                    f"{candidate.name}: skipped, the workspace is busy ({exc}); "
                    f"retry with: sentinel /reindex {candidate.name} --full"
                )
                continue
            except Exception as exc:  # noqa: BLE001 - the model is already active; report, do not crash
                warnings.append(
                    f"{candidate.name}: reindex failed ({exc.__class__.__name__}: {exc}); "
                    f"retry with: sentinel /reindex {candidate.name} --full"
                )
                continue
            done.append(candidate.name)
    finally:
        os.chdir(old_cwd)
    return done, warnings


def semantic_status(*, home: Path | None = None, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    home = Path(home) if home is not None else sentinel_home()
    manifest = manifest if manifest is not None else load_manifest()
    model = _model(manifest)
    destination = model_dir(home, model)
    if not config_path(home).is_file() or not destination.is_dir():
        return {"status": "missing", "path": str(destination), "files": []}
    files = [{"name": entry["name"], "ok": _file_ok(destination / entry["name"], entry)} for entry in model["files"]]
    status = "installed" if all(item["ok"] for item in files) else "mismatch"
    return {"status": status, "path": str(destination), "files": files}


def configured_model(home: Path | None = None, manifest: dict[str, Any] | None = None) -> tuple[str | None, str]:
    """The installed model the memory should load: (path, "current"), (None, "none") or (None, "stale").

    `semantic.json` counts only when it names the manifest's pinned model and revision, at the
    folder `/setup` puts them in. A config left by an older Sentinel (another pinned revision),
    a hand edit or a vanished folder is "stale": ignored, and /doctor says to run /setup again.
    """
    try:
        home = Path(home) if home is not None else sentinel_home()
        path = config_path(home)
        if not path.is_file():
            return None, "none"
        data = memory.read_json(path, {})
        model = _model(manifest if manifest is not None else load_manifest())
        destination = model_dir(home, model)
        current = (
            isinstance(data, dict)
            and data.get("model_id") == model["id"]
            and data.get("revision") == model["revision"]
            and data.get("path") == str(destination)
            and destination.is_dir()
        )
        return (str(destination), "current") if current else (None, "stale")
    except Exception:  # noqa: BLE001 - a broken config must never break memory detection
        return None, "stale"
