from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from .backlog.hooks import evaluate_backlog_privacy
from .gaps import blocking_severities, is_blocking, parse_gap_table
from .compilers.slicing import domain_context_snapshot
from .memory import ContextBroker
from .assumptions import assumptions_projection
from .drift import derived_drift_warnings
from .protocols import HAND_EDITS_DIR, evaluate_needs_context, hand_edited_artifacts, kept_hand_edits
from .core.graph import children_of, load_graph, parents_of
from .workspace import load_config, memory_path, read_json, state_path, update_state, workspace_path, write_json
from .core.io import write_text
from .core.markdown import parse_table_rows
from .core.paths import is_absolute_path, workspace_relative

METRIC_RE = re.compile(r"(\d+(?:[.,]\d+)?\s?%|\$\s?\d+)", re.I)


def run_health(project_id: str) -> dict[str, object]:
    base = workspace_path(project_id)
    collected = collect_health(project_id)
    findings, warnings = collected["findings"], collected["warnings"]
    broker, needs_context = collected["broker"], collected["needs_context_gate"]
    verdict = "CLEAN" if not findings else "DIRTY"
    assumption_projection = assumptions_projection(project_id)
    report_path = base / "06_traceability" / "health_report.md"
    write_text(report_path, render_health(project_id, verdict, findings, warnings))
    write_json(
        base / "06_traceability" / "health_report.json",
        {
            "verdict": verdict,
            "findings": findings,
            "warnings": warnings,
            "memory_backend": broker.backend,
            "memory_backend_degradation_reason": broker.lancedb_degraded_reason or None,
            "needs_context_gate": needs_context,
            "assumptions_projection": assumption_projection["summary"],
        },
    )
    update_state(project_id, health=verdict)
    return {
        "verdict": verdict,
        "findings": findings,
        "warnings": warnings,
        "remediated_by_backlog": collected["remediated_by_backlog"],
        "memory": str(memory_path(project_id)),
        "memory_backend": broker.backend,
        "memory_backend_degradation_reason": broker.lancedb_degraded_reason or None,
        "needs_context_gate": needs_context,
        "assumptions_projection": assumption_projection["summary"],
    }


def reconcile_change_only_health(project_id: str) -> str | None:
    """IMP-406: a workspace of changes has no project command that recomputes /health: do it when it is not CLEAN."""
    state = read_json(state_path(project_id), {})
    if str(state.get("health", "")).upper() == "CLEAN":
        return None
    return str(run_health(project_id)["verdict"])


def health_explanation(project_id: str) -> dict | None:
    """IMP-406: why health is not CLEAN and the command that clears it (writes nothing); None when it is CLEAN."""
    from .readiness_verdict import health_fix_step

    state = read_json(state_path(project_id), {})
    verdict = str(state.get("health", "")).upper()
    if verdict == "CLEAN":
        return None
    collected = collect_health(project_id)
    findings = list(collected["findings"])
    if findings:
        return {"verdict": verdict, "findings": findings[:5],
                **health_fix_step(project_id, health_fixes(project_id, collected))}
    return {"verdict": verdict, "findings": [], "title": "Health was never evaluated",
            "text": f"Nothing keeps health dirty: DIRTY is the state /init leaves until /health runs. Run /health {project_id}.",
            "command": f"/health {project_id}"}


