from __future__ import annotations

from pathlib import Path
import re

from .compilers.specs import spec_unit_snapshot, spec_unit_statement
from .core.markdown import parse_frontmatter, parse_table_rows
from .decisions import register_gate_override
from .ears import requirements_quality_report
from .ids import prefix_for_node_type
from .maturity import brief_section_readiness, prd_section_readiness
from .core.graph import load_graph, parents_of
from .workspace import read_json, state_path, workspace_path


def validate_project(project_id: str, override_source: Path | None = None) -> dict[str, object]:
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
    requirement_quality, requirement_warnings = requirement_quality_validation(base)
    cross_consistency = cross_artifact_consistency(project_id, base)
    consistency_warnings = [str(item["message"]) for item in cross_consistency.get("warnings", []) if isinstance(item, dict)]

    verdict = "VALID" if not findings else "INVALID"
    result = {
        "verdict": verdict,
        "findings": findings,
        "semantic_quality": semantic_quality,
        "requirement_quality": requirement_quality,
        "cross_artifact_consistency": cross_consistency,
        "warnings": [*quality_warnings, *requirement_warnings, *consistency_warnings],
    }
    if override_source:
        result["override"] = register_gate_override(
            project_id,
            "validate",
            override_source,
            verdict=verdict,
            findings=[*findings, *result["warnings"]],
        )
    return result


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


CLAIM_STOPWORDS = {
    "a",
    "al",
    "and",
    "ante",
    "as",
    "con",
    "de",
    "del",
    "dentro",
    "during",
    "el",
    "en",
    "for",
    "from",
    "la",
    "las",
    "los",
    "of",
    "para",
    "por",
    "que",
    "se",
    "the",
    "to",
    "un",
    "una",
    "y",
}
CLAIM_SKIP_PREFIXES = (
    "source:",
    "sources:",
    "fuente:",
    "fuentes:",
    "evidence:",
    "evidencia:",
    "trace:",
    "traza:",
)


def artifact_faithfulness_report(
    artifact_text: str,
    evidence_quotes: list[str] | list[dict[str, object]],
    *,
    artifact: str = "artifact",
) -> dict[str, object]:
    """Score atomic generated claims against local verbatim evidence quotes.

    This is an eval helper, not a runtime gate. It intentionally favors
    deterministic token coverage over semantic inference so unsupported claims
    remain visible in synthetic fixtures.
    """
    evidence_items = normalize_faithfulness_evidence(evidence_quotes)
    claims = extract_atomic_claims(artifact_text)
    evaluated = []
    for index, claim in enumerate(claims, start=1):
        support = best_claim_support(claim["text"], evidence_items)
        evaluated.append(
            {
                "id": f"CLM-{index:03d}",
                "artifact": artifact,
                "text": claim["text"],
                "supported": support["supported"],
                "support_source": support["source"],
                "support_quote": support["quote"],
                "token_coverage": support["token_coverage"],
                "reason": support["reason"],
            }
        )
    supported = sum(1 for claim in evaluated if claim["supported"])
    total = len(evaluated)
    return {
        "artifact": artifact,
        "claim_count": total,
        "supported_claim_count": supported,
        "unsupported_claim_count": total - supported,
        "score": round(supported / total, 3) if total else 1.0,
        "claims": evaluated,
    }


def normalize_faithfulness_evidence(evidence_quotes: list[str] | list[dict[str, object]]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for index, item in enumerate(evidence_quotes, start=1):
        if isinstance(item, dict):
            quote = str(item.get("quote", "")).strip()
            source = str(item.get("source", f"evidence:{index}")).strip()
        else:
            quote = str(item).strip()
            source = f"evidence:{index}"
        if quote:
            items.append({"source": source or f"evidence:{index}", "quote": quote})
    return items


def extract_atomic_claims(markdown_text: str) -> list[dict[str, str]]:
    claims: list[dict[str, str]] = []
    in_fence = False
    in_frontmatter = False
    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if line == "---" and not claims:
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            continue
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line:
            continue
        if line.startswith("#") or re.fullmatch(r"\|?[\s:\-|]+\|?", line):
            continue
        line = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", line)
        cells = parse_table_rows(line) if line.startswith("|") and line.endswith("|") else []
        fragments = cells[0] if cells else [line]
        for fragment in fragments:
            for sentence in split_claim_fragments(fragment):
                if is_atomic_claim(sentence):
                    claims.append({"text": sentence})
    return claims


def split_claim_fragments(text: str) -> list[str]:
    cleaned = re.sub(r"`([^`]+)`", r"\1", text)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"[*_]{1,3}", "", cleaned)
    cleaned = cleaned.strip(" -|\t")
    parts = re.split(r"(?<=[.!?;])\s+|\s+[•]\s+", cleaned)
    return [part.strip(" .;:") for part in parts if part.strip(" .;:")]


