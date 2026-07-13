from __future__ import annotations

import importlib.util
import importlib.metadata
import os
import platform
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from .adapters import manifest_command_names, runtime_command_names
from .memory import ContextBroker, active_embedder_status, embedder_diagnostics
from .portability import stdlib_purity_violations


REQUIRED_COMMANDS = [
    "doctor",
    "dashboard",
    "init",
    "ingest",
    "retrieve",
    "sync",
    "maturity",
    "specs",
    "backlog",
    "backlog-status",
    "quality",
    "health",
    "trace",
    "validate",
    "view",
    "reindex",
    "gaps",
    "annotate",
    "challenge",
    "scrutinize",
    "assume",
    "compose",
    "refine-backlog",
    "story-status",
    "resolve-gaps",
    "brief",
    "context-request",
    "status",
    "export",
]

REQUIRED_CODEX_SKILLS = [
    "sentinel-annotate",
    "sentinel-challenge",
    "sentinel-scrutiny",
    "sentinel-assume",
    "sentinel-compose",
    "sentinel-backlog",
    "sentinel-backlog-refine",
    "sentinel-brownfield-harvest",
    "sentinel-command-router",
    "sentinel-dashboard",
    "sentinel-discovery",
    "sentinel-domain-request",
    "sentinel-gap-response",
    "sentinel-handoff-datasets",
    "sentinel-health",
    "sentinel-implementation-feedback",
    "sentinel-intake-triage",
    "sentinel-maturity",
    "sentinel-privacy-local-first",
    "sentinel-project-brief",
    "sentinel-quality",
    "sentinel-self-review",
    "sentinel-specs",
    "sentinel-sync",
]

REQUIRED_CLAUDE_COMMANDS = manifest_command_names()

REQUIRED_KILO_COMMANDS = manifest_command_names()

REQUIRED_KILO_AGENTS = [
    "sentinel-backlog",
    "sentinel-discovery",
    "sentinel-health",
    "sentinel-maturity",
    "sentinel-quality",
    "sentinel-specs",
    "sentinel-sync",
]


def run_doctor(root: Path | None = None) -> dict[str, Any]:
    root = (root or Path.cwd()).resolve()
    checks = [
        python_check(),
        path_check(root, "sentinel", "core runtime"),
        path_check(root, "AGENTS.md", "Codex Desktop and agent instructions"),
        path_check(root, "README.md", "repository quick start"),
        path_check(root, ".codex/skills", "Codex skills adapter (canonical)"),
        path_check(root, ".agents/skills", "Agent Skills standard directory"),
        path_check(root, ".claude/skills", "Claude Code skills directory"),
        path_check(root, ".codex/hooks", "Codex hooks adapter"),
        path_check(root, ".kilo/agents", "Kilo Code agents adapter"),
        path_check(root, ".kilo/commands", "Kilo Code slash commands"),
        path_check(root, "kilo.jsonc", "Kilo Code repo config"),
        path_check(root, "CLAUDE.md", "Claude Code and Claude Desktop instructions"),
        path_check(root, "sentinel/templates/commands_manifest.json", "command adapter manifest"),
        command_surface_parity_check(),
        stdlib_purity_check(root),
        *docs_command_mentions_checks(root),
        dashboard_artifact_check(root),
        path_check(root, ".claude/commands", "Claude Code slash commands"),
        path_check(root, "user_guide", "user guide"),
        path_check(root, "user_guide/06-installation-vscode.md", "VS Code portable installation guide"),
        path_check(root, "user_guide/07-kilo-code-adapter.md", "Kilo Code adapter guide"),
        path_check(root, "user_guide/08-codex-adapter.md", "Codex adapter guide"),
        path_check(root, "user_guide/13-claude-adapter.md", "Claude adapter guide"),
        path_check(root, "installers/install.ps1", "Windows portable installer"),
        path_check(root, "installers/install.sh", "Unix portable installer"),
        path_check(root, "installers/sentinel.ps1", "Windows portable Sentinel launcher"),
        path_check(root, "installers/sentinel.sh", "Unix portable Sentinel launcher"),
        path_check(root, "input", "input folder scaffold"),
        path_check(root, "input/client_requirement", "input client requirement scaffold"),
        path_check(root, "input/technology_context", "input technology context scaffold"),
        path_check(root, "input/design_context", "input design context scaffold"),
        path_check(root, "input/interactions", "input interactions scaffold"),
        workspace_template_check(root),
        write_check(root),
        *codex_skill_checks(root),
        *skill_metadata_checks(root),
        *kilo_agent_metadata_checks(root),
        *hook_governance_checks(root),
        launcher_exit_code_check(root),
        *agentic_surface_checks(root),
        *kilo_command_checks(root),
        *claude_command_checks(root),
        memory_dependency_check(),
        semantic_embedder_check(),
        lancedb_smoke_check(),
        memory_backend_mode_check(),
        optional_dependency_check("sentence_transformers"),
        mcp_dependency_check(),
    ]
    blocking = [check for check in checks if check["status"] == "FAIL"]
    warnings = [check for check in checks if check["status"] == "WARN"]
    return {
        "verdict": "PASS" if not blocking else "FAIL",
        "root": str(root),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version.split()[0],
            "executable": sys.executable,
        },
        "commands": REQUIRED_COMMANDS,
        "checks": checks,
        "summary": {
            "failures": len(blocking),
            "warnings": len(warnings),
        },
    }