def collect_health(project_id: str) -> dict:
    """The /health findings and warnings, computed without writing anything.

    IMP-360: `remediated_by_backlog` is the subset of findings that /backlog
    itself clears by regenerating its own artifacts; the preflight lets /backlog
    run when nothing else keeps health DIRTY.
    """
    base = workspace_path(project_id)
    graph = load_graph(project_id)
    findings: list[str] = []
    warnings: list[str] = []

    for node in graph.get("nodes", []):
        if node["type"] == "user_story" and not parents_of(project_id, node["id"]):
            findings.append(f"{node['id']} has no parent trace.")
        if node["type"] == "acceptance_criteria" and not parents_of(project_id, node["id"]):
            findings.append(f"{node['id']} has no parent user story.")

    gaps_path = base / "01_discovery" / "gaps.md"
    gaps_text = gaps_path.read_text(encoding="utf-8") if gaps_path.exists() else ""
    if gaps_text and has_blocking_open_gap(gaps_text, blocking_severities(load_config(project_id))):
        findings.append("Blocking gaps remain open.")

    # IMP-332: a raw source is immutable, so its unsourced metric is governed by
    # GAP-METRIC-SOURCE; once every such gap is closed the finding clears.
    raw_metrics_governed = metric_source_gaps_closed(gaps_text)
    for path in base.rglob("*.md"):
        parts = path.relative_to(base).parts
        if parts[0] == ".sentinel" or (parts[0] == "00_raw" and raw_metrics_governed):
            continue
        text = path.read_text(encoding="utf-8")
        if METRIC_RE.search(text) and not re.search(r"(source|fuente|baseline|measured|medido)", text, re.I):
            findings.append(f"Metric without explicit source detected in {path.name}.")

    broker = ContextBroker(project_id)
    memory = broker.data
    indexed_paths = {item["source_path"] for item in memory.get("artifacts", [])}
    for node in graph.get("nodes", []):
        # source_synthesis is deliberately never indexed (IMP-160): it is verbatim
        # citations of already-indexed raw sources, so absence from memory is by design.
        if node.get("path") and node["path"] not in indexed_paths and node["type"] not in {"acceptance_criteria", "source_synthesis"}:
            findings.append(f"{node['id']} is not indexed in memory.")
    findings.extend(graph_path_findings(project_id, graph))

    node_types = {node.get("type") for node in graph.get("nodes", [])}
    if "raw_input" in node_types and "identity_seed_bank" not in node_types:
        findings.append("Raw input exists without identity seeds.")
    if "raw_input" in node_types and "discovery_log" not in node_types:
        findings.append("Raw input exists without discovery log.")
    if "raw_input" in node_types and "lens_review" not in node_types:
        findings.append("Raw input exists without multi-lens critical review.")
    for req in [node for node in graph.get("nodes", []) if node.get("type") == "requirement"]:
        if not children_of(project_id, req["id"]):
            findings.append(f"{req['id']} has no downstream trace.")
    for story in [node for node in graph.get("nodes", []) if node.get("type") == "user_story"]:
        if not any(parent.startswith("EPIC-") for parent in parents_of(project_id, story["id"])):
            findings.append(f"{story['id']} is not linked to an epic.")
    warnings.extend(domain_context_freshness_findings(project_id, base))
    warnings.extend(out_of_cli_edit_warnings(project_id, base))
    warnings.extend(derived_drift_warnings(project_id))
    findings.extend(backlog_lifecycle_findings(project_id))
    staleness = knowledge_staleness_findings(project_id)
    findings.extend(staleness)
    # IMP-360: findings /backlog itself clears by regenerating its own artifacts.
    remediated_by_backlog = staleness if backlog_remediates_staleness(project_id) else []
    suspicious = suspicious_trace_link_findings(project_id)
    findings.extend(suspicious)
    # IMP-369: the semantic-change review clears by regeneration too; when only the
    # backlog artifacts are left, /backlog is the step that clears it.
    pending_review = pending_suspicious_links(project_id) if suspicious else None
    if pending_review and all(rel in BACKLOG_OWNED_ARTIFACTS for rel in pending_review["pending"]):
        remediated_by_backlog = [*remediated_by_backlog, *suspicious]
    privacy = backlog_privacy_findings(project_id)
    findings.extend(privacy["findings"])
    warnings.extend(privacy["warnings"])
    findings.extend(implementation_feedback_findings(project_id))

    # IMP-127: portable soft "needs-context" gate. Soft by default (warning);
    # strict opt-in escalates to a finding. Trigger is indexed volume, not LanceDB.
    needs_context = evaluate_needs_context(project_id, len(memory.get("chunks", [])))
    if needs_context["message"]:
        if needs_context["strict"]:
            findings.append(needs_context["message"])
        else:
            warnings.append(needs_context["message"])

    return {
        "findings": findings,
        "warnings": warnings,
        "remediated_by_backlog": remediated_by_backlog,
        "knowledge_staleness": staleness,
        "suspicious_trace_links": suspicious,
        "broker": broker,
        "needs_context_gate": needs_context,
    }


