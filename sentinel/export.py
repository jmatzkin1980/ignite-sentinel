from __future__ import annotations

import json
import shutil
from pathlib import Path

from .blocks import markdown_to_blocks
from .workspace import update_state, workspace_path


def export_artifact(project_id: str, artifact: str, fmt: str = "md", domain: str | None = None) -> dict[str, str]:
    fmt = fmt.lower()
    base = workspace_path(project_id)
    source = artifact_source(base, artifact, domain)
    if not source.exists():
        raise RuntimeError(f"Export source not found: {source}")
    if fmt == "mdx":
        return export_mdx(project_id, artifact, source)
    if fmt != "md":
        raise RuntimeError("Unsupported export format. Use md or mdx.")
    export_dir = base / "08_context_packs" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / source.name
    shutil.copyfile(source, target)
    update_state(project_id, last_export=str(target.as_posix()))
    return {
        "project_id": project_id,
        "artifact": artifact,
        "format": "md",
        "source": str(source.as_posix()),
        "path": str(target.as_posix()),
    }


def export_mdx(project_id: str, artifact: str, source: Path) -> dict[str, str]:
    artifact = artifact.lower()
    if artifact != "prd":
        raise RuntimeError("MDX export is currently supported only for --artifact prd.")
    text = source.read_text(encoding="utf-8")
    block_model = markdown_to_blocks(text, artifact=artifact)
    export_dir = workspace_path(project_id) / "08_context_packs" / "exports" / f"{artifact}-mdx"
    export_dir.mkdir(parents=True, exist_ok=True)
    mdx_path = export_dir / "index.mdx"
    blocks_path = export_dir / "blocks.json"
    readme_path = export_dir / "README.md"
    blocks_path.write_text(json.dumps(block_model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mdx_path.write_text(render_mdx(project_id, artifact, source, block_model), encoding="utf-8")
    readme_path.write_text(render_mdx_readme(project_id, artifact, source), encoding="utf-8")
    update_state(project_id, last_export=str(mdx_path.as_posix()))
    return {
        "project_id": project_id,
        "artifact": artifact,
        "format": "mdx",
        "source": str(source.as_posix()),
        "path": str(export_dir.as_posix()),
        "mdx": str(mdx_path.as_posix()),
        "blocks": str(blocks_path.as_posix()),
        "readme": str(readme_path.as_posix()),
    }


def render_mdx(project_id: str, artifact: str, source: Path, block_model: dict) -> str:
    metadata = {
        "project_id": project_id,
        "artifact": artifact,
        "source": source.as_posix(),
        "source_sha256": block_model["source_sha256"],
        "block_catalog": block_model["catalog"],
        "roundtrip": block_model["roundtrip"],
    }
    lines = [
        "export const sentinelExport = ",
        json.dumps(metadata, ensure_ascii=False, indent=2),
        ";",
        "",
        "{/*",
        "Ignite Sentinel derived MDX export.",
        "Markdown remains the source of truth; this file is an optional offline render target.",
        "Do not edit this export as project authority. Regenerate it with /export.",
        "*/}",
        "",
    ]
    for block in block_model.get("blocks", []):
        lines.extend(
            [
                "{/*",
                "block: {id} type={type} lines={start}-{end} path={path}".format(
                    id=block.get("id", ""),
                    type=block.get("type", ""),
                    start=block.get("line_start", ""),
                    end=block.get("line_end", ""),
                    path=block.get("section_path", ""),
                ),
                "*/}",
                str(block.get("markdown", "")),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_mdx_readme(project_id: str, artifact: str, source: Path) -> str:
    return f"""# Ignite Sentinel MDX Export

Project: `{project_id}`
Artifact: `{artifact}`
Source of truth: `{source.as_posix()}`

This folder is a derived local-files export for teams that already have an offline MDX renderer.
It does not install or require a renderer, does not call a hosted Plan MCP, and does not change the governed Markdown contract.

Files:

- `index.mdx`: renderable MDX mirror with block comments and export metadata.
- `blocks.json`: derived block interlingua used to build the MDX.
- `README.md`: this note.

Regenerate with:

```powershell
python -m sentinel /export {project_id} --artifact {artifact} --format mdx
```
"""


def artifact_source(base: Path, artifact: str, domain: str | None) -> Path:
    artifact = artifact.lower()
    if artifact == "gaps":
        return base / "01_discovery" / "gaps.md"
    if artifact == "brief":
        return base / "02_requirements" / "project-brief.md"
    if artifact == "prd":
        return base / "03_specs" / "prd.md"
    if artifact == "context-request":
        if not domain:
            raise RuntimeError("--domain is required when exporting context-request.")
        return base / "08_context_packs" / "requests" / f"{domain.lower()}_context_request.md"
    raise RuntimeError(f"Unsupported export artifact: {artifact}")
