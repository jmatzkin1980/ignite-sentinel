from __future__ import annotations

from pathlib import Path
import re

from .core.markdown import parse_frontmatter
from .ids import prefix_for_node_type
from .maturity import brief_section_readiness, prd_section_readiness
from .core.graph import load_graph, parents_of
from .workspace import state_path, workspace_path


def validate_project(project_id: str) -> dict[str, object]:
    findings: list[str] = []
    base = workspace_path(project_id)
    if not base.exists():
        return {"verdict": "INVALID", "findings": [f"Workspace does not exist: {project_id}"]}
    if not state_path(project_id).exists():
        findings.append("Missing state.json.")
    config = base / "sentinel.config.yaml"
    if not config.exists():
        findings.append("Missing sentinel.config.yaml.")

    graph = load_graph(project_id)
    node_ids = set()
    for node in graph.get("nodes", []):
        node_id = node.get("id", "")
        node_type = node.get("type", "")
        expected_prefix = prefix_for_node_type(node_type)
        if expected_prefix and not node_id.startswith(f"{expected_prefix}-"):
            findings.append(f"{node_id} prefix does not match type {node_type}.")
        if node_id in node_ids:
            findings.append(f"Duplicate node id: {node_id}.")
        node_ids.add(node_id)
        path_value = node.get("path")
        if path_value and not resolve_path(base, path_value).exists():
            findings.append(f"{node_id} points to missing artifact: {path_value}.")

    for edge in graph.get("edges", []):
        if edge.get("from") not in node_ids:
            findings.append(f"Edge source missing: {edge.get('from')}.")
        if edge.get("to") not in node_ids:
            findings.append(f"Edge target missing: {edge.get('to')}.")

    findings.extend(validate_semantic_artifacts(project_id, base, graph))

    semantic_quality, quality_warnings = semantic_quality_report(base)
    cross_consistency = cross_artifact_consistency(project_id, base)
    consistency_warnings = [str(item["message"]) for item in cross_consistency.get("warnings", []) if isinstance(item, dict)]

    verdict = "VALID" if not findings else "INVALID"
    return {
        "verdict": verdict,
        "findings": findings,
        "semantic_quality": semantic_quality,
        "cross_artifact_consistency": cross_consistency,
        "warnings": [*quality_warnings, *consistency_warnings],
    }


