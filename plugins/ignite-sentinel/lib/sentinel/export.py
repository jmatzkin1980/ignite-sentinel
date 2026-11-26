from __future__ import annotations

from .errors import InputError  # IMP-302: typed errors

import json
import shutil
from pathlib import Path

from .blocks import markdown_to_blocks
from .core.io import copy_file, write_json, write_text
from .core.paths import workspace_citation, workspace_relative  # IMP-300: `last_export` is workspace-relative
from .secrets_scan import assert_no_leaks
from .changes import change_gaps_path
from .workspace import update_state, workspace_path


def _language(project_id: str, change_id: str | None = None) -> str:
    if change_id:  # IMP-386: a change speaks its own language, fixed at ingest, not the project's
        from .changes import change_language, get_change

        return "es" if change_language(project_id, get_change(project_id, change_id)) == "es" else "en"
    from .workspace import read_state

    state = read_state(project_id, {})
    return "es" if state.get("project_language") == "es" else "en"


def export_artifact(project_id: str, artifact: str, fmt: str = "md", domain: str | None = None,
                    final: bool = False, change_id: str | None = None) -> dict[str, str]:
    from .deliverables import gate
    from .pending_marks import change_extraction_pending, compile_report_for

    fmt = fmt.lower()
    base = workspace_path(project_id)
    if change_id:
        from .changes import check_change_deliverable

        check_change_deliverable(project_id, "export", artifact, change_id, fmt)
        if fmt not in ("md", "interview", "faq"):
            raise InputError(f"/export --change admite los formatos md, interview y faq, no {fmt}.")
        if artifact.lower() in ("borde", "decisiones"):  # IMP-412: rebuilt from what is registered
            from .review_views import write_review_view

            write_review_view(project_id, change_id, artifact.lower())
    else:
        from .changes import refuse_change_only_deliverable

        refuse_change_only_deliverable(project_id, "export", artifact)
    source = artifact_source(base, artifact, domain, change_id)
    if not source.exists():
        raise InputError(f"Export source not found: {source}")
    # IMP-272: a deliverable has zero pending marks or says it is a draft
    # IMP-334: counted as /validate counts them (the brief v2 compile report when there is one)
    extraction = change_extraction_pending(base, change_id) if change_id and artifact.lower() == "brief" else []
    verdict = gate(source.read_text(encoding="utf-8"), artifact=artifact.lower(), fmt=fmt, final=final,
                   report=compile_report_for(source), extraction=extraction, language=_language(project_id, change_id),
                   project_id=project_id, change_id=change_id or "")
    if final and change_id and artifact.lower() == "brief" and fmt == "md":
        _check_final_change(project_id, change_id)  # after the marks and the pending extraction, which say their own thing
    result = _export(project_id, artifact, fmt, source, verdict, change_id, final)
    if final and change_id and artifact.lower() == "brief" and fmt == "md":
        _record_final_export(project_id, change_id, result["path"])
    return {**result, **verdict}


