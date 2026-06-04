from __future__ import annotations

import shutil
from pathlib import Path

from .workspace import update_state, workspace_path


def export_artifact(project_id: str, artifact: str, fmt: str = "md", domain: str | None = None) -> dict[str, str]:
    if fmt != "md":
        raise RuntimeError("Only markdown export is supported for now.")
    base = workspace_path(project_id)
    source = artifact_source(base, artifact, domain)
    if not source.exists():
        raise RuntimeError(f"Export source not found: {source}")
    export_dir = base / "08_context_packs" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / source.name
    shutil.copyfile(source, target)
    update_state(project_id, last_export=str(target.as_posix()))
    return {"project_id": project_id, "artifact": artifact, "source": str(source.as_posix()), "path": str(target.as_posix())}


def artifact_source(base: Path, artifact: str, domain: str | None) -> Path:
    artifact = artifact.lower()
    if artifact == "gaps":
        return base / "01_discovery" / "gaps.md"
    if artifact == "brief":
        return base / "02_requirements" / "project-brief.md"
    if artifact == "context-request":
        if not domain:
            raise RuntimeError("--domain is required when exporting context-request.")
        return base / "08_context_packs" / "requests" / f"{domain.lower()}_context_request.md"
    raise RuntimeError(f"Unsupported export artifact: {artifact}")