def graph_path_findings(project_id: str, graph: dict) -> list[str]:
    """IMP-301: every graph path lies inside the workspace and exists.

    Comparing the graph with memory is not enough: after a move both can carry
    the same stale path and agree.
    """
    findings: list[str] = []
    for node in graph.get("nodes", []):
        if not node.get("path"):
            continue
        stored = workspace_relative(project_id, node["path"])
        if is_absolute_path(stored):
            findings.append(f"{node['id']} points outside the workspace: {stored}. Move the file into the workspace and regenerate it.")
        elif not Path(node["path"]).exists():
            findings.append(f"{node['id']} points to a path that does not exist: {stored}.")
    return findings


def render_health(project_id: str, verdict: str, findings: list[str], warnings: list[str] | None = None) -> str:
    rows = "\n".join(f"- {finding}" for finding in findings) or "- No findings."
    warning_rows = "\n".join(f"- {warning}" for warning in (warnings or [])) or "- No warnings."
    return f"""# Health Report - {project_id}

- Verdict: `{verdict}`

## Findings

{rows}

## Warnings

{warning_rows}
"""


def out_of_cli_edit_warnings(project_id: str, base) -> list[str]:
    """IMP-147: warn when a governed artifact was edited outside the CLI.

    A mutating command is the only sanctioned writer of governed artifacts and
    snapshots their sha256 into `state.json#artifact_hashes` on postflight. Here
    we recompute the current hashes and compare: any file whose bytes differ
    from the last CLI-produced snapshot was edited by hand (or by a `Bash`
    write that bypassed the editor hooks of IMP-146). This is a persistent,
    cross-process/session check — unlike the in-memory optimistic-conflict
    snapshot of IMP-144, which only spans a single process. Purely
    deterministic hash comparison; it only warns, never blocks or reverts.
    """
    edited = hand_edited_artifacts(project_id)
    warnings = [
        f"Governed artifact edited outside the CLI: {rel}. "
        "Its bytes differ from the last command-produced version; revert the edit, or carry "
        "the change through the owning Sentinel command or /sync instead of hand-editing. "
        f"The next mutating command keeps a copy under {HAND_EDITS_DIR}/ before it may change the file."
        for rel in edited
    ]
    # IMP-332: a hand edit a later command changed stays reported while its copy exists.
    warnings.extend(
        f"Hand edit of {rel} was changed by a later command; the edited text is kept at {copy}. "
        "Carry the change through the owning Sentinel command or /sync, then delete that copy to clear this warning."
        for rel, copy in kept_hand_edits(project_id)
    )
    return warnings


def domain_context_freshness_findings(project_id: str, base) -> list[str]:
    readiness_path = base / "08_context_packs" / "implementation_readiness.json"
    backlog_path = base / "08_context_packs" / "backlog_generation.json"
    snapshot = {}
    if readiness_path.exists():
        readiness_pack = read_json(readiness_path, {})
        snapshot = readiness_pack.get("generated_from", {}).get("domain_context_snapshot", {})
    elif backlog_path.exists():
        backlog_pack = read_json(backlog_path, {})
        snapshot = backlog_pack.get("domain_context_snapshot", {})
    if not snapshot:
        return []

    current = domain_context_snapshot(project_id)
    if current.get("aggregate_hash") == snapshot.get("aggregate_hash"):
        return []
    changed_domains = sorted(
        domain
        for domain, payload in current.get("domains", {}).items()
        if payload.get("aggregate_hash") != snapshot.get("domains", {}).get(domain, {}).get("aggregate_hash")
    )
    detail = f" Changed domains: {', '.join(changed_domains)}." if changed_domains else ""
    return [
        "Domain context changed after backlog generation; run /reindex and retrieve focused context before implementation handoff. Regenerate backlog only if the change materially affects story scope, sequencing, acceptance, or execution contracts." + detail
    ]