def is_atomic_claim(text: str) -> bool:
    lowered = text.strip().lower()
    if any(lowered.startswith(prefix) for prefix in CLAIM_SKIP_PREFIXES):
        return False
    normalized = normalize_claim_text(text)
    if not normalized:
        return False
    if any(normalized.startswith(prefix.rstrip(":")) for prefix in CLAIM_SKIP_PREFIXES):
        return False
    tokens = claim_tokens(text)
    return len(tokens) >= 3


def best_claim_support(claim_text: str, evidence_items: list[dict[str, str]]) -> dict[str, object]:
    claim_normalized = normalize_claim_text(claim_text)
    claim_tokens_set = set(claim_tokens(claim_text))
    claim_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", claim_text))
    best = {
        "supported": False,
        "source": None,
        "quote": None,
        "token_coverage": 0.0,
        "reason": "no_evidence",
    }
    for item in evidence_items:
        quote = item["quote"]
        quote_normalized = normalize_claim_text(quote)
        quote_tokens_set = set(claim_tokens(quote))
        if claim_normalized and claim_normalized in quote_normalized:
            return {
                "supported": True,
                "source": item["source"],
                "quote": quote,
                "token_coverage": 1.0,
                "reason": "exact_substring",
            }
        if not claim_tokens_set:
            continue
        coverage = len(claim_tokens_set & quote_tokens_set) / len(claim_tokens_set)
        numbers_match = not claim_numbers or claim_numbers <= set(re.findall(r"\d+(?:[.,]\d+)?", quote))
        if coverage > float(best["token_coverage"]):
            best = {
                "supported": coverage >= 0.78 and numbers_match,
                "source": item["source"],
                "quote": quote,
                "token_coverage": round(coverage, 3),
                "reason": "token_overlap" if numbers_match else "number_mismatch",
            }
    return best


def claim_tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", normalize_claim_text(text))
        if len(token) > 2 and token not in CLAIM_STOPWORDS
    ]