def resolve_path(base: Path, path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    candidate = Path.cwd() / path
    if candidate.exists():
        return candidate
    return base / path


def validate_semantic_artifacts(project_id: str, base: Path, graph: dict) -> list[str]:
    findings: list[str] = []
    node_types = {node.get("type") for node in graph.get("nodes", [])}
    if "raw_input" in node_types:
        for required in ("identity_seed_bank", "discovery_log", "lens_review", "knowledge_ledger", "gap_report", "requirement"):
            if required not in node_types:
                findings.append(f"Discovery artifact missing after raw input: {required}.")

    prd_path = base / "03_specs" / "prd.md"
    if prd_path.exists():
        prd_text = prd_path.read_text(encoding="utf-8")
        required_pairs = (
            ("Resumen Ejecutivo", "Executive Summary"),
            ("Alcance", "Scope"),
            ("Usuarios y personas", "Users And Personas"),
            ("Requerimientos funcionales", "Functional Requirements"),
            ("Acceptance Criteria", "Acceptance Criteria"),
            ("Criterios de exito del negocio", "Business Success Criteria"),
            ("Mapa de dependencias", "Dependency Map"),
            ("Trazabilidad", "Traceability"),
        )
        for es_section, en_section in required_pairs:
            if es_section not in prd_text and en_section not in prd_text:
                findings.append(f"PRD missing section: {es_section}/{en_section}.")

    spec_path = base / "03_specs" / "specs.md"
    if spec_path.exists():
        spec_text = spec_path.read_text(encoding="utf-8")
        for section in ("Spec Contract", "Backlog-Relevant Contract", "Progressive Disclosure Context Map", "Retrieval Plan For Backlog Agents", "Backlog Seeds", "Traceability"):
            if section not in spec_text:
                findings.append(f"Spec missing section: {section}.")
        if not (base / "08_context_packs" / "specs_generation.json").exists():
            findings.append("Specs exist without specs_generation context pack.")

    for story in [node for node in graph.get("nodes", []) if node.get("type") == "user_story"]:
        story_path = resolve_path(base, story.get("path", ""))
        if not story_path.exists():
            continue
        story_text = story_path.read_text(encoding="utf-8")
        for section in ("Acceptance Criteria", "Agent Execution Contract", "Retrieval Plan For Execution Agents", "Readiness Checklist"):
            if section not in story_text:
                findings.append(f"{story['id']} missing story readiness signal: {section}.")
        if not parents_of(project_id, story["id"]):
            findings.append(f"{story['id']} has no upstream parent.")

    if "user_story" in node_types and "backlog_readiness_audit" not in node_types:
        findings.append("Backlog exists without backlog_readiness_audit.")
    if "user_story" in node_types and not (base / "08_context_packs" / "implementation_readiness.json").exists():
        findings.append("Backlog exists without implementation_readiness context pack.")
    gaps_path = base / "01_discovery" / "gaps.md"
    if gaps_path.exists() and "CLOSED" in gaps_path.read_text(encoding="utf-8"):
        resolution_log = base / "01_discovery" / "gap_resolution_log.md"
        if not resolution_log.exists():
            findings.append("Closed gaps exist without gap_resolution_log.md.")
    return findings


PENDING_MARKERS = ("[PENDING INPUT]", "[PENDING DOMAIN CONTEXT]")

EVIDENCE_MARKERS = (
    "| P-E",
    "| FR-E",
    "| FR-",
    "_(source:",
    "_(fuente:",
    "(confirm baseline)",
    "Evidence that triggers the question:",
    "Evidencia que dispara la pregunta:",
)


def score_artifact_text(text: str) -> dict[str, object]:
    """Deterministic semantic-quality score: evidence signals vs pending placeholders.

    This is a heuristic for visibility, not a gate. A low score means the
    artifact is mostly scaffolding and needs more discovery evidence.
    """
    pending = sum(text.count(marker) for marker in PENDING_MARKERS)
    evidence = sum(text.count(marker) for marker in EVIDENCE_MARKERS)
    total = pending + evidence
    score = round(evidence / total, 3) if total else 0.0
    if evidence and score >= 0.5:
        classification = "evidence-backed"
    elif evidence:
        classification = "mixed"
    else:
        classification = "scaffolding"
    return {
        "pending_markers": pending,
        "evidence_signals": evidence,
        "score": score,
        "classification": classification,
    }


def semantic_quality_report(base: Path) -> tuple[dict[str, dict[str, object]], list[str]]:
    """Score generated artifacts and emit non-blocking warnings for scaffolding."""
    targets = {
        "project-brief.md": base / "02_requirements" / "project-brief.md",
        "prd.md": base / "03_specs" / "prd.md",
        "specs.md": base / "03_specs" / "specs.md",
    }
    report: dict[str, dict[str, object]] = {}
    warnings: list[str] = []
    for name, path in targets.items():
        if not path.exists():
            continue
        result = score_artifact_text(path.read_text(encoding="utf-8"))
        report[name] = result
        if result["classification"] == "scaffolding":
            warnings.append(
                f"{name} has no evidence-backed signals ({result['pending_markers']} pending markers): "
                "it is mostly scaffolding. Resolve gaps and re-run /specs before downstream handoff."
            )
        elif result["classification"] == "mixed":
            warnings.append(
                f"{name} is partially evidence-backed (score {result['score']}): "
                f"{result['pending_markers']} pending markers remain."
            )
    return report, warnings


EARS_ID_RE = re.compile(r"\bREQ-EARS-\d{3}\b")
FR_EXTRACT_ID_RE = re.compile(r"\bFR-E\d{2,3}\b")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.M)


def cross_artifact_consistency(project_id: str, base: Path | None = None) -> dict[str, object]:
    """Report non-blocking consistency warnings across brief, PRD, specs, and units."""
    base = base or workspace_path(project_id)
    warnings: list[dict[str, str]] = []
    checks: list[dict[str, object]] = []

    check_brief_prd_continuity(project_id, base, checks, warnings)
    check_ears_specs_continuity(project_id, base, checks, warnings)
    check_fr_specs_continuity(project_id, base, checks, warnings)
    check_spec_unit_pointers(project_id, base, checks, warnings)

    return {
        "verdict": "WARN" if warnings else "CLEAN",
        "warnings_count": len(warnings),
        "warnings": warnings,
        "checks": checks,
    }


