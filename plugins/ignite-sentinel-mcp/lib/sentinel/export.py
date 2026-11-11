from __future__ import annotations

import json
import shutil
from pathlib import Path

from .blocks import markdown_to_blocks
from .core.io import copy_file, write_json, write_text
from .secrets_scan import assert_no_leaks
from .workspace import update_state, workspace_path


def _language(project_id: str) -> str:
    from .workspace import read_state

    state = read_state(project_id, {})
    return "es" if state.get("project_language") == "es" else "en"


def export_artifact(project_id: str, artifact: str, fmt: str = "md", domain: str | None = None,
                    final: bool = False) -> dict[str, str]:
    from .deliverables import gate

    fmt = fmt.lower()
    base = workspace_path(project_id)
    source = artifact_source(base, artifact, domain)
    if not source.exists():
        raise RuntimeError(f"Export source not found: {source}")
    # IMP-272: a deliverable has zero pending marks or says it is a draft
    verdict = gate(source.read_text(encoding="utf-8"), artifact=artifact.lower(), fmt=fmt, final=final)
    result = _export(project_id, artifact, fmt, source, verdict)
    return {**result, **verdict}


def _export(project_id: str, artifact: str, fmt: str, source: Path, verdict: dict) -> dict[str, str]:
    from .deliverables import with_banner

    base = workspace_path(project_id)
    if fmt == "mdx":
        return export_mdx(project_id, artifact, source, verdict)
    if fmt == "interview":
        return export_interview(project_id, artifact)
    if fmt == "faq":
        return export_faq(project_id, artifact)
    if fmt != "md":
        raise RuntimeError("Unsupported export format. Use md, mdx, interview, or faq.")
    export_dir = base / "08_context_packs" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / source.name
    assert_no_leaks(project_id, source.read_text(encoding="utf-8"), base, f"export {artifact}")
    if verdict["deliverable"] == "draft":
        write_text(target, with_banner(source.read_text(encoding="utf-8"), int(verdict["pending_marks"]), _language(project_id)))
    else:
        copy_file(source, target)
    update_state(project_id, last_export=str(target.as_posix()))
    return {
        "project_id": project_id,
        "artifact": artifact,
        "format": "md",
        "source": str(source.as_posix()),
        "path": str(target.as_posix()),
    }


def export_interview(project_id: str, artifact: str) -> dict[str, str]:
    if artifact.lower() != "gaps":
        raise RuntimeError("Interview export is currently supported only for --artifact gaps.")
    from .discovery import build_interview_script

    script = build_interview_script(project_id)
    export_dir = workspace_path(project_id) / "08_context_packs" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / "gaps-interview.md"
    assert_no_leaks(project_id, script, workspace_path(project_id), "interview export")
    write_text(target, script)
    update_state(project_id, last_export=str(target.as_posix()))
    return {
        "project_id": project_id,
        "artifact": "gaps",
        "format": "interview",
        "source": str((workspace_path(project_id) / "01_discovery" / "gaps.md").as_posix()),
        "path": str(target.as_posix()),
    }


def export_faq(project_id: str, artifact: str) -> dict[str, str]:
    if artifact.lower() != "gaps":
        raise RuntimeError("FAQ export is currently supported only for --artifact gaps.")
    from .discovery import build_faq

    faq = build_faq(project_id)
    export_dir = workspace_path(project_id) / "08_context_packs" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / "gaps-faq.md"
    assert_no_leaks(project_id, faq, workspace_path(project_id), "FAQ export")
    write_text(target, faq)
    update_state(project_id, last_export=str(target.as_posix()))
    return {
        "project_id": project_id,
        "artifact": "gaps",
        "format": "faq",
        "source": str((workspace_path(project_id) / "01_discovery" / "decisions.md").as_posix()),
        "path": str(target.as_posix()),
    }


def export_mdx(project_id: str, artifact: str, source: Path, verdict: dict | None = None) -> dict[str, str]:
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
    mdx_text = render_mdx(project_id, artifact, source, block_model, verdict or {})
    assert_no_leaks(project_id, mdx_text, workspace_path(project_id), "MDX export")
    write_json(blocks_path, block_model)
    write_text(mdx_path, mdx_text)
    write_text(readme_path, render_mdx_readme(project_id, artifact, source))
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


def render_mdx(project_id: str, artifact: str, source: Path, block_model: dict, verdict: dict | None = None) -> str:
    metadata = {
        "project_id": project_id,
        "artifact": artifact,
        "source": source.as_posix(),
        "source_sha256": block_model["source_sha256"],
        "block_catalog": block_model["catalog"],
        "roundtrip": block_model["roundtrip"],
    }
    if verdict and verdict.get("deliverable") == "draft":  # IMP-272: a draft says so
        metadata["draft"] = True
        metadata["pending_marks"] = verdict["pending_marks"]
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