def python_check() -> dict[str, str]:
    if sys.version_info >= (3, 10):
        return {"name": "python>=3.10", "status": "PASS", "detail": sys.version.split()[0]}
    return {"name": "python>=3.10", "status": "FAIL", "detail": sys.version.split()[0]}


def path_check(root: Path, relative: str, label: str) -> dict[str, str]:
    path = root / relative
    return {
        "name": label,
        "status": "PASS" if path.exists() else "FAIL",
        "detail": str(path),
    }


def skill_metadata_checks(root: Path) -> list[dict[str, str]]:
    """IMP-163: validate that every canonical skill carries usable metadata.

    The name+description frontmatter is the only triggering signal the
    generated surfaces (.claude/skills, .agents/skills) expose to a model, so
    a skill whose frontmatter is missing, unparseable, or mislabeled is
    silently invisible or mistargeted on every surface — the H5 audit found
    10 of 19 in that state while the existence-only check stayed green.
    Structural problems FAIL; agent-specific wording only WARNs.
    """
    from .core.markdown import parse_frontmatter

    checks: list[dict[str, str]] = []
    for skill in REQUIRED_CODEX_SKILLS:
        label = f"Codex skill metadata: {skill}"
        path = root / ".codex" / "skills" / skill / "SKILL.md"
        if not path.exists():
            checks.append({"name": label, "status": "FAIL", "detail": "SKILL.md missing"})
            continue
        frontmatter = parse_frontmatter(path.read_text(encoding="utf-8-sig"))
        name = str(frontmatter.get("name", "")).strip()
        description = str(frontmatter.get("description", "")).strip()
        if not name or not description:
            status = "FAIL"
            detail = "frontmatter must parse with a non-empty name and description"
        elif name != skill:
            status = "FAIL"
            detail = f"frontmatter name '{name}' does not match directory '{skill}'"
        elif "codex" in description.lower():
            status = "WARN"
            detail = "description names a specific agent; keep it agent-neutral (mirrored to every surface)"
        else:
            status = "PASS"
            detail = str(path)
        checks.append({"name": label, "status": status, "detail": detail})
    return checks