def backlog_lifecycle_findings(project_id: str) -> list[str]:
    state = read_json(workspace_path(project_id) / "state.json", {})
    lifecycle = state.get("story_lifecycle", {})
    if not isinstance(lifecycle, dict):
        return []
    stale = sorted(story_id for story_id, item in lifecycle.items() if isinstance(item, dict) and item.get("status") == "Stale")
    if not stale:
        return []
    return ["Backlog contains Stale stories after source changes: " + ", ".join(stale) + "."]


# IMP-360: the downstream artifacts only /backlog rewrites, and the command that
# rewrites each of the others (workspace-relative paths).
BACKLOG_OWNED_ARTIFACTS = ("04_backlog/BACKLOG.md", "08_context_packs/implementation_readiness.json")
STALE_ARTIFACT_OWNERS = {
    "02_requirements/project-brief.md": "/brief",
    "03_specs/prd.md": "/specs",
    "03_specs/specs.md": "/specs",
    **{rel: "/backlog" for rel in BACKLOG_OWNED_ARTIFACTS},
}


def pending_stale_artifacts(project_id: str) -> list[str]:
    """Workspace-relative downstream artifacts still stale after the last knowledge change.

    The prescribed remediation is regenerating the listed artifacts: one
    regenerated strictly after the knowledge change (mtime > recorded_at) is
    refreshed and stops counting as stale. Markers without recorded_at
    (pre-fix workspaces) keep the conservative always-stale behavior.
    """
    base = workspace_path(project_id)
    state = read_json(base / "state.json", {})
    return _not_regenerated(project_id, state.get("knowledge_staleness", {}))


def _not_regenerated(project_id: str, payload: object) -> list[str]:
    """The `downstream_artifacts` of a marker not regenerated after its `recorded_at`."""
    if not isinstance(payload, dict):
        return []
    artifacts = [str(item) for item in payload.get("downstream_artifacts", []) if item]
    recorded_at = str(payload.get("recorded_at", ""))
    recorded_ns = payload.get("recorded_at_ns")  # I-1: sub-second stamp; older markers fall back to recorded_at
    pending = []
    for item in artifacts:
        path = Path(item)
        if recorded_at:
            if not path.exists():
                continue
            if isinstance(recorded_ns, int) and not isinstance(recorded_ns, bool):
                if path.stat().st_mtime_ns > recorded_ns:
                    continue
                pending.append(workspace_relative(project_id, item))
                continue
            mtime_iso = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat()
            if mtime_iso > recorded_at:
                continue
        pending.append(workspace_relative(project_id, item))
    return pending


def backlog_remediates_staleness(project_id: str) -> bool:
    """IMP-360: True when every stale downstream artifact is one only /backlog rewrites."""
    pending = pending_stale_artifacts(project_id)
    return bool(pending) and all(rel in BACKLOG_OWNED_ARTIFACTS for rel in pending)


def knowledge_staleness_findings(project_id: str) -> list[str]:
    state = read_json(workspace_path(project_id) / "state.json", {})
    payload = state.get("knowledge_staleness", {})
    if not isinstance(payload, dict):
        return []
    units = [str(item) for item in payload.get("impacted_knowledge_units", []) if item]
    if not pending_stale_artifacts(project_id):
        return []
    detail = f" Impacted knowledge units: {', '.join(units)}." if units else ""
    return [
        "Knowledge changed after downstream artifacts were generated; refresh affected brief/PRD/spec/backlog before implementation handoff."
        + detail
    ]


