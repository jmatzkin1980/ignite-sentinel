from __future__ import annotations

from .errors import GateRefusal  # IMP-302: typed errors

import re
from pathlib import Path
from typing import Any

from .backlog.gates import evaluate_story_gates, update_story_gate_state
from .core.graph import add_edge, add_node, nodes_by_type
from .decisions import register_gate_override
from .memory import ContextBroker
from .workspace import read_json, state_path, update_state, workspace_path
from .compilers.change_functionalities import story_size
from .core.io import write_text

REQUIRED_AC_CLASSES = {"fail-to-pass", "pass-to-pass", "evidence"}
STORY_QUALITY_MIN_SCORE = 0.8
TECHNICAL_LAYER_TERMS = {
    "endpoint",
    "api",
    "table",
    "database",
    "schema",
    "repository",
    "service",
    "worker",
    "component",
    "infra",
    "infrastructure",
    "migration",
}
BEHAVIOR_TERMS = {
    "user",
    "usuario",
    "system",
    "sistema",
    "display",
    "show",
    "view",
    "submit",
    "approve",
    "reject",
    "notify",
    "block",
    "recover",
    "audit",
    "trace",
    "mostrar",
    "ver",
    "aprobar",
    "rechazar",
    "notificar",
    "bloquear",
}
INVEST_SIGNAL_ORDER = (
    ("I", "Independent"),
    ("N", "Negotiable"),
    ("V", "Valuable"),
    ("E", "Estimable"),
    ("S", "Small"),
    ("T", "Testable"),
)
UPSTREAM_TRACE_PREFIXES = ("SPEC-", "REQ-", "FR-", "JTBD-", "RULE-", "KPI-")
STORY_REFERENCE_PREFIXES = ("US-",)


CHANGE_QUALITY_TEXT = {
    "es": {
        "behind": "El backlog de {cid} falta o está atrasado",
        "empty": "{cid} no tiene historias para auditar",
    },
    "en": {
        "behind": "The backlog of {cid} is missing or behind",
        "empty": "{cid} has no stories to audit",
    },
}