def kilo_agent_metadata_checks(root: Path) -> list[dict[str, str]]:
    """IMP-173: validate that every handcrafted Kilo agent carries usable
    frontmatter. Kilo has no skills — these 7 agents are its model-facing depth —
    and they are handcrafted (no generator), so the existence-only check left the
    same false-green gap IMP-163 closed for skills. Mirrors skill_metadata_checks.
    """
    from .core.markdown import parse_frontmatter

    checks: list[dict[str, str]] = []
    for agent in REQUIRED_KILO_AGENTS:
        label = f"Kilo agent metadata: {agent}"
        path = root / ".kilo" / "agents" / f"{agent}.md"
        if not path.exists():
            checks.append({"name": label, "status": "FAIL", "detail": "agent file missing"})
            continue
        frontmatter = parse_frontmatter(path.read_text(encoding="utf-8-sig"))
        name = str(frontmatter.get("name", "")).strip()
        description = str(frontmatter.get("description", "")).strip()
        if not name or not description:
            status = "FAIL"
            detail = "frontmatter must parse with a non-empty name and description"
        elif name != agent:
            status = "FAIL"
            detail = f"frontmatter name '{name}' does not match file '{agent}'"
        else:
            status = "PASS"
            detail = str(path)
        checks.append({"name": label, "status": status, "detail": detail})
    return checks


def workspace_template_check(root: Path) -> dict[str, str]:
    """IMP-175 (E1): the versioned `workspaces/_template` scaffold must match the
    `WORKSPACE_DIRS` list that `/init` actually builds from — the single source of
    truth. Deriving the check from `WORKSPACE_DIRS` keeps the two from drifting
    (the audit found _template had lost `08_context_packs/requests`+`exports`)
    while `/doctor` path-checked a third, partial subset.
    """
    from .workspace import WORKSPACE_DIRS

    label = "workspace template scaffold"
    base = root / "workspaces" / "_template"
    if not base.is_dir():
        return {"name": label, "status": "FAIL", "detail": f"{base} missing"}
    missing = [relative for relative in WORKSPACE_DIRS if not (base / relative).is_dir()]
    if missing:
        return {"name": label, "status": "FAIL", "detail": "missing dirs vs WORKSPACE_DIRS: " + ", ".join(missing)}
    return {"name": label, "status": "PASS", "detail": f"{len(WORKSPACE_DIRS)} dirs match WORKSPACE_DIRS"}


# Catch the verb "patch"/"patching" in prose, not identifiers like `apply_patch`
# (a real tool name) or `dispatch` — the lookbehind rejects a preceding word char.
_HAND_EDIT_INVITATION = re.compile(r"manual artifact edits|(?<!\w)patch", re.IGNORECASE)
# Tools a read-only verifier agent must never hold. Its frontmatter allowlist and
# its declared denylist must not contradict each other.
_DANGEROUS_AGENT_TOOLS = ("Write", "Edit", "Bash", "Agent")


def hook_governance_checks(root: Path) -> list[dict[str, str]]:
    """IMP-177 (H1): content check for the Codex hooks + shared hook logic.

    IMP-172 extirpated the hand-edit/patching invitations and re-anchored the
    guardrail; the existence-only check could not tell if one crept back. FAIL if
    a forbidden invitation reappears in the hook surface.
    """
    checks: list[dict[str, str]] = []
    sources = sorted((root / ".codex" / "hooks").glob("*.py"))
    shared = root / "sentinel" / "hooks_logic.py"
    if shared.exists():
        sources.append(shared)
    for source in sources:
        label = f"hook governance: {source.name}"
        text = source.read_text(encoding="utf-8")
        if _HAND_EDIT_INVITATION.search(text):
            checks.append({"name": label, "status": "FAIL", "detail": "contains a hand-edit/patching invitation"})
        else:
            checks.append({"name": label, "status": "PASS", "detail": str(source)})
    return checks