def normalize_claim_text(text: str) -> str:
    normalized = str(text).lower()
    normalized = re.sub(r"`([^`]+)`", r"\1", normalized)
    normalized = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", normalized)
    normalized = re.sub(r"[^a-z0-9áéíóúñü]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def requirement_quality_validation(base: Path) -> tuple[dict[str, object], list[str]]:
    path = base / "02_requirements" / "requirements.md"
    if not path.exists():
        return {"score": 0.0, "statement_count": 0, "classifications": {}, "statements": [], "warnings": []}, []
    report = requirements_quality_report(path.read_text(encoding="utf-8"))
    warnings = [
        (
            f"{item['statement_id']} requirement-quality warning {item['signal_id']}: "
            f"{item['message']} Fragment: \"{item['fragment']}\""
        )
        for item in report.get("warnings", [])
        if isinstance(item, dict)
    ]
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
    check_expected_evidence_contract(project_id, base, checks, warnings)
    check_spec_unit_story_handoff_fidelity(project_id, base, checks, warnings)

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


EXPECTED_EVIDENCE_SOURCE_MARKERS = {
    "client": ("00_raw", "02_requirements", "client", "requirements.md", "workshop"),
    "customer": ("00_raw", "02_requirements", "client", "requirements.md", "workshop"),
    "business": ("00_raw", "02_requirements", "client", "requirements.md", "workshop"),
    "business_rule": ("00_raw", "02_requirements", "client", "requirements.md", "workshop"),
    "quality": ("quality", "05_quality"),
    "design": ("design", "prototype", "ux"),
    "technology": ("technology", "technical", "architecture", "backend", "frontend", "sad"),
    "technical": ("technology", "technical", "architecture", "backend", "frontend", "sad"),
    "prd": ("03_specs/prd.md", "prd"),
    "spec": ("03_specs", "spec"),
    "assumption": ("assumption", "assumptions"),
    "decision": ("decision", "decisions"),
}


def check_expected_evidence_contract(
    project_id: str,
    base: Path,
    checks: list[dict[str, object]],
    warnings: list[dict[str, str]],
) -> None:
    unit_paths = sorted((base / "03_specs" / "units").glob("SPEC-U-*.md"))
    declared = 0
    issues = 0
    for path in unit_paths:
        frontmatter = parse_frontmatter(read_text(path))
        expected = frontmatter.get("expected_evidence")
        if not isinstance(expected, dict):
            continue
        kind = str(expected.get("kind", "")).strip()
        rationale = str(expected.get("rationale", "")).strip()
        if not kind:
            continue
        declared += 1
        sources = frontmatter.get("sources", [])
        if not isinstance(sources, list):
            sources = []
        if expected_evidence_matches_sources(kind, [str(source) for source in sources]):
            continue
        issues += 1
        detail = f" Rationale: {rationale}" if rationale else ""
        add_consistency_warning(
            warnings,
            "expected_evidence_mismatch",
            "spec_unit->source",
            relative_to_workspace(base, path),
            f"{path.stem} expects `{kind}` evidence, but its cited sources do not match that expectation.{detail}",
            f"python -m sentinel /specs {project_id}",
        )
    checks.append(
        {
            "id": "expected_evidence_contract",
            "status": "SKIP" if declared == 0 else ("WARN" if issues else "PASS"),
            "layer": "spec_unit->source",
            "artifact": "03_specs/units/",
            "declared": declared,
            "issues": issues,
        }
    )


def expected_evidence_matches_sources(kind: str, sources: list[str]) -> bool:
    normalized_kind = re.sub(r"[^a-z0-9]+", "_", kind.lower()).strip("_")
    markers = EXPECTED_EVIDENCE_SOURCE_MARKERS.get(normalized_kind)
    if markers is None:
        return True
    evidence_text = "\n".join(sources).lower()
    return any(marker in evidence_text for marker in markers)


def check_spec_unit_story_handoff_fidelity(
    project_id: str,
    base: Path,
    checks: list[dict[str, object]],
    warnings: list[dict[str, str]],
) -> None:
    readiness_path = base / "08_context_packs" / "implementation_readiness.json"
    if not readiness_path.exists():
        checks.append({"id": "spec_unit_story_handoff", "status": "SKIP", "layer": "spec_unit->story", "artifact": "04_backlog/"})
        return
    readiness = read_json(readiness_path, {})
    stories = readiness.get("stories", []) if isinstance(readiness, dict) else []
    if not isinstance(stories, list) or not stories:
        checks.append({"id": "spec_unit_story_handoff", "status": "SKIP", "layer": "spec_unit->story", "artifact": "04_backlog/"})
        return
    units = {
        str(unit_id).strip(): spec_unit_statement(str(data.get("text", "")))
        for unit_id, data in spec_unit_snapshot(base).items()
        if isinstance(data, dict)
    }
    issues = 0
    checked = 0
    for item in stories:
        if not isinstance(item, dict):
            continue
        story_id = str(item.get("story_id", "")).strip()
        source_unit = str(item.get("source_unit", "")).strip()
        if not story_id or not source_unit or source_unit not in units:
            continue
        statement = str(units[source_unit]).strip()
        if not statement:
            continue
        story_path = base / "04_backlog" / f"{story_id}.md"
        if not story_path.exists():
            continue
        checked += 1
        acceptance = story_acceptance_criteria(read_text(story_path))
        statement_key = normalize_handoff_text(statement)
        if any(statement_key in normalize_handoff_text(str(row.get("criterion", ""))) for row in acceptance):
            continue
        issues += 1
        snippet = statement if len(statement) <= 96 else statement[:93] + "..."
        add_consistency_warning(
            warnings,
            "spec_unit_story_handoff",
            "spec_unit->story",
            relative_to_workspace(base, story_path),
            f"{story_id} does not preserve the confirmed {source_unit} statement inside story acceptance criteria: {snippet}",
            f"python -m sentinel /backlog {project_id}",
        )
    checks.append(
        {
            "id": "spec_unit_story_handoff",
            "status": "SKIP" if checked == 0 else ("WARN" if issues else "PASS"),
            "layer": "spec_unit->story",
            "artifact": "04_backlog/",
            "stories": checked,
            "issues": issues,
        }
    )


def ids_in_file(path: Path, pattern: re.Pattern[str]) -> set[str]:
    return set(pattern.findall(read_text(path)))


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def unit_texts_exist(base: Path) -> bool:
    return any((base / "03_specs" / "units").glob("SPEC-U-*.md"))


def story_acceptance_criteria(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("| AC-"):
            continue
        cells = parse_table_rows(line, strip_code_ticks=False)[0]
        if len(cells) >= 3:
            rows.append({"id": cells[0], "classification": cells[1], "criterion": cells[2]})
    return rows


def normalize_handoff_text(text: str) -> str:
    normalized = str(text).replace("`", " ").lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


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