def pending_suspicious_links(project_id: str) -> dict | None:
    """IMP-369: the semantic-change review still pending, or None.

    A /sync whose note reads like a change of meaning ("now", "instead",
    "out of scope"...) flags the trace links of that change for BA review. Two
    things clear it: the BA records the review (`/trace --reviewed CHG-NNN`),
    or regenerates the downstream artifacts the change feeds (brief, PRD,
    specs, backlog) after it. Markers written before IMP-369 carry no
    `recorded_at`; only the review clears those.

    IMP-435 (A-01, Q1): regenerating alone no longer clears it: the documents are rebuilt from the same
    confirmed answers, so nothing of the change reached them. Only `/trace --reviewed CHG-NNN`, or an answer
    applied from that change followed by the regeneration, does. With everything regenerated and neither,
    it stays pending with an empty `pending` list.
    """
    state = read_json(workspace_path(project_id) / "state.json", {})
    payload = state.get("suspicious_trace_links", {})
    if not isinstance(payload, dict):
        return None
    links = [item for item in payload.get("links", []) if isinstance(item, dict)]
    if not links or payload.get("reviewed"):
        return None
    if payload.get("recorded_at"):
        pending = _not_regenerated(project_id, payload)
        if not pending and _answer_applied_from(project_id, str(payload.get("change_id") or "")):
            return None
    else:
        pending = [rel for rel in STALE_ARTIFACT_OWNERS if (workspace_path(project_id) / rel).exists()]
    return {"change_id": str(payload.get("change_id") or "latest change"), "links": links, "pending": pending,
            "legacy": not payload.get("recorded_at")}


def _answer_applied_from(project_id: str, change_id: str) -> bool:
    """IMP-435 (A-01): a confirmed gap answer (`### GAP-...`) was applied from this change: its row names the change as source."""
    if not change_id:
        return False
    base = workspace_path(project_id) / "01_discovery"
    text = "\n".join(path.read_text(encoding="utf-8") for path in (base / "identity_seeds.md", base / "decisions.md") if path.exists())
    return any(len(row) >= 5 and row[1].strip("` ").startswith("GAP-") and row[2].upper() == "CONFIRMED"
               and row[4].strip("` ") == change_id for row in parse_table_rows(text, skip_separator_rows=True))


def review_suspicious_links(project_id: str, change_id: str, reason: str = "") -> dict:
    """IMP-369: `/trace --reviewed CHG-NNN` records that the BA reviewed a semantic change.

    The BA read the trace links the change flagged and decided nothing
    downstream has to change (or already changed it). The review is stored in
    state.json and on each flagged edge of the graph (`review_status:
    reviewed`); the /health finding clears. Only the change /health names can
    be reviewed.
    """
    from .core.graph import load_graph, save_graph
    from .errors import InputError
    from .workspace import utc_now

    change_id = change_id.strip().upper()
    state = read_json(workspace_path(project_id) / "state.json", {})
    payload = state.get("suspicious_trace_links", {})
    links = payload.get("links", []) if isinstance(payload, dict) else []
    current = str(payload.get("change_id", "")) if isinstance(payload, dict) else ""
    if not links or payload.get("reviewed"):
        raise InputError(f"No semantic change is waiting for review (asked for {change_id}).",
                         next_step=f"Run /health {project_id} to see what keeps health DIRTY.")
    if change_id != current.upper():
        raise InputError(f"{change_id} is not the change waiting for review; /health names {current}.",
                         next_step=f"Run /trace {project_id} --reviewed {current}.")
    reviewed = {"at": utc_now(), "reason": reason.strip() or "BA reviewed the flagged trace links; nothing downstream changes."}
    graph = load_graph(project_id)
    edges = 0
    for edge in graph.get("edges", []):
        if edge.get("from") == current and edge.get("suspicious"):
            edge["review_status"] = "reviewed"
            edge["reviewed_at"] = reviewed["at"]
            edges += 1
    save_graph(project_id, graph)
    update_state(project_id, suspicious_trace_links={**payload, "reviewed": reviewed})
    return {"change_id": current, "reviewed_links": edges, **reviewed}