def launcher_exit_code_check(root: Path) -> dict[str, str]:
    """IMP-177 (H1): the PowerShell launcher must propagate the CLI exit code
    (BUG G1, IMP-171). Without it, every gate is invisible to scripts/agents."""
    label = "launcher exit-code propagation"
    launcher = root / "installers" / "sentinel.ps1"
    if not launcher.exists():
        return {"name": label, "status": "FAIL", "detail": f"{launcher} missing"}
    if "exit $LASTEXITCODE" in launcher.read_text(encoding="utf-8"):
        return {"name": label, "status": "PASS", "detail": str(launcher)}
    return {"name": label, "status": "FAIL", "detail": "sentinel.ps1 no longer propagates `exit $LASTEXITCODE`"}


def agentic_surface_checks(root: Path) -> list[dict[str, str]]:
    """IMP-177 (doc 38 E2, local/deterministic agentic-surface audit): the opt-in
    hook example JSON must parse, and the read-only verifier agent's tools
    allowlist must not contain any tool its own denylist forbids.
    """
    from .core.io import read_json
    from .core.markdown import parse_frontmatter

    checks: list[dict[str, str]] = []

    example = root / ".claude" / "hooks" / "verify-governed-artifact.example.json"
    label = "agentic surface: hook example JSON parses"
    if not example.exists():
        checks.append({"name": label, "status": "FAIL", "detail": f"{example} missing"})
    else:
        try:
            read_json(example)
            checks.append({"name": label, "status": "PASS", "detail": str(example)})
        except ValueError as exc:  # JSONDecodeError is a ValueError
            checks.append({"name": label, "status": "FAIL", "detail": f"invalid JSON: {exc}"})

    agent = root / ".claude" / "agents" / "ignite-verifier.md"
    label = "agentic surface: verifier tool allowlist coherent"
    if not agent.exists():
        checks.append({"name": label, "status": "FAIL", "detail": f"{agent} missing"})
    else:
        text = agent.read_text(encoding="utf-8-sig")
        frontmatter = parse_frontmatter(text)
        allowed = {tool.strip() for tool in str(frontmatter.get("tools", "")).split(",") if tool.strip()}
        conflicts = sorted(allowed.intersection(_DANGEROUS_AGENT_TOOLS))
        if conflicts:
            checks.append({"name": label, "status": "FAIL", "detail": "allowlist grants denylisted tools: " + ", ".join(conflicts)})
        elif "Denylist" not in text:
            checks.append({"name": label, "status": "FAIL", "detail": "verifier no longer declares its denylist"})
        else:
            checks.append({"name": label, "status": "PASS", "detail": f"tools={sorted(allowed)}"})

    return checks


def write_check(root: Path) -> dict[str, str]:
    probe = root / ".sentinel_doctor_write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return {"name": "repo write access", "status": "PASS", "detail": str(root)}
    except OSError as exc:
        return {"name": "repo write access", "status": "FAIL", "detail": str(exc)}


def dashboard_artifact_check(root: Path) -> dict[str, str]:
    ignored = "dashboard.html" in (root / ".gitignore").read_text(encoding="utf-8") if (root / ".gitignore").exists() else False
    exists = (root / "dashboard.html").exists()
    if ignored:
        detail = "dashboard.html is ignored; " + ("local snapshot present" if exists else "snapshot will be generated on demand")
        return {"name": "dashboard.html local snapshot policy", "status": "PASS", "detail": detail}
    return {
        "name": "dashboard.html local snapshot policy",
        "status": "WARN",
        "detail": "dashboard.html is not listed in .gitignore; generated dashboards may expose embedded workspace content",
    }


def command_surface_parity_check(
    runtime: list[str] | None = None,
    manifest: list[str] | None = None,
) -> dict[str, str]:
    runtime_names = set(runtime_command_names() if runtime is None else runtime)
    manifest_names = set(manifest_command_names() if manifest is None else manifest) - {"sentinel"}
    missing_in_manifest = sorted(runtime_names - manifest_names)
    missing_in_runtime = sorted(manifest_names - runtime_names)
    if not missing_in_manifest and not missing_in_runtime:
        return {
            "name": "command surface parity",
            "status": "PASS",
            "detail": f"{len(runtime_names)} runtime commands match the command manifest",
        }
    details = []
    if missing_in_manifest:
        details.append("runtime only: " + ", ".join(missing_in_manifest))
    if missing_in_runtime:
        details.append("manifest only: " + ", ".join(missing_in_runtime))
    return {"name": "command surface parity", "status": "FAIL", "detail": "; ".join(details)}