def _check_final_change(project_id: str, change_id: str) -> None:
    """IMP-406 I6/I7: `--final` seals a brief that does not contradict its own seal.

    It refuses while the change verdict is NOT_READY, and while the exported text (the project brief v2 format,
    not only the internal brief) still carries pending marks."""
    from .changes import deferred_gaps
    from .compilers.change_deliverable import render_change_deliverable_parts
    from .deliverables import DeliverableNotReady
    from .pending_marks import count_pending_marks
    from .readiness_verdict import build_change_verdict

    es = _language(project_id, change_id) == "es"
    from .consolidation_control import consolidation_control

    pending = consolidation_control(project_id, change_id)["pending"]  # IMP-414: every element resolved first
    if pending:
        shown = ", ".join(pending[:10]) + (f" (+{len(pending) - 10})" if len(pending) > 10 else "")
        command = f"/extract {project_id} --change {change_id} --consolidate PATH"
        sheet = f"01_discovery/{change_id}/consolidation_control.md"
        if es:
            message = (f"/export --final rechazado: {len(pending)} elemento(s) de {change_id} sin consolidar ({shown}). "
                       f"Proponé el texto con {command} (planilla: {sheet}), confirmá cada uno con --confirm-replacement ID "
                       "o marcá --keep-text ID --gap GAP --reason TEXTO.")
        else:
            message = (f"/export --final refused: {len(pending)} element(s) of {change_id} not consolidated ({shown}). "
                       f"Propose the text with {command} (worksheet: {sheet}), confirm each one with --confirm-replacement ID "
                       "or mark --keep-text ID --gap GAP --reason TEXT.")
        raise DeliverableNotReady(message, command)
    found = build_change_verdict(project_id, change_id)
    if found["verdict"] == "NOT_READY":
        held = [d for d in deferred_gaps(project_id, change_id) if d["impact"] == "construccion"]
        first = next((d for d in held if not d["classed"]), None) or (held[0] if held else None)
        reasons = "; ".join(found["blockers"])
        if held:
            command = (f"/gaps {project_id} --change {change_id} --id {first['id']} "
                       "--impact construccion|operativo --reason TEXTO")
            how_es = f"Respondelos o clasificalos con {command}; /export sin --final deja un borrador."
            how_en = f"Answer them or class them with {command}; /export without --final leaves a draft."
        else:
            command = f"/next {project_id} --change {change_id}"
            how_es = f"Resolvé lo que dice el veredicto ({command} dice por dónde); /export sin --final deja un borrador."
            how_en = f"Resolve what the verdict says ({command} says where to start); /export without --final leaves a draft."
        if es:
            message = (f"/export --final rechazado: el veredicto de {change_id} es NOT_READY ({reasons}). "
                       + (f"Pendientes que frenan la construcción: {', '.join(d['id'] for d in held)}. " if held else "")
                       + how_es)
        else:
            message = (f"/export --final refused: the verdict of {change_id} is NOT_READY ({reasons}). "
                       + (f"Items that hold back the build: {', '.join(d['id'] for d in held)}. " if held else "")
                       + how_en)
        raise DeliverableNotReady(message, command)
    text, report = render_change_deliverable_parts(project_id, change_id, True)
    marks = count_pending_marks(text, report)
    if not marks.blocking:
        # IMP-414: the final body leaves the EARS rows out, so a confirmed statement that says «a definir»
        # would vanish from the sealed text; the working text still carries it and must not be sealed either.
        working, working_report = render_change_deliverable_parts(project_id, change_id, False)
        marks = count_pending_marks(working, working_report)
    if marks.blocking:
        raise DeliverableNotReady(
            f"/export --final refused: {marks.blocking} pending marks remain in the brief that would be exported "
            "(a confirmed statement or answer that says «a definir»/TBD is one). Close them (or export without --final "
            "to get a marked draft).", f"/export {project_id} --artifact brief --change {change_id}")


def _record_final_export(project_id: str, change_id: str, path: str) -> dict[str, str]:
    """IMP-406: the milestone `export_final`: where the final export went and the hash of the brief it came from."""
    from .changes import list_changes
    from .compilers.change_deliverable import brief_sha, build_seal, seal_sha
    from .core.time import utc_now

    from .consolidation_control import consolidation_sha

    seal = build_seal(project_id, change_id, True, _language(project_id, change_id))
    recorded = {
        "path": workspace_relative(project_id, Path(path)),
        "at": utc_now(),
        "brief_sha": brief_sha(workspace_path(project_id), change_id),
        "verdict": seal["verdict"],
        "seal_sha": seal_sha(project_id, change_id),
        "consolidation_sha": consolidation_sha(project_id, change_id),
    }
    changes = {key: dict(value) for key, value in list_changes(project_id).items()}
    changes[change_id]["final_export"] = recorded
    update_state(project_id, changes=changes)
    return recorded


def _export(project_id: str, artifact: str, fmt: str, source: Path, verdict: dict,
            change_id: str | None = None, final: bool = False) -> dict[str, str]:
    from .deliverables import with_banner

    base = workspace_path(project_id)
    if fmt == "mdx":
        return export_mdx(project_id, artifact, source, verdict)
    if fmt == "interview":
        return export_interview(project_id, artifact, change_id)
    if fmt == "faq":
        return export_faq(project_id, artifact, change_id)
    if fmt != "md":
        raise InputError("Unsupported export format. Use md, mdx, interview, or faq.")
    export_dir = base / "08_context_packs" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / (f"{change_id}-{source.name}" if change_id else source.name)
    if change_id and artifact.lower() == "brief":
        # IMP-406: the change's deliverable is written by the project's brief v2 compiler, not copied from the working brief
        from .compilers.change_deliverable import render_change_deliverable

        text = render_change_deliverable(project_id, change_id, final)
        assert_no_leaks(project_id, text, base, f"export {artifact}")
        if verdict["deliverable"] == "draft":
            text = with_banner(text, int(verdict["pending_marks"]), _language(project_id, change_id),
                               list(verdict.get("extraction_pending") or []))
        write_text(target, text)
        update_state(project_id, last_export=workspace_relative(project_id, target))
        return {
            "project_id": project_id,
            "artifact": artifact,
            "format": "md",
            "source": str(source.as_posix()),
            "path": str(target.as_posix()),
        }
    assert_no_leaks(project_id, source.read_text(encoding="utf-8"), base, f"export {artifact}")
    if verdict["deliverable"] == "draft":
        write_text(target, with_banner(source.read_text(encoding="utf-8"), int(verdict["pending_marks"]), _language(project_id, change_id),
                                                         list(verdict.get("extraction_pending") or [])))
    else:
        copy_file(source, target)
    update_state(project_id, last_export=workspace_relative(project_id, target))
    return {
        "project_id": project_id,
        "artifact": artifact,
        "format": "md",
        "source": str(source.as_posix()),
        "path": str(target.as_posix()),
    }