def regeneration_steps(pending: list[str], project_id: str | None = None) -> list[str]:
    """IMP-360/369: the commands that regenerate `pending` artifacts, in order, ending with /backlog.

    IMP-435 (A-13.3): without specs there is nothing to regenerate in a chain: `/specs` compiles the brief it needs, and
    `/brief` then `/backlog` would not reach the specs `/backlog` waits for."""
    steps = list(dict.fromkeys(STALE_ARTIFACT_OWNERS.get(rel, "/backlog") for rel in pending))
    if project_id and not (workspace_path(project_id) / "03_specs" / "specs.md").exists():
        return ["/specs", "/backlog"]
    order = ["/brief", "/specs"]
    return [step for step in order if step in steps] + ["/backlog"]


def suspicious_trace_link_findings(project_id: str) -> list[str]:
    pending = pending_suspicious_links(project_id)
    if pending is None:
        return []
    change_id = pending["change_id"]
    targets = ", ".join(str(item.get("to")) for item in pending["links"][:8] if item.get("to"))
    suffix = f" Targets: {targets}." if targets else ""
    chain = ", then ".join(regeneration_steps(pending["pending"], project_id))
    if not pending["pending"] and not pending.get("legacy"):
        return [
            f"Semantic change may invalidate downstream trace links for {change_id}; BA review required before "
            f"implementation handoff.{suffix} The documents were regenerated, but nothing of the change reached them. "
            f"Apply it as an answer (### GAP-...) and regenerate, or record the review with "
            f"/trace {project_id} --reviewed {change_id}."
        ]
    if pending.get("legacy"):
        return [
            f"Semantic change may invalidate downstream trace links for {change_id}; BA review required before "
            f"implementation handoff.{suffix} Review the targets, then record the review with "
            f"/trace {project_id} --reviewed {change_id}."
        ]
    return [
        f"Semantic change may invalidate downstream trace links for {change_id}; BA review required before implementation handoff."
        + suffix
        + f" Review the targets, then run {chain}; or, if nothing downstream has to change, record the review with "
        f"/trace {project_id} --reviewed {change_id}."
    ]


def backlog_privacy_findings(project_id: str) -> dict[str, list[str]]:
    result = evaluate_backlog_privacy(project_id)
    messages = [
        f"Backlog privacy scan finding in {item['path']}:{item['line']} ({item['pattern']})."
        for item in result["findings"]
    ]
    if result["verdict"] == "BLOCKED":
        return {"findings": messages, "warnings": []}
    return {"findings": [], "warnings": messages}


def implementation_feedback_findings(project_id: str) -> list[str]:
    state = read_json(workspace_path(project_id) / "state.json", {})
    payload = state.get("implementation_feedback", {})
    open_by_story = payload.get("open_by_story", {}) if isinstance(payload, dict) else {}
    if not isinstance(open_by_story, dict) or not open_by_story:
        return []
    return [
        "Open implementation feedback blocks DoD for "
        + ", ".join(f"{story} ({len(ids)})" for story, ids in sorted(open_by_story.items()))
        + "."
    ]


_NOT_INDEXED_RE = re.compile(r"^(\S+) is not indexed in memory\.$")
_STALE_STORIES_PREFIX = "Backlog contains Stale stories after source changes: "