def check_brief_prd_continuity(
    project_id: str,
    base: Path,
    checks: list[dict[str, object]],
    warnings: list[dict[str, str]],
) -> None:
    brief_path = base / "02_requirements" / "project-brief.md"
    prd_path = base / "03_specs" / "prd.md"
    if not brief_path.exists() or not prd_path.exists():
        checks.append({"id": "brief_to_prd", "status": "SKIP", "layer": "brief->prd", "artifact": "03_specs/prd.md"})
        return

    brief = brief_section_readiness(brief_path.read_text(encoding="utf-8"))
    prd = prd_section_readiness(prd_path.read_text(encoding="utf-8"))
    mappings = {
        "1": ("1", "6"),
        "2": ("3",),
        "3": ("2", "4", "7"),
        "4": ("9", "12"),
        "5": ("5", "8"),
        "6": ("10", "11", "13"),
    }
    issues = 0
    brief_sections = brief.get("sections", {})
    prd_sections = prd.get("sections", {})
    for brief_section, prd_targets in mappings.items():
        if not isinstance(brief_sections, dict) or not isinstance(prd_sections, dict):
            continue
        source = brief_sections.get(brief_section, {})
        if not isinstance(source, dict) or source.get("status") != "populated":
            continue
        populated_targets = [
            target
            for target in prd_targets
            if isinstance(prd_sections.get(target), dict) and prd_sections[target].get("status") == "populated"
        ]
        if populated_targets:
            continue
        issues += 1
        add_consistency_warning(
            warnings,
            "brief_to_prd",
            "brief->prd",
            "03_specs/prd.md",
            f"Brief section {brief_section} is populated but mapped PRD sections {', '.join(prd_targets)} still look pending.",
            f"python -m sentinel /specs {project_id}",
        )
    checks.append({"id": "brief_to_prd", "status": "WARN" if issues else "PASS", "layer": "brief->prd", "artifact": "03_specs/prd.md", "issues": issues})


def check_ears_specs_continuity(
    project_id: str,
    base: Path,
    checks: list[dict[str, object]],
    warnings: list[dict[str, str]],
) -> None:
    requirements_path = base / "02_requirements" / "requirements.md"
    specs_path = base / "03_specs" / "specs.md"
    unit_paths = sorted((base / "03_specs" / "units").glob("SPEC-U-*.md"))
    ears_ids = ids_in_file(requirements_path, EARS_ID_RE)
    if not ears_ids:
        checks.append({"id": "ears_to_specs", "status": "SKIP", "layer": "requirements->specs", "artifact": "02_requirements/requirements.md"})
        return
    specs_ids = ids_in_file(specs_path, EARS_ID_RE)
    unit_ids = set()
    for path in unit_paths:
        unit_ids.update(ids_in_file(path, EARS_ID_RE))
    missing_specs = sorted(ears_ids - specs_ids)
    missing_units = sorted(ears_ids - unit_ids)
    for ears_id in missing_specs:
        add_consistency_warning(
            warnings,
            "ears_to_specs_index",
            "requirements->specs",
            "03_specs/specs.md",
            f"{ears_id} is confirmed in requirements but is not cited in specs.md.",
            f"python -m sentinel /specs {project_id}",
        )
    for ears_id in missing_units:
        add_consistency_warning(
            warnings,
            "ears_to_spec_unit",
            "requirements->spec_unit",
            "03_specs/units/",
            f"{ears_id} is confirmed in requirements but has no SPEC-U unit.",
            f"python -m sentinel /specs {project_id}",
        )
    checks.append(
        {
            "id": "ears_to_specs",
            "status": "WARN" if missing_specs or missing_units else "PASS",
            "layer": "requirements->specs",
            "artifact": "03_specs/",
            "requirements": len(ears_ids),
            "missing_specs": missing_specs,
            "missing_units": missing_units,
        }
    )