def stdlib_purity_check(root: Path) -> dict[str, str]:
    package_dir = root / "sentinel"
    if not package_dir.exists():
        return {"name": "stdlib purity", "status": "FAIL", "detail": f"missing runtime package: {package_dir}"}
    violations = stdlib_purity_violations(package_dir)
    if not violations:
        return {
            "name": "stdlib purity",
            "status": "PASS",
            "detail": "runtime imports are stdlib, local, or guarded optional dependencies",
        }
    detail = "; ".join(violation.format() for violation in violations[:5])
    if len(violations) > 5:
        detail += f"; +{len(violations) - 5} more"
    return {"name": "stdlib purity", "status": "FAIL", "detail": detail}


DOC_COMMAND_MENTION_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "user_guide/01-command-reference.md",
)


def docs_command_mentions_checks(
    root: Path,
    commands: list[str] | None = None,
    docs: tuple[str, ...] = DOC_COMMAND_MENTION_FILES,
) -> list[dict[str, str]]:
    command_names = sorted(commands or runtime_command_names())
    checks: list[dict[str, str]] = []
    for relative in docs:
        path = root / relative
        if not path.exists():
            checks.append({"name": f"docs command mentions: {relative}", "status": "WARN", "detail": "document missing"})
            continue
        text = path.read_text(encoding="utf-8")
        missing = [command for command in command_names if f"/{command}" not in text]
        if missing:
            checks.append(
                {
                    "name": f"docs command mentions: {relative}",
                    "status": "WARN",
                    "detail": "missing " + ", ".join(f"/{command}" for command in missing),
                }
            )
        else:
            checks.append(
                {
                    "name": f"docs command mentions: {relative}",
                    "status": "PASS",
                    "detail": f"{len(command_names)} command tokens mentioned",
                }
            )
    return checks


def optional_dependency_check(module_name: str) -> dict[str, str]:
    found = importlib.util.find_spec(module_name) is not None
    detail = package_detail(module_name) if found else "not installed; JSON fallback remains usable"
    return {
        "name": f"optional dependency: {module_name}",
        "status": "PASS" if found else "WARN",
        "detail": detail,
    }


def codex_skill_checks(root: Path) -> list[dict[str, str]]:
    return [
        path_check(root, f".codex/skills/{skill}/SKILL.md", f"Codex skill: {skill}")
        for skill in REQUIRED_CODEX_SKILLS
    ]


def kilo_command_checks(root: Path) -> list[dict[str, str]]:
    return [
        path_check(root, f".kilo/commands/{command}.md", f"Kilo slash command: /{command}")
        for command in REQUIRED_KILO_COMMANDS
    ]


def claude_command_checks(root: Path) -> list[dict[str, str]]:
    return [
        path_check(root, f".claude/commands/{command}.md", f"Claude slash command: /{command}")
        for command in REQUIRED_CLAUDE_COMMANDS
    ]


def mcp_dependency_check() -> dict[str, str]:
    found = importlib.util.find_spec("mcp") is not None
    if found:
        detail = package_detail("mcp") + "; expose the lifecycle to MCP clients with `python -m sentinel.mcp`"
    else:
        detail = (
            "not installed; chat adapters and CLI remain fully functional. "
            "Enable the local stdio MCP server with `python -m pip install -e .[mcp]`."
        )
    return {
        "name": "optional dependency: mcp (local stdio server)",
        "status": "PASS" if found else "WARN",
        "detail": detail,
    }