def health_fixes(project_id: str, collected: dict | None = None) -> list[dict]:
    """IMP-369: each /health finding with the command that clears it, in the order to run them.

    One classification for the DIRTY gate of /backlog, /quality and
    /refine-backlog and for /next, so both name the same concrete next command.
    Each entry: `findings` (the /health lines it covers), `fix` (one sentence
    the BA reads) and `steps` (the commands, in order). The regeneration chain
    comes last and always ends with /backlog: it is what the DIRTY gate waits for.
    """
    collected = collected or collect_health(project_id)
    findings = list(collected["findings"])
    pid = project_id
    entries: dict[str, dict] = {}

    def add(key: str, rank: int, finding: str, fix: str, steps: list[str]) -> None:
        entry = entries.setdefault(key, {"kind": key.split("-")[0], "rank": rank, "findings": [], "fix": fix, "steps": steps})
        entry["findings"].append(finding)

    chain_findings = set(collected.get("knowledge_staleness", [])) | set(collected.get("suspicious_trace_links", []))
    pending: list[str] = []
    for finding in findings:
        if finding in chain_findings:
            continue
        if _NOT_INDEXED_RE.match(finding):
            add("reindex", 0, finding, f"Run /reindex {pid}.", [f"/reindex {pid}"])
        elif finding == "Blocking gaps remain open.":
            changes = _open_change_gaps(project_id)
            if changes:
                steps = [f"/gaps {pid} --id {gap} --disposition accepted|rejected" for gap in changes]
                add("gaps", 1, finding, f"Decide the late change{'s' if len(changes) > 1 else ''}: run "
                    + ", then ".join(steps) + ".", steps)
            else:
                fix, steps = blocking_gap_fix(project_id)
                add("gaps", 1, finding, fix, steps)
        elif finding.startswith("Open implementation feedback blocks DoD"):
            add("feedback", 2, finding, f"Record the decision on each finding with /implementation-feedback {pid} "
                "--source FILE (same id, status resolved).", [f"/implementation-feedback {pid} --source FILE"])
        elif finding.startswith(_STALE_STORIES_PREFIX):
            stories = [s.strip() for s in finding[len(_STALE_STORIES_PREFIX):].rstrip(".").split(",") if s.strip()]
            steps = [f"/story-status {pid} --story {story} --set Draft" for story in stories]
            add("stale", 3, finding, "Review each story against the change, then move it back: run "
                + ", then ".join(steps) + ".", steps)
        else:
            add(f"other-{len(entries)}", 4, finding,
                f"Fix it with the command that owns that artifact (never by hand); /health {pid} lists it.",
                [f"/health {pid}"])
    knowledge = [f for f in findings if f in set(collected.get("knowledge_staleness", []))]
    suspicious = [f for f in findings if f in set(collected.get("suspicious_trace_links", []))]
    if knowledge:
        pending += pending_stale_artifacts(project_id)
    review = pending_suspicious_links(project_id) if suspicious else None
    if review:
        pending += review["pending"]
    for entry in entries.values():
        entry["label"] = " ".join(entry["findings"])
    if knowledge or suspicious:
        pending = list(dict.fromkeys(pending))
        steps = regeneration_steps(pending, project_id)
        fix = "Run " + ", then ".join(steps) + "."
        labels = []
        if knowledge:
            stale = ", ".join(rel.rsplit("/", 1)[-1] for rel in pending_stale_artifacts(project_id))
            verb = "was" if len(pending_stale_artifacts(project_id)) == 1 else "were"
            labels.append(f"Knowledge changed after {stale} {verb} generated.")
        if review:
            targets = ", ".join(str(item.get("to")) for item in review["links"][:8] if item.get("to"))
            labels.append(f"Semantic change {review['change_id']} may invalidate downstream trace links"
                          + (f" (targets: {targets})." if targets else "."))
            fix = ("Review the targets, then " + fix[0].lower() + fix[1:]
                   + f" If nothing downstream has to change, record the review instead with "
                   f"/trace {pid} --reviewed {review['change_id']}.")
            if (review.get("legacy") or not review["pending"]) and not knowledge:
                # recorded before IMP-369 (regeneration cannot be dated against it), or regenerated without applying anything
                steps = [f"/trace {pid} --reviewed {review['change_id']}"]
                fix = (f"Review the targets, then record the review with /trace {pid} --reviewed {review['change_id']}"
                       + ("." if review.get("legacy") else "; or apply the change as an answer (### GAP-...) and regenerate."))
        entries["chain"] = {"kind": "review" if review and not knowledge else "chain", "rank": 5,
                            "findings": knowledge + suspicious, "label": " ".join(labels), "fix": fix,
                            "steps": steps, "pending": pending, "review": review}
    return [{k: v for k, v in entry.items() if k != "rank"}
            for entry in sorted(entries.values(), key=lambda e: e["rank"])]