def _change_story_scope(project_id: str, change_id: str, stories: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    """IMP-431: the change's stories (gate: its backlog is there and current, and has stories) and the language of its artifacts."""
    from .changes import change_language, get_change
    from .compilers.change_backlog import _change_story_ids, read_change_units
    from .readiness_verdict import _backlog_behind

    change = get_change(project_id, change_id)
    language = "en" if change_language(project_id, change) == "en" else "es"
    text = CHANGE_QUALITY_TEXT[language]
    base = workspace_path(project_id)
    backlog = change.get("backlog")
    derived = [record for record in (change.get("backlog_releases") or {}).values()
               if isinstance(record, dict) and record.get("stories")]
    if backlog:
        behind = _backlog_behind(
            base, change_id, read_change_units(project_id, change_id), list(backlog.get("dropped_units") or []))
    else:  # a confirmed series (7d) keeps one record per derived release: audit the stories of all of them
        behind = not derived
    if behind:
        raise GateRefusal(text["behind"].format(cid=change_id), next_step=f"/backlog {project_id} --change {change_id}")
    own = set(_change_story_ids(base, change_id))
    scoped = sorted((story for story in stories if story["id"] in own), key=lambda story: story["id"])
    if not scoped:
        raise GateRefusal(text["empty"].format(cid=change_id), next_step=f"/backlog {project_id} --change {change_id}")
    return scoped, language


def _project_stories(project_id: str, stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """IMP-431: the project's own stories: the ones a change wrote (frontmatter `change:`) are audited by `/quality --change`."""
    from .changes import list_changes
    from .compilers.change_backlog import _change_story_ids

    base = workspace_path(project_id)
    theirs = {sid for change_id in list_changes(project_id) for sid in _change_story_ids(base, change_id)}
    return [story for story in stories if story["id"] not in theirs]


def generate_quality(project_id: str, override_source: Path | None = None, change_id: str | None = None) -> dict[str, object]:
    base = workspace_path(project_id)
    stories = nodes_by_type(project_id, "user_story")
    language: str | None = None
    if change_id:
        stories, language = _change_story_scope(project_id, change_id, stories)
        out_dir = base / "05_quality" / change_id
    else:
        stories = _project_stories(project_id, stories)
        out_dir = base / "05_quality"
    if not stories:
        raise GateRefusal("Cannot generate quality artifacts without user stories.")

    readiness_by_story = implementation_readiness_by_story(project_id)
    quality_results: dict[str, dict[str, Any]] = {}
    created: list[str] = []
    for index, story in enumerate(stories, start=1):
        story_path = resolve_story_path(story["path"])
        story_text = story_path.read_text(encoding="utf-8") if story_path.exists() else ""
        criteria = extract_acceptance_criteria(story_text)
        criterion_details = extract_acceptance_details(story_text)
        readiness_item = readiness_by_story.get(story["id"], {})
        quality_results[story["id"]] = evaluate_story_quality(story, story_text, criterion_details, readiness_item)

        tc_path = out_dir / f"TC-{index:03d}.md"
        write_text(tc_path, render_test_case(project_id, story["id"], criteria, language))
        tc_id = add_node(project_id, "TC", "test_case", tc_path, f"Test coverage for {story['id']}", domain="quality")
        add_edge(project_id, story["id"], tc_id, "covered_by")
        ContextBroker(project_id).index_artifact(
            tc_id,
            "test_case",
            tc_path,
            tc_path.read_text(encoding="utf-8"),
            domain="quality",
            trace_ids=[story["id"], tc_id],
        )
        created.append(tc_id)

    if change_id:  # the project's own entries stay
        previous = read_json(state_path(project_id), {}).get("story_quality", {})
        update_state(project_id, story_quality={**(previous if isinstance(previous, dict) else {}), **quality_results})
    else:
        update_state(project_id, story_quality=quality_results)
    state = read_json(state_path(project_id), {})
    lifecycle = state.get("story_lifecycle", {}) if isinstance(state.get("story_lifecycle", {}), dict) else {}
    for story in stories:
        readiness_item = dict(readiness_by_story.get(story["id"], {}))
        lifecycle_entry = lifecycle.get(story["id"], {}) if isinstance(lifecycle.get(story["id"], {}), dict) else {}
        if lifecycle_entry.get("owner"):
            readiness_item["owner"] = lifecycle_entry["owner"]
        story_path = resolve_story_path(story["path"])
        story_text = story_path.read_text(encoding="utf-8") if story_path.exists() else ""
        gate_story = story_for_gate(story, story_text, readiness_item)
        update_story_gate_state(project_id, story["id"], evaluate_story_gates(project_id, gate_story, readiness_item))

    audit_path = out_dir / "backlog_readiness_audit.md"
    write_text(audit_path, render_backlog_audit(project_id, stories, quality_results, language, change_id))
    audit_id = add_node(project_id, "QA", "backlog_readiness_audit", audit_path, "Backlog readiness audit", domain="quality")
    for story in stories:
        add_edge(project_id, story["id"], audit_id, "audited_by")
    ContextBroker(project_id).index_artifact(
        audit_id,
        "backlog_readiness_audit",
        audit_path,
        audit_path.read_text(encoding="utf-8"),
        domain="quality",
        trace_ids=[audit_id, *[story["id"] for story in stories]],
    )

    verdict = quality_audit_verdict(quality_results)
    result: dict[str, object] = {
        "test_cases": created,
        "count": len(created),
        "audit": str(audit_path),
        "verdict": verdict,
        "story_quality": quality_results,
    }
    if change_id:
        result["change_id"] = change_id
    if override_source:
        result["override"] = register_gate_override(
            project_id,
            "quality",
            override_source,
            verdict=verdict,
            findings=quality_override_findings(quality_results),
        )
    if change_id:
        _record_change_quality(project_id, change_id, stories, quality_results, created, audit_path, verdict)
    else:
        update_state(project_id, phase="quality_completed")
    return result


def _record_change_quality(project_id: str, change_id: str, stories: list[dict[str, Any]], quality_results: dict[str, dict[str, Any]],
                           test_cases: list[str], audit_path: Path, verdict: str) -> None:
    """IMP-431: the verdict of the change lives in the change (never `phase` or `health`); the digest says which backlog it audited."""
    from .compilers.change_backlog import change_backlog_digest
    from .core.time import utc_now

    counts = {"PASS": 0, "PARTIAL": 0, "FAIL": 0}
    for item in quality_results.values():
        counts[{"PASS": "PASS", "FAIL": "FAIL"}.get(str(item.get("status", "")), "PARTIAL")] += 1
    changes = read_json(state_path(project_id), {}).get("changes", {})
    changes[change_id]["quality"] = {
        "verdict": verdict,
        "counts": counts,
        "stories": [story["id"] for story in stories],
        "test_cases": test_cases,
        "audit": audit_path.relative_to(workspace_path(project_id)).as_posix(),
        "backlog_digest": change_backlog_digest(project_id, change_id),
        "audited_at": utc_now(),
    }
    update_state(project_id, changes=changes)


def resolve_story_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def extract_acceptance_criteria(text: str) -> list[str]:
    criteria: list[str] = []
    for line in text.splitlines():
        classified = re.match(r"\|\s*(AC-\d+(?:-\d+)?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|", line)
        if classified:
            criteria.append(f"{classified.group(1)} [{classified.group(2).strip()}]: {classified.group(3).strip()}")
            continue
        legacy = re.match(r"\|\s*(AC-\d+(?:-\d+)?)\s*\|\s*(.+?)\s*\|", line)
        if legacy:
            criteria.append(f"{legacy.group(1)}: {legacy.group(2)}")
    return criteria or ["AC-001: Validate the main happy path and a recoverable failure path."]


def extract_acceptance_details(text: str) -> list[dict[str, str]]:
    criteria: list[dict[str, str]] = []
    for line in text.splitlines():
        match = re.match(r"\|\s*(AC-\d+(?:-\d+)?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|", line)
        if not match:
            continue
        classification = match.group(2).strip()
        if classification.lower() in {"classification", "---"}:
            continue
        criteria.append(
            {
                "id": match.group(1).strip(),
                "classification": classification,
                "text": match.group(3).strip(),
            }
        )
    return criteria


def implementation_readiness_by_story(project_id: str) -> dict[str, dict[str, Any]]:
    path = workspace_path(project_id) / "08_context_packs" / "implementation_readiness.json"
    pack = read_json(path, {})
    stories = pack.get("stories", []) if isinstance(pack, dict) else []
    return {str(item.get("story_id", "")): item for item in stories if isinstance(item, dict) and item.get("story_id")}


def story_for_gate(story: dict[str, Any], story_text: str, readiness_item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": story["id"],
        "owner": readiness_item.get("owner", ""),
        "acceptance": extract_acceptance_details(story_text),
        "trace": readiness_item.get("trace", []),
        "slicing": readiness_item.get("slicing", slicing_from_story_text(story_text)),
        "readiness": readiness_item.get("readiness", ""),
        "readiness_score": readiness_item.get("readiness_score", 0.0),
    }


def slicing_from_story_text(text: str) -> str:
    match = re.search(r"\*\*Slicing Pattern:\*\*\s*(.+)", text)
    return match.group(1).strip() if match else ""


def evaluate_story_quality(
    story: dict[str, Any],
    story_text: str,
    criteria: list[dict[str, str]],
    readiness_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    readiness = readiness_item or {}
    grouped_units = readiness.get("source_units")  # IMP-416: only a change story carries its grouped units
    story_id = str(story.get("id", readiness.get("story_id", "")))
    story_type = str(readiness.get("type", "") or type_from_story_text(story_text))
    slicing = str(readiness.get("slicing", "") or slicing_from_story_text(story_text)).strip()
    source_unit = str(readiness.get("source_unit", ""))
    trace = [str(item) for item in readiness.get("trace", []) if str(item).strip()]
    dependencies = [str(item) for item in readiness.get("dependencies", []) if str(item).strip()]
    enables = [str(item) for item in readiness.get("enables", []) if str(item).strip()]
    ac_classes = {str(item.get("classification", "")).strip() for item in criteria}
    lowered = f"{story.get('title', '')} {story_text}".lower()
    has_behavior = any(term in lowered for term in BEHAVIOR_TERMS)
    layer_only = any(term in lowered for term in TECHNICAL_LAYER_TERMS) and not has_behavior
    is_enabler = story_type == "cross_cutting_enabler"
    is_pending = "[pending input]" in lowered or story_type == "pending"

    checks = [
        quality_check(
            "slicing_pattern_governed",
            slicing.startswith("Cross-Cutting Enabler /")
            or slicing
            in {
                "Workflow Step / Happy Path",
                "Rules / Regression Slice",
                "Data / External Dependency",
                "Interface / UX State",
                "Quality Evidence / Traceability",
            },
            "Story must use a governed INVEST/SPIDR/Lawrence slicing pattern.",
        ),
        quality_check(
            "vertical_slice",
            (is_enabler and bool(enables)) or (not is_enabler and not layer_only and has_behavior),
            "Story must describe end-to-end behavior or a concrete enabler boundary, not an isolated technical layer.",
        ),
        quality_check(
            "small_but_valuable",
            (is_enabler and bool(enables))
            or (
                not is_enabler
                and not is_pending
                and has_behavior
                and not layer_only
                and (source_unit.startswith("SPEC-U-") or any(item.startswith("SPEC-U") for item in trace))
            ),
            "Story must be small but still independently meaningful, testable and useful.",
        ),
        quality_check(
            "acceptance_criteria_coverage",
            REQUIRED_AC_CLASSES.issubset(ac_classes),
            "Acceptance criteria must cover fail-to-pass, pass-to-pass and evidence expectations.",
            observed=sorted(ac_classes),
        ),
        quality_check(
            "traceability_chain",
            bool(trace) and (is_enabler or any(item.startswith("SPEC-U") for item in trace + [source_unit])),
            "Traceability must connect the story to its SPEC-U/REQ evidence or concrete enabler evidence.",
            trace=trace,
        ),
        quality_check(
            "independent_dependencies",
            all("[PENDING" not in item for item in dependencies),
            "Dependencies must be explicit and must not hide a layer-only prerequisite.",
            dependencies=dependencies,
        ),
    ]
    passed = sum(1 for item in checks if item["passed"])
    score = round(passed / len(checks), 3) if checks else 0.0
    warnings = [str(item["warning"]) for item in checks if not item["passed"]]
    status = "PASS" if score >= 1.0 else "WARN" if score >= STORY_QUALITY_MIN_SCORE else "FAIL"
    verdict = "ready-for-handoff" if status == "PASS" else "review-before-handoff"
    signals = invest_audit(
        story,
        readiness,
        criteria=criteria,
        ac_classes=ac_classes,
        trace=trace,
        dependencies=dependencies,
        enables=enables,
        source_unit=source_unit,
        **(
            {"source_units": [str(item) for item in grouped_units], "max_units": story_size()}
            if isinstance(grouped_units, list)
            else {}
        ),
    )
    signal_count = sum(1 for item in signals.values() if item.get("passed"))
    return {
        "story_id": story_id,
        "score": score,
        "status": status,
        "verdict": verdict,
        "threshold": STORY_QUALITY_MIN_SCORE,
        "checks": checks,
        "warnings": warnings,
        "invest_audit": signals,
        "invest_audit_summary": {"passed": signal_count, "total": len(INVEST_SIGNAL_ORDER)},
    }


def invest_audit(
    story: dict[str, Any],
    readiness_item: dict[str, Any],
    *,
    criteria: list[dict[str, str]],
    ac_classes: set[str],
    trace: list[str],
    dependencies: list[str],
    enables: list[str],
    source_unit: str,
    source_units: list[str] | None = None,
    max_units: int | None = None,
) -> dict[str, dict[str, Any]]:
    story_type = str(readiness_item.get("type") or story.get("type") or "").strip()
    is_enabler = story_type == "cross_cutting_enabler"
    acceptance_ids = [str(item.get("id", "")).strip() for item in criteria if str(item.get("id", "")).strip()]
    upstream_trace = unique_strings(
        ([source_unit] if source_unit else [])
        + [item for item in trace if item.startswith(UPSTREAM_TRACE_PREFIXES)]
    )
    story_trace = [item for item in trace if item.startswith(STORY_REFERENCE_PREFIXES)]
    explicit_dependencies = [item for item in dependencies if item.strip()]
    pending_dependencies = [item for item in explicit_dependencies if "[PENDING" in item.upper()]
    readiness_score = float(readiness_item.get("readiness_score", 0.0) or 0.0)

    signals = {
        "I": invest_signal(
            "Independent",
            not explicit_dependencies and not story_trace and bool(upstream_trace or (is_enabler and enables)),
            "No prerequisite story or pending dependency is required to start this slice."
            if not explicit_dependencies and not story_trace and bool(upstream_trace or (is_enabler and enables))
            else "Structural coupling is still visible through prerequisite stories, explicit dependencies, or missing upstream anchors.",
            source_unit=source_unit,
            trace=trace,
            dependencies=explicit_dependencies,
            enables=enables,
        ),
        "N": invest_signal(
            "Negotiable",
            bool(acceptance_ids) and bool(upstream_trace or enables),
            "The story is framed as a traced outcome contract with acceptance coverage."
            if bool(acceptance_ids) and bool(upstream_trace or enables)
            else "Negotiability is weak because the story lacks traced outcome anchors or acceptance coverage.",
            trace=upstream_trace or trace,
            acceptance_ids=acceptance_ids,
            acceptance_classes=sorted(ac_classes),
        ),
        "V": invest_signal(
            "Valuable",
            bool(upstream_trace) or bool(enables),
            "Value is anchored to upstream requirements or to enabled downstream stories."
            if bool(upstream_trace) or bool(enables)
            else "No structural value anchor was found in upstream trace or enabled stories.",
            source_unit=source_unit,
            trace=upstream_trace,
            enables=enables,
        ),
        "E": invest_signal(
            "Estimable",
            bool(acceptance_ids) and not pending_dependencies and bool(upstream_trace or enables),
            "Scope, dependencies, and acceptance coverage are explicit enough to estimate."
            if bool(acceptance_ids) and not pending_dependencies and bool(upstream_trace or enables)
            else "Estimability is weakened by pending dependencies or a missing acceptance/trace contract.",
            trace=upstream_trace or trace,
            dependencies=explicit_dependencies,
            pending_dependencies=pending_dependencies,
            acceptance_classes=sorted(ac_classes),
            readiness_score=readiness_score,
        ),
        "S": small_signal(
            is_enabler, enables, source_unit, source_units, max_units, explicit_dependencies, upstream_trace
        ),
        "T": invest_signal(
            "Testable",
            REQUIRED_AC_CLASSES.issubset(ac_classes) and bool(acceptance_ids),
            "Classified acceptance criteria cover fail-to-pass, pass-to-pass, and evidence paths."
            if REQUIRED_AC_CLASSES.issubset(ac_classes) and bool(acceptance_ids)
            else "The acceptance contract is not yet rich enough to test this slice independently.",
            acceptance_ids=acceptance_ids,
            acceptance_classes=sorted(ac_classes),
        ),
    }
    return signals


def small_signal(
    is_enabler: bool,
    enables: list[str],
    source_unit: str,
    source_units: list[str] | None,
    max_units: int | None,
    explicit_dependencies: list[str],
    upstream_trace: list[str],
) -> dict[str, Any]:
    if source_units is not None:
        limit = max_units if max_units is not None else story_size()
        count = len(source_units)
        bounded = (is_enabler and bool(enables)) or 1 <= count <= limit
        passed = bounded and len(explicit_dependencies) <= 1
        finding = (
            f"The slice stays bounded to {count} unit(s) of one functionality, within the slicing model size ({limit})."
            if passed
            else f"The slice has {count} units, above the slicing model size ({limit})."
        )
        return invest_signal(
            "Small",
            passed,
            finding,
            source_unit=source_unit,
            source_units=source_units,
            dependencies=explicit_dependencies,
            enables=enables,
        )
    passed = (
        ((not is_enabler and bool(source_unit)) or (is_enabler and bool(enables)))
        and len(explicit_dependencies) <= 1
        and len(upstream_trace) <= 2
    )
    return invest_signal(
        "Small",
        passed,
        "The slice stays bounded to one upstream unit with limited prerequisite coupling."
        if passed
        else "The slice looks broad because upstream scope or prerequisite coupling is not tightly bounded.",
        source_unit=source_unit,
        trace=upstream_trace,
        dependencies=explicit_dependencies,
        enables=enables,
    )


def invest_signal(label: str, passed: bool, finding: str, **evidence: Any) -> dict[str, Any]:
    compact_evidence = {key: value for key, value in evidence.items() if value not in ("", [], {}, None)}
    return {
        "label": label,
        "passed": bool(passed),
        "finding": finding,
        "evidence": compact_evidence,
    }


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def type_from_story_text(text: str) -> str:
    match = re.search(r"\*\*Type:\*\*\s*(.+)", text)
    return match.group(1).strip() if match else ""


def quality_check(key: str, passed: bool, warning: str, **extra: Any) -> dict[str, Any]:
    item = {"key": key, "passed": bool(passed), "warning": "" if passed else warning}
    item.update(extra)
    return item


TEST_CASE_ES = {
    "title": "Casos de prueba", "project": "Proyecto", "source": "Historia de origen", "status": "Estado", "draft": "borrador",
    "matrix": "Matriz de cobertura", "step": "Paso de prueba", "criterion": "Criterio de aceptación",
    "row": "Paso de prueba", "notes": "Notas de automatización",
    "bullets": [
        "Preparar datos de entrada válidos para el camino feliz.",
        "Preparar datos de entrada faltantes e inválidos para los caminos de validación.",
        "Separar las verificaciones fail-to-pass, las de regresión pass-to-pass y las de evidencia cuando hay clasificaciones.",
        "Verificar que los IDs de trazabilidad sigan visibles en la cadena de artefactos.",
    ],
}


def render_test_case(project_id: str, story_id: str, criteria: list[str], language: str | None = None) -> str:
    """`language` None (the project) or "en": the bytes of 0.38.0; "es" (a change written in Spanish): headings and fixed copy in Spanish."""
    if language == "es":
        t = TEST_CASE_ES
        rows = "\n".join(f"| {t['row']} {criterion.split(':', 1)[0]} | {criterion} |" for criterion in criteria)
        bullets = "\n".join(f"- {line}" for line in t["bullets"])
        return f"""# {t['title']} - {story_id}

- {t['project']}: `{project_id}`
- {t['source']}: `{story_id}`
- {t['status']}: `{t['draft']}`

## {t['matrix']}

| {t['step']} | {t['criterion']} |
| --- | --- |
{rows}

## {t['notes']}

{bullets}
"""
    rows = "\n".join(f"| TC step {criterion.split(':', 1)[0]} | {criterion} |" for criterion in criteria)
    return f"""# Test Case Set - {story_id}

- Project: `{project_id}`
- Source story: `{story_id}`
- Status: `draft`

## Coverage Matrix

| Test Step | Acceptance Criterion |
| --- | --- |
{rows}

## Automation Notes

- Prepare valid input data for the happy path.
- Prepare missing and invalid input data for validation paths.
- Separate fail-to-pass checks, pass-to-pass regression checks, and evidence checks when classifications are present.
- Assert trace IDs remain visible in the artifact chain.
"""


AUDIT_ES = {
    "title": "Auditoría de preparación del backlog",
    "intro": "Esta auditoría revisa si los ítems del backlog están listos para la ejecución posterior, con la trazabilidad y el contexto de dominio de Sentinel vNext.",
    "verdict": "Veredicto",
    "census": "Censo de historias",
    "census_header": "| ID de historia | Título | Puntaje INVEST/SPIDR | Estado | Notas de revisión |",
    "no_warnings": "Sin advertencias INVEST/SPIDR.",
    "checks": "Verificaciones de calidad de las historias",
    "checklist": "Lista de auditoría",
    "check_items": [
        "Cada historia se evalúa contra el modelo de cortes INVEST/SPIDR/Lawrence gobernado.",
        "Cada historia se revisa por comportamiento de punta a punta o por un límite concreto de habilitador.",
        "La cobertura de criterios de aceptación revisa las expectativas fail-to-pass, pass-to-pass y de evidencia.",
        "La trazabilidad conecta historia -> SPEC-U/REQ o evidencia concreta del habilitador -> AC -> TC.",
        "La auditoría INVEST paralela muestra las señales estructurales Independent, Negotiable, Valuable, Estimable, Small y Testable sin cambiar el veredicto actual.",
        "Los hallazgos no bloquean por defecto y alimentan las advertencias de DoR en `state.json#story_gates`.",
    ],
}


def render_backlog_audit(
    project_id: str,
    stories: list[dict[str, str]],
    quality_results: dict[str, dict[str, Any]],
    language: str | None = None,
    change_id: str | None = None,
) -> str:
    """`language` None (the project): the bytes of 0.38.0; with a change the title carries `{pid} / {cid}`, in Spanish when the change is."""
    verdict = quality_audit_verdict(quality_results)
    es = language == "es"
    rows = "\n".join(render_audit_row(story, quality_results.get(story["id"], {}), es) for story in stories)
    detail_sections = "\n\n".join(
        render_story_quality_detail(story["id"], quality_results.get(story["id"], {}), es) for story in stories
    )
    scope = f"{project_id} / {change_id}" if change_id else project_id
    if es:
        t = AUDIT_ES
        checklist = "\n".join(f"- [x] {line}" for line in t["check_items"])
        return f"""# {t['title']} - {scope}

{t['intro']}

## {t['verdict']}

`{verdict}`

## {t['census']}

{t['census_header']}
| --- | --- | ---: | --- | --- |
{rows}

## {t['checks']}

{detail_sections}

## {t['checklist']}

{checklist}
"""
    return f"""# Backlog Readiness Audit - {scope}

This audit checks whether backlog items are ready for downstream execution using Sentinel vNext traceability and domain context.

## Verdict

`{verdict}`

## Story Census

| Story ID | Title | INVEST/SPIDR Score | Status | Review Notes |
| --- | --- | ---: | --- | --- |
{rows}

## Story Quality Checks

{detail_sections}

## Audit Checklist

- [x] Each story is evaluated against the governed INVEST/SPIDR/Lawrence slicing model.
- [x] Each story is checked for end-to-end behavior or a concrete enabler boundary.
- [x] Acceptance criteria coverage checks fail-to-pass, pass-to-pass, and evidence expectations.
- [x] Traceability checks connect story -> SPEC-U/REQ or concrete enabler evidence -> AC -> TC.
- [x] Parallel INVEST audit now surfaces structural signals for Independent, Negotiable, Valuable, Estimable, Small, and Testable without changing the current verdict.
- [x] Findings remain non-blocking by default and feed DoR warnings through `state.json#story_gates`.
"""


def quality_audit_verdict(quality_results: dict[str, dict[str, Any]]) -> str:
    if not quality_results:
        return "PARTIAL"
    statuses = {str(item.get("status", "")) for item in quality_results.values()}
    if statuses == {"PASS"}:
        return "PASS"
    if "FAIL" in statuses:
        return "ATTENTION"
    return "PARTIAL"


def quality_override_findings(quality_results: dict[str, dict[str, Any]]) -> list[str]:
    findings: list[str] = []
    for story_id, result in quality_results.items():
        status = str(result.get("status", "UNKNOWN"))
        warnings = [str(item) for item in result.get("warnings", []) if str(item).strip()]
        if warnings:
            findings.extend(f"{story_id}: {warning}" for warning in warnings)
        elif status != "PASS":
            findings.append(f"{story_id}: quality audit status is {status}.")
    return findings


def render_audit_row(story: dict[str, str], result: dict[str, Any], es: bool = False) -> str:
    none = AUDIT_ES["no_warnings"] if es else "No INVEST/SPIDR warnings."
    notes = "; ".join(result.get("warnings", [])) if result.get("warnings") else none
    return (
        f"| `{story['id']}` | {story.get('title', 'User story')} | "
        f"{float(result.get('score', 0.0)):.2f} | {result.get('status', 'UNKNOWN')} | {notes} |"
    )


def render_story_quality_detail(story_id: str, result: dict[str, Any], es: bool = False) -> str:
    checks = result.get("checks", []) if isinstance(result, dict) else []
    rows = "\n".join(
        f"| {item.get('key', '')} | {'PASS' if item.get('passed') else 'WARN'} | {item.get('warning') or 'OK'} |"
        for item in checks
        if isinstance(item, dict)
    )
    audit = result.get("invest_audit", {}) if isinstance(result, dict) else {}
    summary = result.get("invest_audit_summary", {}) if isinstance(result, dict) else {}
    invest_rows = render_invest_audit_rows(audit)
    if es:
        return f"""### {story_id}

| Verificación | Estado | Hallazgo |
| --- | --- | --- |
{rows or '| story_quality | WARN | No hubo una evaluación de calidad disponible. |'}

#### Auditoría INVEST paralela

Señales estructurales aprobadas: `{int(summary.get('passed', 0))}/{int(summary.get('total', len(INVEST_SIGNAL_ORDER)))}`.

| Letra | Señal | Estado | Hallazgo | Evidencia |
| --- | --- | --- | --- | --- |
{invest_rows}
"""
    return f"""### {story_id}

| Check | Status | Finding |
| --- | --- | --- |
{rows or '| story_quality | WARN | No quality evaluation was available. |'}

#### Parallel INVEST Audit

Passed `{int(summary.get('passed', 0))}/{int(summary.get('total', len(INVEST_SIGNAL_ORDER)))}` structural signals.

| Letter | Signal | Status | Finding | Evidence |
| --- | --- | --- | --- | --- |
{invest_rows}
"""


def render_invest_audit_rows(audit: dict[str, Any]) -> str:
    if not isinstance(audit, dict) or not audit:
        return "| - | INVEST audit | WARN | No parallel INVEST audit was available. | n/a |"
    rows: list[str] = []
    for letter, label in INVEST_SIGNAL_ORDER:
        item = audit.get(letter, {}) if isinstance(audit.get(letter, {}), dict) else {}
        rows.append(
            "| {letter} | {label} | {status} | {finding} | {evidence} |".format(
                letter=letter,
                label=label,
                status="PASS" if item.get("passed") else "WARN",
                finding=item.get("finding", "No finding."),
                evidence=render_invest_evidence(item.get("evidence", {})),
            )
        )
    return "\n".join(rows)


def render_invest_evidence(evidence: dict[str, Any]) -> str:
    if not isinstance(evidence, dict) or not evidence:
        return "n/a"
    parts: list[str] = []
    for key, value in evidence.items():
        if isinstance(value, list):
            if not value:
                continue
            rendered = ", ".join(f"`{item}`" for item in value)
        elif isinstance(value, float):
            rendered = f"{value:.2f}"
        else:
            text = str(value).strip()
            if not text:
                continue
            rendered = f"`{text}`"
        parts.append(f"{key}: {rendered}")
    return "; ".join(parts) if parts else "n/a"