def memory_dependency_check() -> dict[str, str]:
    found = importlib.util.find_spec("lancedb") is not None
    if found:
        detail = package_detail("lancedb")
    else:
        detail = (
            "local-restricted OK: lancedb is optional and not installed; "
            "deterministic json-hybrid memory is active and the full lifecycle works without pip installs. "
            "Enable vector retrieval with `python -m pip install -e .[memory]` only when the environment allows it."
        )
    return {
        "name": "memory dependency: lancedb (optional)",
        "status": "PASS" if found else "WARN",
        "detail": detail,
    }


def semantic_embedder_check() -> dict[str, str]:
    status = active_embedder_status()
    if status["semantic"]:
        return {
            "name": "memory embedder: semantic local (optional)",
            "status": "PASS",
            "detail": (
                f"{status['level']} active; dimensions={status['dimensions']}; "
                f"version={status['version']}"
            ),
        }
    detail = "semantic embedder not active; deterministic hash_embedding fallback is active. "
    try:
        diagnostics = embedder_diagnostics()
    except Exception:  # noqa: BLE001 - diagnosis is best-effort and must never break /doctor
        diagnostics = {"candidates": [], "recommendation": ""}
    reasons = "; ".join(
        f"{candidate.get('level')}: {candidate.get('outcome')}"
        for candidate in diagnostics.get("candidates", [])
        if candidate.get("outcome")
    )
    if reasons:
        detail += f"Candidates — {reasons}. "
    detail += diagnostics.get("recommendation") or (
        "Install optional local models with `python -m pip install -e .[memory-semantic]` "
        "and pre-seed the model cache or set SENTINEL_MODEL2VEC_MODEL / "
        "SENTINEL_SENTENCE_TRANSFORMERS_MODEL to a local model path."
    )
    return {
        "name": "memory embedder: semantic local (optional)",
        "status": "WARN",
        "detail": detail,
    }


def lancedb_smoke_check() -> dict[str, str]:
    if importlib.util.find_spec("lancedb") is None:
        return {
            "name": "LanceDB local open/create",
            "status": "WARN",
            "detail": "local-restricted OK: lancedb probe skipped because the optional package is not installed; json-hybrid mode is healthy",
        }
    try:
        import lancedb  # type: ignore

        with tempfile.TemporaryDirectory(prefix="sentinel_lancedb_doctor_") as temp_dir:
            db = lancedb.connect(temp_dir)
            db.create_table(
                "doctor_probe",
                data=[
                    {
                        "id": "probe",
                        "text": "local LanceDB probe",
                        "vector": [0.0, 1.0],
                    }
                ],
                mode="overwrite",
            )
        return {
            "name": "LanceDB local open/create",
            "status": "PASS",
            "detail": "local table probe succeeded",
        }
    except Exception as exc:
        return {
            "name": "LanceDB local open/create",
            "status": "FAIL",
            "detail": str(exc),
        }


def memory_backend_mode_check() -> dict[str, str]:
    if importlib.util.find_spec("lancedb") is None:
        return {
            "name": "memory backend mode",
            "status": "WARN",
            "detail": "json-hybrid; local-restricted OK; lancedb is optional and not installed",
        }
    old_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="sentinel_memory_backend_doctor_") as temp_dir:
        try:
            os.chdir(temp_dir)
            broker = ContextBroker("DOCTOR_MEMORY")
            if broker.lancedb_degraded_reason:
                return {
                    "name": "memory backend mode",
                    "status": "WARN",
                    "detail": f"{broker.backend}; degradation cause: {broker.lancedb_degraded_reason}",
                }
            return {
                "name": "memory backend mode",
                "status": "PASS",
                "detail": f"{broker.backend}; FTS index {'active' if broker.fts_ready else 'unavailable'}",
            }
        except Exception as exc:
            return {"name": "memory backend mode", "status": "WARN", "detail": str(exc)}
        finally:
            os.chdir(old_cwd)


def package_detail(module_name: str) -> str:
    try:
        version = importlib.metadata.version(module_name.replace("_", "-"))
        return f"available ({version})"
    except importlib.metadata.PackageNotFoundError:
        return "available"