def check_fr_specs_continuity(
    project_id: str,
    base: Path,
    checks: list[dict[str, object]],
    warnings: list[dict[str, str]],
) -> None:
    prd_path = base / "03_specs" / "prd.md"
    fr_ids = ids_in_file(prd_path, FR_EXTRACT_ID_RE)
    if not fr_ids:
        checks.append({"id": "fr_to_specs", "status": "SKIP", "layer": "prd->specs", "artifact": "03_specs/prd.md"})
        return
    missing = [] if unit_texts_exist(base) else sorted(fr_ids)
    for fr_id in missing:
        add_consistency_warning(
            warnings,
            "fr_to_spec_unit",
            "prd->spec_unit",
            "03_specs/units/",
            f"{fr_id} appears in the PRD but is not referenced by any spec unit.",
            f"python -m sentinel /specs {project_id}",
        )
    checks.append({"id": "fr_to_specs", "status": "WARN" if missing else "PASS", "layer": "prd->specs", "artifact": "03_specs/units/", "functional_extracts": len(fr_ids), "missing_units": missing})


def check_spec_unit_pointers(
    project_id: str,
    base: Path,
    checks: list[dict[str, object]],
    warnings: list[dict[str, str]],
) -> None:
    requirements_ears = ids_in_file(base / "02_requirements" / "requirements.md", EARS_ID_RE)
    unit_paths = sorted((base / "03_specs" / "units").glob("SPEC-U-*.md"))
    issues = 0
    for path in unit_paths:
        text = read_text(path)
        unit_id = path.stem
        unit_ears = set(EARS_ID_RE.findall(text))
        orphan_ears = sorted(unit_ears - requirements_ears)
        for ears_id in orphan_ears:
            issues += 1
            add_consistency_warning(
                warnings,
                "orphan_spec_unit_ears",
                "spec_unit->requirements",
                relative_to_workspace(base, path),
                f"{unit_id} cites {ears_id}, but that EARS ID is absent from requirements.md.",
                f"python -m sentinel /specs {project_id}",
            )
        sources = parse_frontmatter(text).get("sources", [])
        if not isinstance(sources, list):
            sources = []
        for pointer in [str(value) for value in sources]:
            if pointer.startswith("[PENDING"):
                continue
            if not pointer_resolves(base, pointer):
                issues += 1
                add_consistency_warning(
                    warnings,
                    "dangling_spec_unit_pointer",
                    "spec_unit->source",
                    relative_to_workspace(base, path),
                    f"{unit_id} has a dangling source pointer: {pointer}.",
                    f"python -m sentinel /specs {project_id}",
                )
    checks.append({"id": "spec_unit_pointers", "status": "WARN" if issues else "PASS", "layer": "spec_unit->source", "artifact": "03_specs/units/", "units": len(unit_paths), "issues": issues})


def ids_in_file(path: Path, pattern: re.Pattern[str]) -> set[str]:
    return set(pattern.findall(read_text(path)))


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def unit_texts_exist(base: Path) -> bool:
    return any((base / "03_specs" / "units").glob("SPEC-U-*.md"))


def pointer_resolves(base: Path, pointer: str) -> bool:
    file_part, _, anchor = pointer.partition("#")
    target = base / file_part
    if not target.exists() or not target.is_file():
        return False
    if not anchor:
        return True
    text = target.read_text(encoding="utf-8")
    if anchor == "normalized-requirements-ears":
        return "Normalized Requirements (EARS)" in text
    if anchor and anchor[0].isdigit():
        section = anchor.split("-", 1)[0]
        return bool(re.search(rf"^##\s+{re.escape(section)}\.", text, re.M))
    return anchor in markdown_heading_anchors(text)


def markdown_heading_anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    for match in HEADING_RE.finditer(text):
        title = re.sub(r"`([^`]+)`", r"\1", match.group(2)).strip().lower()
        title = re.sub(r"[^a-z0-9\s-]", "", title)
        title = re.sub(r"\s+", "-", title).strip("-")
        if title:
            anchors.add(title)
    return anchors


def add_consistency_warning(
    warnings: list[dict[str, str]],
    check_id: str,
    layer: str,
    artifact: str,
    message: str,
    suggested_command: str,
) -> None:
    warnings.append(
        {
            "check": check_id,
            "layer": layer,
            "artifact": artifact,
            "message": message,
            "suggested_command": suggested_command,
        }
    )


def relative_to_workspace(base: Path, path: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()