def export_interview(project_id: str, artifact: str, change_id: str | None = None) -> dict[str, str]:
    if artifact.lower() != "gaps":
        raise InputError("Interview export is currently supported only for --artifact gaps.")
    from .discovery import build_interview_script

    script = build_interview_script(project_id, change_id=change_id)
    export_dir = workspace_path(project_id) / "08_context_packs" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / (f"{change_id}-gaps-interview.md" if change_id else "gaps-interview.md")
    assert_no_leaks(project_id, script, workspace_path(project_id), "interview export")
    write_text(target, script)
    update_state(project_id, last_export=workspace_relative(project_id, target))
    return {
        "project_id": project_id,
        "artifact": "gaps",
        "format": "interview",
        "source": str((change_gaps_path(workspace_path(project_id), change_id) if change_id
                       else workspace_path(project_id) / "01_discovery" / "gaps.md").as_posix()),
        "path": str(target.as_posix()),
    }


def export_faq(project_id: str, artifact: str, change_id: str | None = None) -> dict[str, str]:
    if artifact.lower() != "gaps":
        raise InputError("FAQ export is currently supported only for --artifact gaps.")
    from .discovery import build_faq

    if change_id:  # IMP-412: the questions of the change someone decided, with the answer and evidence as registered
        from .decision_memory import closed_decisions
        from .discovery.elicitation import render_faq

        answers = {item["id"]: {"statement": item["answer"], "source": item["evidence"]}
                   for item in closed_decisions(project_id, change_id)}
        faq = render_faq(project_id, answers, _language(project_id, change_id))
    else:
        faq = build_faq(project_id)
    export_dir = workspace_path(project_id) / "08_context_packs" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / (f"{change_id}-gaps-faq.md" if change_id else "gaps-faq.md")
    assert_no_leaks(project_id, faq, workspace_path(project_id), "FAQ export")
    write_text(target, faq)
    update_state(project_id, last_export=workspace_relative(project_id, target))
    return {
        "project_id": project_id,
        "artifact": "gaps",
        "format": "faq",
        "source": str((change_gaps_path(workspace_path(project_id), change_id) if change_id
                       else workspace_path(project_id) / "01_discovery" / "decisions.md").as_posix()),
        "path": str(target.as_posix()),
    }


def export_mdx(project_id: str, artifact: str, source: Path, verdict: dict | None = None) -> dict[str, str]:
    artifact = artifact.lower()
    if artifact != "prd":
        raise InputError("MDX export is currently supported only for --artifact prd.")
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
    update_state(project_id, last_export=workspace_relative(project_id, mdx_path))
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
        "source": workspace_citation(project_id, source),  # IMP-308
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
Source of truth: `{workspace_citation(project_id, source)}`

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


def artifact_source(base: Path, artifact: str, domain: str | None, change_id: str | None = None) -> Path:
    artifact = artifact.lower()
    if change_id:  # IMP-386: the change's own brief and gaps; everything else is the project's
        if artifact == "gaps":
            return change_gaps_path(base, change_id)
        if artifact == "brief":
            return base / "02_requirements" / change_id / "project-brief.md"
        if artifact in ("borde", "decisiones"):  # IMP-412
            from .review_views import review_path

            return review_path(base, change_id, artifact)
        if artifact in ("prototype", "prototype-manual", "prototype-trace"):  # H27 inc 7a: the change's own prototype folder
            from .prototype import INVENTORY_MD, prototype_dir
            from .prototype_manual import MANUAL_MD
            from .prototype_trace import TRACE_MD

            return prototype_dir(base, change_id) / {"prototype": INVENTORY_MD, "prototype-manual": MANUAL_MD, "prototype-trace": TRACE_MD}[artifact]
        if artifact == "release-guide":  # H27 inc 7c: the guide of the change's series
            from .release_guide import GUIDE_FILE
            from .series_scope import series_dir

            return series_dir(base, change_id) / GUIDE_FILE
        raise InputError(f"Unsupported export artifact with --change: {artifact}")
    if artifact == "gaps":
        return base / "01_discovery" / "gaps.md"
    if artifact == "brief":
        return base / "02_requirements" / "project-brief.md"
    if artifact == "prd":
        return base / "03_specs" / "prd.md"
    if artifact == "context-request":
        if not domain:
            raise InputError("--domain is required when exporting context-request.")
        return base / "08_context_packs" / "requests" / f"{domain.lower()}_context_request.md"
    raise InputError(f"Unsupported export artifact: {artifact}")