def open_blocking_gaps(project_id: str) -> list[str]:
    """The ids of the blocking gaps still open in gaps.md, in the order the file lists them."""
    path = workspace_path(project_id) / "01_discovery" / "gaps.md"
    if not path.exists():
        return []
    blocking = blocking_severities(load_config(project_id))
    return [str(gap.get("id", "")).strip("`") for gap in parse_gap_table(path.read_text(encoding="utf-8"), include_legacy=True)
            if is_blocking(gap, blocking)]


def blocking_gap_fix(project_id: str) -> tuple[str, list[str]]:
    """IMP-435 (A-13): what closes each blocking gap: the brief settings are confirmed with /brief, the rest are the client's answers."""
    from .brief_schema import SETTINGS_GAP_ID, brief_settings_proposal

    from .core.text import project_language

    es = project_language(project_id) == "es"  # IMP-435 (M-2)
    pid = project_id
    ids = open_blocking_gaps(project_id)
    steps: list[str] = []
    parts: list[str] = []
    if SETTINGS_GAP_ID in ids:
        proposal = brief_settings_proposal(project_id)
        steps.append(f"/brief {pid} --profile {','.join(proposal['profiles'])} --genesis {proposal['genesis']}")
        parts.append(f"Confirmá los ajustes del brief ({SETTINGS_GAP_ID}): corré {steps[-1]}." if es
                     else f"Confirm the brief settings ({SETTINGS_GAP_ID}): run {steps[-1]}.")
    rest = [gap for gap in ids if gap != SETTINGS_GAP_ID]
    if rest or not steps:
        steps.append(f"/resolve-gaps {pid} --source ANSWERS")
        if es:
            parts.append((f"Cerrá {', '.join(rest)} " if rest else "Cerralos ")
                         + f"con las respuestas del cliente: corré /resolve-gaps {pid} --source ANSWERS.")
        else:
            parts.append((f"Close {', '.join(rest)} " if rest else "Close them ")
                         + f"with the client's answers: run /resolve-gaps {pid} --source ANSWERS.")
    return " ".join(parts), steps


def _open_change_gaps(project_id: str) -> list[str]:
    """Open GAP-CHG-* rows (IMP-337): late changes that wait for the BA, not the client."""
    path = workspace_path(project_id) / "01_discovery" / "gaps.md"
    if not path.exists():
        return []
    return sorted(
        str(gap.get("id", "")).strip("`") for gap in parse_gap_table(path.read_text(encoding="utf-8"), include_legacy=True)
        if str(gap.get("id", "")).strip("`").startswith("GAP-CHG-") and str(gap.get("status", "")).strip("`").upper() != "CLOSED"
    )


def metric_source_gaps_closed(gaps_text: str) -> bool:
    """IMP-332: True when gaps.md tracks GAP-METRIC-SOURCE and every such gap is CLOSED."""
    metric_gaps = [
        gap for gap in parse_gap_table(gaps_text, include_legacy=True)
        if str(gap.get("id", "")).strip("`").startswith("GAP-METRIC-SOURCE")
    ]
    return bool(metric_gaps) and all(str(gap.get("status", "")).strip("`").upper() == "CLOSED" for gap in metric_gaps)


def has_blocking_open_gap(text: str, severities: set[str] | None = None) -> bool:
    blocking = severities or blocking_severities({})
    for gap in parse_gap_table(text, include_legacy=True):
        if is_blocking(gap, blocking):
            return True
    return False
