"""IMP-425 (H27 inc 7b): `/setup --semantic-memory`, the verified model install.

The person runs this once. It fetches a pinned embedding model (through
`setup_download.py`, the only network code, run as a subprocess) or copies it
from `--offline-from DIR`, checks every file's sha256 and size against
`templates/semantic_models.json`, and only then activates it: the folder is
moved into place, `<home>/semantic.json` is written, and every workspace is
reindexed. Any mismatch deletes the staging folder and leaves the previous
install, if any, untouched. `semantic_status` rehashes without network.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from . import memory
from .core import io as core_io
from .core.paths import is_valid_project_id
from .resources import read_package_json

CONFIG_FILE = "semantic.json"
PIP_COMMAND = "python -m pip install -c constraints/memory-semantic.txt -e .[memory-semantic]"

Fetch = Callable[[str, Path, "list[str]"], None]


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


def _model(manifest: dict[str, Any]) -> dict[str, Any]:
    default = manifest["default"]
    for model in manifest["models"]:
        if model["id"] == default:
            return model
    raise SetupError(f"semantic_models.json: default model {default} is not listed")


def subprocess_fetch(url: str, dest: Path, hosts: list[str]) -> None:
    subprocess.run(
        [sys.executable, "-I", str(Path(__file__).with_name("setup_download.py")), url, str(dest), *hosts],
        check=True,
        timeout=3600,
    )


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
        raise SetupError(f"model2vec is not installed; run {PIP_COMMAND} and retry")

    staging = home / "models" / f".staging-{model['id']}"
    _clear_dir(staging, home)
    staging.mkdir(parents=True, exist_ok=True)
    try:
        for entry in model["files"]:
            name = entry["name"]
            target = staging / name
            if offline_from is not None:
                source = Path(offline_from) / name
                if not source.is_file():
                    raise SetupError(f"{name} missing in {offline_from}; nothing was activated")
                core_io.copy_file(source, target, root=home)
            else:
                url = model["url_template"].format(repo=model["repo"], revision=model["revision"], name=name)
                try:
                    fetch(url, target, _hosts(manifest))
                except (OSError, subprocess.SubprocessError) as exc:
                    raise SetupError(f"{name}: download failed ({exc}); nothing was activated") from exc
            if not target.is_file():
                raise SetupError(f"{name} missing in {staging}; nothing was activated")
            got = _sha256(target)
            size = target.stat().st_size
            if got != entry["sha256"]:
                raise SetupError(f"{name}: sha256 mismatch (expected {entry['sha256']}, got {got}); nothing was activated")
            if size != entry["size"]:
                raise SetupError(f"{name}: size mismatch (expected {entry['size']}, got {size}); nothing was activated")
    except BaseException:
        _clear_dir(staging, home)
        raise

    destination = model_dir(home, model)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _clear_dir(destination, home)
    os.replace(staging, destination)
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
    reindexed = _reindex_all(root)
    return {"status": "installed", "path": str(destination), "revision": model["revision"], "reindexed": reindexed}


def _reindex_all(root: Path | None) -> list[str]:
    """Every workspace, walked as dashboard.py walks them, with a full rebuild."""
    root_path = (Path(root) if root is not None else Path.cwd()).resolve()
    workspaces = root_path / "workspaces"
    if not workspaces.is_dir():
        return []
    done: list[str] = []
    old_cwd = Path.cwd()
    os.chdir(root_path)
    try:
        for candidate in sorted(workspaces.iterdir(), key=lambda item: item.name.lower()):
            if candidate.name == "_template" or not candidate.is_dir() or not (candidate / "state.json").exists():
                continue
            if not is_valid_project_id(candidate.name):
                continue
            memory.reindex_workspace(candidate.name, full=True)
            done.append(candidate.name)
    finally:
        os.chdir(old_cwd)
    return done


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
