from __future__ import annotations

import importlib.util
import importlib.metadata
import os
import platform
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, NamedTuple

from .adapters import SKILL_TARGET_DIRS, manifest_command_names, runtime_command_names
from .memory import ContextBroker, active_embedder_status, embedder_diagnostics
from .portability import stdlib_purity_violations
from .core.io import remove, write_text


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
    "sentinel-views",
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
    "sentinel-prototype-manual",
    "sentinel-prototype-trace",
    "sentinel-quality",
    "sentinel-release-split",
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
        path_check(root, ".codex/skills", "canonical skills source (read by no agent; mirrored)"),
        path_check(root, ".agents/skills", "Agent Skills standard directory (Codex, Kilo)"),
        path_check(root, ".claude/skills", "Claude Code skills directory"),
        path_check(root, ".codex/hooks", "Codex hooks adapter"),
        path_check(root, ".kilo/agents", "Kilo Code agents adapter"),
        path_check(root, ".kilo/commands", "Kilo Code slash commands"),
        path_check(root, "kilo.jsonc", "Kilo Code repo config"),
        path_check(root, "CLAUDE.md", "Claude Code and Claude Desktop instructions"),
        path_check(root, "sentinel/templates/commands_manifest.json", "command adapter manifest"),
        command_surface_parity_check(),
        stdlib_purity_check(root),
        themes_check(root),
        vendored_mermaid_check(root),
        user_themes_check(root),
        project_ids_check(root),
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
        *skill_invocation_checks(root),
        skill_spec_compliance_check(root),
        tracked_secrets_check(root),
        workspaces_ignored_check(root),
        network_isolation_check(),
        skill_naming_check(root),
        claude_plugin_check(root),
        *kilo_agent_metadata_checks(root),
        *hook_governance_checks(root),
        launcher_exit_code_check(root),
        *agentic_surface_checks(root),
        *agentic_surface_audit_checks(root),
        *kilo_command_checks(root),
        kilo_command_allowlist_check(root),
        kilo_config_schema_check(root),
        kilo_governed_deny_check(root),
        claude_settings_schema_check(root),
        surface_contract_registry_check(root),
        command_description_neutrality_check(),
        *claude_command_checks(root),
        memory_dependency_check(),
        semantic_embedder_check(),
        lancedb_smoke_check(),
        memory_backend_mode_check(),
        optional_dependency_check("sentence_transformers"),
        mcp_dependency_check(),
        brief_schema_check(),
        brief_vocabulary_check(root),
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
        "commands": runtime_command_names(),
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


# IMP-224 (H12): the agentic surfaces this repo generates from single source.
# A `description` is the one string a user reads in the autocomplete of *every*
# surface, so naming one of them there is wrong on the other two. Word-bounded
# so ordinary prose never trips it.
_SURFACE_NAMES = re.compile(r"\b(?:kilo|claude|codex|cursor|gemini|vs ?code)\b", re.IGNORECASE)


def surface_leaks(text: str) -> list[str]:
    """Return the surface names leaked by a description mirrored to every agent.

    `CLAUDE.md`/`AGENTS.md`-style tokens are repo files a description may
    legitimately cite, not a claim about which agent is running, so a match
    immediately followed by `.md` does not count as a leak.
    """
    leaks: list[str] = []
    for match in _SURFACE_NAMES.finditer(text):
        if text[match.end() : match.end() + 3].lower() == ".md":
            continue
        leaks.append(match.group(0))
    return list(dict.fromkeys(leaks))


def command_description_neutrality_check() -> dict[str, str]:
    """IMP-224 (H12): no command `description` in the manifest may name a
    concrete surface. The manifest is single-source for `.claude/commands/` and
    `.kilo/commands/` alike, so `doctor` telling every agent it validates "this
    VS Code workspace" — and `sentinel` advertising "one generic Kilo workflow" —
    was wrong on two surfaces out of three. `skill_metadata_checks` has carried
    this invariant for skills since IMP-163; commands had no equivalent, which is
    exactly why the leak survived. WARN, in the molde of that sibling: the
    wording misleads, it does not break governance.
    """
    from .adapters import load_manifest

    label = "command descriptions stay surface-neutral"
    try:
        commands = load_manifest()["commands"]
    except (OSError, ValueError, KeyError) as exc:
        return {"name": label, "status": "WARN", "detail": f"unreadable manifest: {exc}"}
    offenders = [
        f"/{entry['name']} names {', '.join(leaks)}"
        for entry in commands
        if (leaks := surface_leaks(str(entry.get("description", ""))))
    ]
    if offenders:
        return {"name": label, "status": "WARN", "detail": "; ".join(offenders)}
    return {"name": label, "status": "PASS", "detail": f"{len(commands)} descriptions are agent-neutral"}


def skill_metadata_checks(root: Path) -> list[dict[str, str]]:
    """IMP-163: validate that every canonical skill carries usable metadata.

    The name+description frontmatter is the only triggering signal the
    generated surfaces (.claude/skills, .agents/skills) expose to a model, so
    a skill whose frontmatter is missing, unparseable, or mislabeled is
    silently invisible or mistargeted on every surface — the H5 audit found
    10 of 19 in that state while the existence-only check stayed green.
    Structural problems FAIL; agent-specific wording only WARNs.

    IMP-233 (H12): the label reads "skill metadata", not "Codex skill metadata".
    The file inspected is the canonical source, which no agent discovers; naming a
    single surface in a check that covers all three was the same doctrine error the
    labels of `codex_skill_checks` carried.
    """
    from .core.markdown import parse_frontmatter

    checks: list[dict[str, str]] = []
    for skill in REQUIRED_CODEX_SKILLS:
        label = f"skill metadata: {skill}"
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


# IMP-200 (H8, doc 40 §2): the sanctioned registry of skills that must NOT be
# auto-invoked by the model (`disable-model-invocation: true`). Default is auto;
# human-only is an explicit, conservative opt-in. `sentinel-privacy-local-first`
# is a deliberate deep reference — its non-negotiable rules are always-on in
# AGENTS.md/CLAUDE.md, so auto-loading the skill adds nothing and a human-invoked
# reference is the right posture. Keep this list minimal.
EXPECTED_HUMAN_ONLY_SKILLS = frozenset({"sentinel-privacy-local-first"})


def _skill_is_human_only(frontmatter: dict[str, Any]) -> bool:
    return str(frontmatter.get("disable-model-invocation", "")).strip().lower() == "true"


def skill_invocation_checks(root: Path) -> list[dict[str, str]]:
    """IMP-200 (H8, doc 40 §2): audit the human-only invocation flag that keeps a
    governance skill from being auto-loaded by the model. Two guarantees:

    * the set of canonical skills actually carrying `disable-model-invocation:
      true` matches `EXPECTED_HUMAN_ONLY_SKILLS` — a flag that creeps onto an
      unlisted skill, or drops off a listed one, FAILs (IMP-163 drift-guard
      spirit: the policy is explicit, not incidental);
    * for every sanctioned human-only skill the flag is coherent between the
      canonical `.codex/skills` source and each generated mirror (`skills_out_of_
      sync` already enforces byte-identity; this reports the flag directly so a
      regression names the invocation policy, not just "bytes differ").
    """
    from .core.markdown import parse_frontmatter

    checks: list[dict[str, str]] = []

    canonical_flagged: set[str] = set()
    for skill in REQUIRED_CODEX_SKILLS:
        path = root / ".codex" / "skills" / skill / "SKILL.md"
        if not path.exists():
            continue  # existence is already covered by codex_skill_checks/skill_metadata_checks
        if _skill_is_human_only(parse_frontmatter(path.read_text(encoding="utf-8-sig"))):
            canonical_flagged.add(skill)

    label = "skill invocation policy: human-only registry"
    missing = sorted(EXPECTED_HUMAN_ONLY_SKILLS - canonical_flagged)
    unexpected = sorted(canonical_flagged - EXPECTED_HUMAN_ONLY_SKILLS)
    if not missing and not unexpected:
        # IMP-232 (H12): name the reach of the policy. `disable-model-invocation`
        # is a Claude Code vendor field (AGENT_SKILL_VENDOR_FIELDS), so these
        # skills are human-only *there*; Codex and Kilo ignore the flag and can
        # still auto-load them. The rules themselves stay always-on via
        # AGENTS.md/CLAUDE.md, so the gap is scope of the flag, not governance.
        detail = "human-only: " + (", ".join(sorted(EXPECTED_HUMAN_ONLY_SKILLS)) or "none")
        detail += f" ({AGENT_SKILL_VENDOR_FIELDS['disable-model-invocation']})"
        checks.append({"name": label, "status": "PASS", "detail": detail})
    else:
        details = []
        if missing:
            details.append("missing disable-model-invocation flag: " + ", ".join(missing))
        if unexpected:
            details.append("unsanctioned human-only flag: " + ", ".join(unexpected))
        checks.append({"name": label, "status": "FAIL", "detail": "; ".join(details)})

    for skill in sorted(EXPECTED_HUMAN_ONLY_SKILLS):
        label = f"skill invocation coherence: {skill}"
        canonical = root / ".codex" / "skills" / skill / "SKILL.md"
        if not canonical.exists():
            checks.append({"name": label, "status": "FAIL", "detail": f".codex/skills/{skill}/SKILL.md missing"})
            continue
        if not _skill_is_human_only(parse_frontmatter(canonical.read_text(encoding="utf-8-sig"))):
            checks.append({"name": label, "status": "FAIL", "detail": "canonical no longer declares disable-model-invocation: true"})
            continue
        incoherent: list[str] = []
        for target in SKILL_TARGET_DIRS:
            mirror = root / target / skill / "SKILL.md"
            if not mirror.exists():
                incoherent.append(f"{target} missing")
            elif not _skill_is_human_only(parse_frontmatter(mirror.read_text(encoding="utf-8-sig"))):
                incoherent.append(f"{target} lacks the flag")
        if incoherent:
            checks.append({"name": label, "status": "FAIL", "detail": "; ".join(incoherent)})
        else:
            checks.append({"name": label, "status": "PASS", "detail": f"human-only coherent across {len(SKILL_TARGET_DIRS)} mirrors"})

    return checks


# IMP-232 (H12): the Agent Skills standard, verified against the published spec
# on 2026-07-26. Until now the only guarantees over our 24 skills were byte
# identity between mirrors (`skills_out_of_sync`) and name/description sanity
# (`skill_metadata_checks`); nothing checked the limits of the standard itself,
# so the skills passed by discipline rather than by enforcement.
AGENT_SKILL_STANDARD_FIELDS = frozenset(
    {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
)

# Vendor extensions must be declared here with the surface that honours them, so
# a field that only works on one agent can never enter silently. Every mirror is
# byte-identical, so a vendor field ships to all three surfaces regardless: what
# this registry records is where it actually *does* something.
AGENT_SKILL_VENDOR_FIELDS = {
    "disable-model-invocation": "Claude Code only; no-op in Codex and Kilo",
}

MAX_SKILL_NAME_LENGTH = 64
MAX_SKILL_DESCRIPTION_LENGTH = 1024
# Progressive-disclosure budget: a skill longer than this belongs in
# `references/`, which is the doctrine the standard's own layering encodes.
MAX_SKILL_LINES = 500
# Standard: lowercase alphanumerics in hyphen-separated segments — no leading,
# trailing or doubled hyphen, which `[a-z0-9]+(-[a-z0-9]+)*` already forbids.
_SKILL_NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def skill_spec_violations(root: Path) -> list[str]:
    """Validate every canonical skill against the Agent Skills standard.

    Deterministic and stdlib-only, in the spirit of the runtime purity guard.
    Scope is `.codex/skills` (the canonical source): the mirrors are already
    byte-identical by `skills_out_of_sync`, and scanning the directory rather
    than `REQUIRED_CODEX_SKILLS` means a skill added without registering it is
    still held to the spec. Deliberately does *not* re-check `name` == directory
    or non-empty metadata — those stay owned by `skill_metadata_checks`, so a
    single defect is reported once, by one check.
    """
    from .core.markdown import parse_frontmatter

    base = root / ".codex" / "skills"
    if not base.is_dir():
        return [".codex/skills: missing"]

    violations: list[str] = []
    for directory in sorted(item for item in base.iterdir() if item.is_dir()):
        skill = directory.name
        path = directory / "SKILL.md"
        if not path.exists():
            violations.append(f"{skill}: SKILL.md missing")
            continue
        text = path.read_text(encoding="utf-8-sig")
        frontmatter = parse_frontmatter(text)

        name = str(frontmatter.get("name", "")).strip()
        if len(name) > MAX_SKILL_NAME_LENGTH:
            violations.append(f"{skill}: name is {len(name)} chars (max {MAX_SKILL_NAME_LENGTH})")
        if name and not _SKILL_NAME_PATTERN.match(name):
            violations.append(f"{skill}: name '{name}' is not lowercase hyphen-separated")

        description = str(frontmatter.get("description", "")).strip()
        if len(description) > MAX_SKILL_DESCRIPTION_LENGTH:
            violations.append(
                f"{skill}: description is {len(description)} chars (max {MAX_SKILL_DESCRIPTION_LENGTH})"
            )

        lines = len(text.splitlines())
        if lines > MAX_SKILL_LINES:
            violations.append(f"{skill}: SKILL.md is {lines} lines (max {MAX_SKILL_LINES}); split into references/")

        unknown = sorted(
            set(frontmatter) - AGENT_SKILL_STANDARD_FIELDS - set(AGENT_SKILL_VENDOR_FIELDS)
        )
        if unknown:
            violations.append(f"{skill}: undeclared frontmatter field(s): {', '.join(unknown)}")

        for item in sorted(directory.rglob("*")):
            if not item.is_file():
                continue
            relative = item.relative_to(directory)
            if len(relative.parts) > 2:
                violations.append(f"{skill}: {relative.as_posix()} nests deeper than one reference level")

    return violations


# IMP-285: the repo itself must not carry secrets, and client workspaces must
# never be committed. Both read git's own view of the tree; without git (a zip
# download, a plugin cache) the checks degrade to WARN instead of guessing.
_MAX_SCANNED_BYTES = 1_000_000


def _git(root: Path, *args: str) -> "subprocess.CompletedProcess[str] | None":
    import subprocess

    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None


def tracked_secret_findings(root: Path) -> list[str] | None:
    from .secrets_scan import detect_secrets, load_allowlist

    listing = _git(root, "ls-files", "-z")
    if listing is None or listing.returncode != 0:
        return None
    allowlist = load_allowlist(root)
    findings: list[str] = []
    for name in sorted(item for item in listing.stdout.split("\0") if item):
        path = root / name
        try:
            if not path.is_file() or path.stat().st_size > _MAX_SCANNED_BYTES:
                continue
            text = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # binary or unreadable: not a text secret carrier
        for item in detect_secrets(text, allowlist):
            findings.append(f"{name}:{item.line} {item.type} ({item.short})")
    return findings


def tracked_secrets_check(root: Path) -> dict[str, str]:
    label = "tracked files carry no secrets"
    findings = tracked_secret_findings(root)
    if findings is None:
        return {"name": label, "status": "WARN", "detail": "not a git checkout (or git unavailable); tracked files not scanned"}
    if findings:
        return {"name": label, "status": "FAIL", "detail": "; ".join(findings[:20]) + (f"; +{len(findings) - 20} more" if len(findings) > 20 else "")}
    return {"name": label, "status": "PASS", "detail": "no private key, cloud key, JWT, token, URL credential or connection string in git ls-files"}


def workspaces_ignored_check(root: Path) -> dict[str, str]:
    """IMP-285 + IMP-212: new workspaces are ignored by default; versioning one is an explicit choice.

    A tracked file outside `_template/` and `.gitkeep` is a WARN, not a FAIL: in a
    private project repo the owner may un-ignore their workspace on purpose
    (`!workspaces/<ID>/`, see .gitignore), but in a public repo it is a leak.
    """
    label = "workspaces/ is ignored by git"
    probe = "workspaces/__sentinel_probe__/00_raw/source.md"
    result = _git(root, "check-ignore", "-q", "--no-index", probe)
    if result is None or result.returncode not in (0, 1):
        return {"name": label, "status": "WARN", "detail": "not a git checkout (or git unavailable); ignore rules not checked"}
    if result.returncode == 1:
        return {"name": label, "status": "FAIL", "detail": "a new workspace would be committable: keep the blanket `workspaces/*` rule in .gitignore"}
    tracked = _git(root, "ls-files", "workspaces")
    projects = sorted(
        {
            line.split("/")[1]
            for line in (tracked.stdout.splitlines() if tracked and tracked.returncode == 0 else [])
            if line.count("/") >= 2 and line.split("/")[1] != "_template"
        }
    )
    if projects:
        return {
            "name": label,
            "status": "WARN",
            "detail": f"versioned workspace(s): {', '.join(projects)} — fine in a private repo you own; never push them to a public one",
        }
    return {"name": label, "status": "PASS", "detail": "new workspaces are ignored; only _template/ is versioned"}


# IMP-284: zero network, verifiable. No module of the package may import a
# network library (stdlib or third-party HTTP clients), directly or through
# `importlib.import_module` / `__import__` with a literal name; `webbrowser`
# lives only behind `core/local_browser.py`, which opens existing local files.
NETWORK_MODULES = frozenset(
    {"socket", "urllib", "http", "ftplib", "smtplib", "ssl", "xmlrpc", "telnetlib", "poplib", "imaplib", "nntplib",
     "requests", "httpx", "aiohttp", "urllib3", "websockets", "websocket"}
)
BROWSER_MODULE_HOME = "core/local_browser.py"


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def network_import_violations(package_dir: Path) -> list[str]:
    import ast

    violations: list[str] = []
    for path in sorted(package_dir.rglob("*.py")):
        relative = path.relative_to(package_dir).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except (OSError, SyntaxError, ValueError) as exc:
            violations.append(f"{relative}: unparseable ({exc.__class__.__name__})")
            continue
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                func = node.func
                dynamic = (isinstance(func, ast.Name) and func.id == "__import__") or (
                    isinstance(func, ast.Attribute) and func.attr == "import_module"
                )
                if dynamic:
                    names = [node.args[0].value]
            for name in names:
                top = name.split(".")[0]
                if top in NETWORK_MODULES:
                    violations.append(f"{relative}:{node.lineno} imports {name} (network)")
                elif top == "webbrowser" and relative != BROWSER_MODULE_HOME:
                    violations.append(f"{relative}:{node.lineno} imports webbrowser (use core.local_browser.open_local_file)")
    return violations


def claude_plugin_check(root: Path) -> dict[str, str]:
    """IMP-279 (H14): the Claude Code marketplace and plugins are generated and valid.

    Two halves, both offline: the drift guard (the committed `plugins/` and
    `.claude-plugin/marketplace.json` equal a fresh `python -m sentinel.adapters
    --plugin`) and the subset of `claude plugin validate` this repo relies on. The
    authoritative `claude plugin validate --strict` runs in CI, which has network.
    """
    from .plugin_package import plugin_manifest_issues, plugin_out_of_sync

    label = "Claude Code plugin and marketplace"
    issues = plugin_manifest_issues(root)
    drift = plugin_out_of_sync(root)
    if drift:
        shown = "; ".join(drift[:5]) + (f"; ... {len(drift) - 5} more" if len(drift) > 5 else "")
        issues.append(f"out of sync, run `python -m sentinel.adapters --plugin`: {shown}")
    if issues:
        return {"name": label, "status": "FAIL", "detail": "; ".join(issues)}
    return {"name": label, "status": "PASS", "detail": "marketplace and 2 plugins valid and in sync with the generator"}


def network_isolation_check() -> dict[str, str]:
    label = "package imports no network module"
    package_dir = _package_dir()
    if not package_dir.is_dir():
        return {"name": label, "status": "WARN", "detail": f"package sources not on disk ({package_dir.as_posix()}); checked at build time"}
    violations = network_import_violations(package_dir)
    if violations:
        return {"name": label, "status": "FAIL", "detail": "; ".join(violations)}
    return {"name": label, "status": "PASS", "detail": "no socket/urllib/http/ftplib/smtplib/ssl or HTTP client imports; webbrowser only on file://"}


# IMP-277: naming convention and description best practices for distribution.
_SKILL_CONVENTION = re.compile(r"sentinel-[a-z0-9]+(?:-[a-z0-9]+)*\Z")
# Surface or vendor names never belong in a skill name: mirrors are byte-identical
# across surfaces, and in a plugin the namespace already says where it runs.
_SURFACE_WORDS = {"claude", "codex", "kilo", "copilot", "cursor", "gemini", "opencode", "windsurf", "vscode", "mcp"}
_TRIGGER = re.compile(r"Use (when|on|before)\b")
_NEGATIVE = re.compile(r"\bNot (for|needed)\b")


def skill_naming_violations(root: Path) -> list[str]:
    """IMP-277: `sentinel-<object>[-<action>]` names and descriptions that say when (not) to use them."""
    from .core.markdown import parse_frontmatter

    base = root / ".codex" / "skills"
    if not base.is_dir():
        return [".codex/skills: missing"]
    violations: list[str] = []
    for directory in sorted(item for item in base.iterdir() if item.is_dir()):
        path = directory / "SKILL.md"
        if not path.exists():
            continue  # reported by skill_spec_violations
        frontmatter = parse_frontmatter(path.read_text(encoding="utf-8-sig"))
        name = str(frontmatter.get("name", directory.name)).strip()
        if not _SKILL_CONVENTION.match(name):
            violations.append(f"{directory.name}: name '{name}' must be sentinel-<object>[-<action>] in kebab-case")
        surface = sorted(set(name.split("-")) & _SURFACE_WORDS)
        if surface:
            violations.append(f"{directory.name}: name carries a surface/vendor word ({', '.join(surface)}); skills run on every surface")
        description = str(frontmatter.get("description", "")).strip().strip('"')
        if not _TRIGGER.match(description):
            violations.append(f"{directory.name}: description must open with the trigger (\"Use when\", \"Use on\" or \"Use before\")")
        if not _NEGATIVE.search(description):
            violations.append(f"{directory.name}: description must say when NOT to use it (\"Not for ...\" or \"Not needed ...\")")
    return violations


def skill_naming_check(root: Path) -> dict[str, str]:
    label = "skill names and descriptions follow the convention"
    violations = skill_naming_violations(root)
    if violations:
        return {"name": label, "status": "FAIL", "detail": "; ".join(violations)}
    count = len([item for item in (root / ".codex" / "skills").iterdir() if item.is_dir()])
    return {"name": label, "status": "PASS", "detail": f"{count} skills named sentinel-<object>[-<action>] with trigger and Not-for clause"}


def skill_spec_compliance_check(root: Path) -> dict[str, str]:
    """IMP-232 (H12): report the Agent Skills spec verdict of
    `skill_spec_violations`. FAIL, not WARN: an over-long name, an oversize
    description or an undeclared frontmatter field is how a skill becomes
    invisible or gets rejected by a surface — structural, like the rest of
    `skill_metadata_checks`' FAIL branch, not a matter of wording.
    """
    label = "skill spec compliance (Agent Skills standard)"
    violations = skill_spec_violations(root)
    if violations:
        return {"name": label, "status": "FAIL", "detail": "; ".join(violations)}
    total = len([item for item in (root / ".codex" / "skills").iterdir() if item.is_dir()])
    vendor = ", ".join(f"{field} ({surface})" for field, surface in sorted(AGENT_SKILL_VENDOR_FIELDS.items()))
    return {"name": label, "status": "PASS", "detail": f"{total} skills valid; vendor fields: {vendor}"}


def kilo_agent_metadata_checks(root: Path) -> list[dict[str, str]]:
    """IMP-173: validate that every handcrafted Kilo agent carries usable
    frontmatter. These 7 agents are handcrafted (no generator), so the
    existence-only check left the same false-green gap IMP-163 closed for skills.
    Mirrors skill_metadata_checks.

    IMP-233 (H12): this docstring used to justify the agents with "Kilo has no
    skills". That is false — Kilo loads `.agents/skills/` by default, so the 24
    skills operate there too (see `KILO_DEFAULT_SKILL_DIRS` in `adapters.py`). The
    agents remain Kilo's mode/routing layer; what to do with the depth they
    duplicate is an open decision, not an established doctrine.
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


# IMP-199 (H8, doc 40 §2 — AgentShield local-first): deterministic denylist for
# the agentic-surface audit. Calibrated for ZERO false positives against our own
# legitimate hook/launcher commands — `python`/`py`/`pwsh`/`powershell`/`sh`
# invocations of the CLI and launchers, plus `git`/`gh` — so only unambiguously
# dangerous shell constructs match: recursive force-delete, a download piped
# straight into a shell, `eval`, `sudo`, and redirection to an absolute path
# outside the repo (excluding /dev/*).
_DANGEROUS_SHELL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("recursive force remove (rm -rf)", re.compile(r"\brm\s+-\S*r\S*f|\brm\s+-\S*f\S*r", re.IGNORECASE)),
    ("download piped to a shell (curl|wget -> sh)", re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|z)?sh\b", re.IGNORECASE)),
    ("shell eval", re.compile(r"\beval\b")),
    ("privilege escalation (sudo)", re.compile(r"\bsudo\b")),
    ("redirect to an absolute path outside the repo", re.compile(r">>?\s*(?!/dev/)(?:/[A-Za-z]|[A-Za-z]:[\\/])")),
)

# JSON keys whose values are human-facing prose (comments, agent prompts), not
# shell commands. They are still parse-checked, but excluded from the denylist
# sweep so a benign mention (e.g. discussing an `eval`) never trips a false WARN.
_PROSE_JSON_KEYS = frozenset({"_comment", "description", "prompt", "instructions", "note"})

# Matches JSONC comments and string literals so the stripper can drop the former
# while preserving the latter (a naive replace would corrupt a string with `//`).
_JSONC_COMMENT = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.DOTALL)


def _strip_jsonc(text: str) -> str:
    """Drop `//` and `/* */` comments (and JSONC trailing commas) so json.loads
    can parse a JSONC document, without corrupting string literals."""
    def _keep_strings(match: re.Match[str]) -> str:
        token = match.group(0)
        return token if token.startswith('"') else ""

    without_comments = _JSONC_COMMENT.sub(_keep_strings, text)
    return re.sub(r",(\s*[}\]])", r"\1", without_comments)


def _iter_command_strings(node: Any, skip_keys: frozenset[str]) -> list[str]:
    """Collect every string leaf of a parsed JSON document except those directly
    under a prose key (comments/prompts), which carry no shell commands."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in skip_keys and isinstance(value, str):
                continue
            found.extend(_iter_command_strings(value, skip_keys))
    elif isinstance(node, list):
        for item in node:
            found.extend(_iter_command_strings(item, skip_keys))
    elif isinstance(node, str):
        found.append(node)
    return found


def agentic_surface_audit_checks(root: Path) -> list[dict[str, str]]:
    """IMP-199 (H8, doc 40 §2): sweep the agentic config the framework itself
    ships and audit it for two failure modes IMP-177's file-specific checks do
    not cover systematically:

    * every hook/settings JSON (`.claude/`, `.codex/`) and the `kilo.jsonc`
      example must parse — an unparseable config silently disables governance
      (FAIL, molde IMP-177);
    * no command string inside them may contain an unambiguously dangerous shell
      construct (`_DANGEROUS_SHELL_PATTERNS`) — WARN citing file + pattern.

    Scope is deliberately *our own versioned surface* (doc 40 §4 seed #3): the
    gitignored `settings.local.json` (the BA's local bypass) and the user's own
    system are out of scope. Frontmatter name/description validity stays owned by
    IMP-163/173 and the verifier tool allowlist by IMP-177 — this check does not
    duplicate them. Zero network, zero LLM.
    """
    from .core.io import parse_json, read_json

    checks: list[dict[str, str]] = []

    targets: list[tuple[Path, str]] = []
    settings = root / ".claude" / "settings.json"
    if settings.exists():
        targets.append((settings, "json"))
    for hook_json in sorted((root / ".claude" / "hooks").glob("*.json")):
        targets.append((hook_json, "json"))
    for codex_json in sorted((root / ".codex").rglob("*.json")):
        if "__pycache__" in codex_json.parts:
            continue
        targets.append((codex_json, "json"))
    kilo = root / "kilo.jsonc"
    if kilo.exists():
        targets.append((kilo, "jsonc"))

    for path, kind in targets:
        label = f"agentic surface audit: {path.relative_to(root).as_posix()}"
        try:
            if kind == "jsonc":
                parsed = parse_json(_strip_jsonc(path.read_text(encoding="utf-8-sig")))
            else:
                parsed = read_json(path)
        except ValueError as exc:  # JSONDecodeError is a ValueError
            checks.append({"name": label, "status": "FAIL", "detail": f"unparseable {kind.upper()}: {exc}"})
            continue
        finding: tuple[str, str] | None = None
        for command in _iter_command_strings(parsed, _PROSE_JSON_KEYS):
            for pattern_label, pattern in _DANGEROUS_SHELL_PATTERNS:
                if pattern.search(command):
                    finding = (pattern_label, command.strip())
                    break
            if finding:
                break
        if finding:
            pattern_label, snippet = finding
            if len(snippet) > 80:
                snippet = snippet[:77] + "..."
            checks.append({"name": label, "status": "WARN", "detail": f"dangerous shell pattern — {pattern_label} — in: {snippet!r}"})
        else:
            checks.append({"name": label, "status": "PASS", "detail": str(path)})

    return checks


def write_check(root: Path) -> dict[str, str]:
    probe = root / ".sentinel_doctor_write_test"
    try:
        write_text(probe, "ok", root=root)
        remove(probe, root=root)
        return {"name": "repo write access", "status": "PASS", "detail": str(root)}
    except OSError as exc:
        return {"name": "repo write access", "status": "FAIL", "detail": str(exc)}


def brief_schema_check() -> dict[str, str]:
    """IMP-252: the brief v2 schema is well formed and its ids follow the append-only lock."""
    from .brief_schema import ids_lock_problems, schema_ids, validate_schema

    label = "brief v2 schema and id golden"
    try:
        problems = validate_schema() + ids_lock_problems()
    except Exception as exc:  # noqa: BLE001 - doctor reports, never raises
        return {"name": label, "status": "FAIL", "detail": f"unreadable: {exc}"}
    if problems:
        return {"name": label, "status": "FAIL", "detail": "; ".join(problems[:5])}
    return {"name": label, "status": "PASS", "detail": f"{len(schema_ids())} stable ids, none renumbered or reused"}


def brief_vocabulary_check(root: Path) -> dict[str, str]:
    """IMP-255: skills and mirrors write the v2 marker and the pending marks only in their canonical form."""
    from .brief_integrity import skill_vocabulary_problems

    label = "brief v2 marker and mark vocabulary in skills"
    problems = skill_vocabulary_problems(root)
    if problems:
        return {"name": label, "status": "FAIL", "detail": "; ".join(problems[:5])}
    return {"name": label, "status": "PASS", "detail": "canonical marker and marks only"}


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


def user_themes_check(root: Path) -> dict[str, str]:  # noqa: C901
    """IMP-241: user-local themes load, declare their provenance and do not shadow built-ins.

    Looks at ``~/.ignite/themes`` (or ``IGNITE_THEMES_DIR``) and every
    ``workspaces/*/.sentinel/themes``. Findings are WARN, never FAIL: these themes are
    the user's own and never part of the repo.
    """
    from .themes import ThemeError, list_builtin_themes, load_theme, theme_warnings, user_theme_dirs
    from .workspace import local_themes_rule_present

    name = "user-local themes"
    folders = list(user_theme_dirs())
    workspaces = root / "workspaces"
    findings: list[str] = []
    if workspaces.is_dir():
        for workspace in sorted(path for path in workspaces.iterdir() if path.is_dir()):
            local = workspace / ".sentinel" / "themes"
            folders.append(local)
            gitignore = workspace / ".gitignore"
            ignored = gitignore.is_file() and local_themes_rule_present(gitignore.read_bytes())
            if local.is_dir() and not ignored:
                findings.append(f"{workspace.name}: .sentinel/themes exists but the workspace .gitignore does not exclude .sentinel/ (re-run /init {workspace.name}: it only adds what is missing)")
    builtin = set(list_builtin_themes())
    count = 0
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            count += 1
            if path.stem in builtin:
                findings.append(f"{path.name} uses a built-in name and is ignored (built-ins always win)")
                continue
            try:
                theme = load_theme(path)
            except ThemeError as exc:
                findings.append(f"{path.name}: {str(exc).replace(str(path), path.name).replace(path.as_posix(), path.name)}")
                continue
            findings += [f"{path.name}: {warning}" for warning in theme_warnings(theme)]
    if findings:
        return {"name": name, "status": "WARN", "detail": "; ".join(findings)}
    return {"name": name, "status": "PASS", "detail": f"{count} local theme(s) valid" if count else "no local themes"}


VIEW_TEMPLATES = frozenset(
    {
        "shell.html", "shell.css", "shell.js",
        "dashboard-page.html", "dashboard.css", "dashboard.js",
        "view-page.html", "view-nav.html", "view.css", "view.js",
        "readiness-page.html", "readiness-nav.html", "readiness.css", "readiness.js",
        "diagrams.css", "diagrams.js",
    }
)


def vendored_mermaid_check(root: Path) -> dict[str, str]:
    """IMP-273: the vendored mermaid and its MIT notice match their pinned sha256.

    When the running package is a checkout's ``sentinel/`` both files must be there. A
    package that leaves the vendor out (the minimal ``.pyz``) passes, whatever ``--root``
    points at: the diagrams view shows the code unrendered.
    """
    from . import diagrams
    from .diagrams import MERMAID_VERSION, VENDOR_DIR

    name = "vendored mermaid"
    status, detail = diagrams.mermaid_status()
    if status == "ok":
        return {"name": name, "status": "PASS", "detail": f"mermaid {MERMAID_VERSION}, sha256 pinned (MIT notice present)"}
    package = Path(diagrams.__file__).resolve().parent
    checkout = package == (root / "sentinel").resolve() and (package / "diagrams.py").is_file()
    if status == "missing" and not checkout:
        return {"name": name, "status": "PASS", "detail": "not bundled: /view diagrams shows each diagram's code unrendered"}
    return {"name": name, "status": "FAIL", "detail": f"{detail} ({'/'.join(('sentinel',) + VENDOR_DIR)})"}


def project_ids_check(root: Path) -> dict[str, str]:
    """IMP-243: list existing workspaces whose folder name is not a valid PROJECT_ID.

    Commands now reject such ids, so these workspaces need renaming before use.
    ``_template`` is the runtime's own scaffold and is skipped.
    """
    from .core.io import parse_json
    from .core.paths import is_valid_project_id

    name = "workspace ids"
    workspaces = root / "workspaces"
    if not workspaces.is_dir():
        return {"name": name, "status": "PASS", "detail": "no workspaces"}
    folders = sorted(path for path in workspaces.iterdir() if path.is_dir() and path.name != "_template")
    findings: list[str] = []
    invalid = [path.name for path in folders if not is_valid_project_id(path.name)]
    if invalid:
        findings.append("rename to a valid PROJECT_ID (letters, digits, '_' or '-'; no Windows device names): " + ", ".join(invalid))
    escaping = [path.name for path in folders if path.resolve().parent != workspaces.resolve()]
    if escaping:
        findings.append("resolve outside workspaces/ (symlink or junction): " + ", ".join(escaping))
    by_fold: dict[str, list[str]] = {}
    for path in folders:
        by_fold.setdefault(path.name.casefold(), []).append(path.name)
    collisions = [names for names in by_fold.values() if len(names) > 1]
    if collisions:
        findings.append("differ only in letter case: " + "; ".join(", ".join(names) for names in collisions))
    mismatched = []
    for path in folders:
        state = path / "state.json"
        if state.is_file():
            try:
                declared = parse_json(state.read_text(encoding="utf-8")).get("project_id")
            except (ValueError, OSError, AttributeError):
                continue
            if declared and declared != path.name:
                mismatched.append(f"{path.name} (state.json says {declared!r})")
    if mismatched:
        findings.append("folder name and state.json project_id differ: " + ", ".join(mismatched))
    if findings:
        return {"name": name, "status": "WARN", "detail": "; ".join(findings)}
    return {"name": name, "status": "PASS", "detail": "all workspace ids are valid"}


def themes_check(root: Path, builtin: list[str] | None = None) -> dict[str, str]:
    """IMP-238: the checkout's ``sentinel/themes/`` holds only ``neutral`` and ``base.css``.

    Inspects ``<root>/sentinel/themes`` (falls back to the installed package when
    the root is not a framework checkout, e.g. a ``.pyz`` run). Any other theme or
    file type there (a brand theme, a logo) fails: brand themes live in a user's
    local theme directory (IMP-241), never in this public repo.
    """
    from .themes import DEFAULT_THEME, ThemeError, list_builtin_themes, load_theme, validate_theme

    name = "visual themes"
    allowed_files = {f"{DEFAULT_THEME}.json", "base.css"}
    themes_dir = root / "sentinel" / "themes"
    if builtin is not None:
        found = {f"{item}.json" for item in builtin} | {"base.css"}
    elif themes_dir.is_dir():
        found = {item.name for item in themes_dir.iterdir() if item.is_file()}
    else:
        found = {f"{item}.json" for item in list_builtin_themes()} | {"base.css"}
    extra = sorted(found - allowed_files)
    if extra:
        return {"name": name, "status": "FAIL", "detail": f"only {', '.join(sorted(allowed_files))} may ship in sentinel/themes/; found: {', '.join(extra)}"}
    missing = sorted(allowed_files - found)
    if missing:
        return {"name": name, "status": "FAIL", "detail": f"missing in sentinel/themes/: {', '.join(missing)}"}
    templates_dir = themes_dir / "templates"
    if builtin is None and templates_dir.is_dir():
        stray = sorted(item.name for item in templates_dir.iterdir() if item.is_file() and item.name not in VIEW_TEMPLATES)
        if stray:
            return {"name": name, "status": "FAIL", "detail": f"only the view templates may ship in sentinel/themes/templates/; found: {', '.join(stray)}"}
    target = themes_dir / f"{DEFAULT_THEME}.json" if builtin is None and themes_dir.is_dir() else DEFAULT_THEME
    try:
        theme = load_theme(target)
    except ThemeError as exc:
        return {"name": name, "status": "FAIL", "detail": str(exc)}
    # A path loads as a user theme (provenance optional); the repo theme must always declare it.
    provenance_errors = [error for error in validate_theme(theme, require_provenance=True) if "procedencia" in error]
    if provenance_errors:
        return {"name": name, "status": "FAIL", "detail": "; ".join(provenance_errors)}
    return {"name": name, "status": "PASS", "detail": f"built-in themes: {DEFAULT_THEME} (valid, light and dark)"}


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
    """Existence of every required skill at its canonical authoring path.

    IMP-233 (H12): the labels say "skill source", not "Codex skill". `.codex/skills`
    is discovery path for nobody — Codex reads `.agents/skills` — and a label that
    implied otherwise sent a maintainer debugging a missing skill to the wrong
    directory. The per-surface discovery table lives next to `SKILL_TARGET_DIRS`
    in `adapters.py`; `skills_out_of_sync` guards the mirrors themselves.
    """
    return [
        path_check(root, f".codex/skills/{skill}/SKILL.md", f"skill source: {skill}")
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


# Top-level keys published by Kilo's config schema (https://app.kilo.ai/config.json),
# snapshotted 2026-07-26 against Kilo Code 7.4.16. IMP-235 exists because nothing
# ever checked this: the file carried a `permissions` key for seven weeks and Kilo
# discarded the whole block while `/doctor` stayed green. A third-party schema can
# grow, so an unknown key is a WARN, not a FAIL — but it can no longer be silent.
KILO_CONFIG_TOP_LEVEL_KEYS = frozenset(
    {
        "$schema", "shell", "logLevel", "server", "command", "skills", "references",
        "reference", "watcher", "snapshot", "plugin", "share", "autoshare", "autoupdate",
        "disabled_providers", "enabled_providers", "model", "small_model", "default_agent",
        "subagent_depth", "username", "mode", "agent", "provider", "mcp", "formatter",
        "lsp", "instructions", "layout", "permission", "tools", "attachment", "enterprise",
        "tool_output", "compaction", "experimental",
        # VS Code extension additions
        "auto_expand_history", "remote_control", "auto_collapse_reasoning",
        "terminal_command_display", "code_edit_display", "hide_prompt_training_models",
        "commit_message",
    }
)
# Sub-keys of `permission` that accept a rule (an action, or a map of
# pattern -> action). The action-only siblings (`todowrite`, `question`,
# `webfetch`, `websearch`, `doom_loop`) take a bare action and no pattern map.
KILO_PERMISSION_RULE_KEYS = frozenset(
    {
        "read", "edit", "glob", "grep", "list", "bash", "task", "external_directory",
        "lsp", "skill", "notebook_read", "notebook_edit", "notebook_execute",
    }
)
KILO_PERMISSION_ACTION_KEYS = frozenset({"todowrite", "question", "webfetch", "websearch", "doom_loop"})
KILO_PERMISSION_ACTIONS = frozenset({"allow", "ask", "deny"})


def _kilo_config(root: Path) -> tuple[dict, str | None]:
    """Parse `kilo.jsonc`, returning (config, error). Shared by the Kilo checks."""
    from .core.io import parse_json

    path = root / "kilo.jsonc"
    if not path.exists():
        return {}, "kilo.jsonc missing"
    try:
        parsed = parse_json(_strip_jsonc(path.read_text(encoding="utf-8-sig")))
    except ValueError as exc:  # JSONDecodeError is a ValueError
        return {}, f"unparseable JSONC: {exc}"
    if not isinstance(parsed, dict):
        return {}, "kilo.jsonc is not a JSON object"
    return parsed, None


def kilo_command_allowlist_check(root: Path) -> dict[str, str]:
    """IMP-213 (H10, anti-staleness), re-pointed at the real schema by IMP-235:
    the Kilo config must pre-authorize every runtime command, or a new command
    silently costs the BA a prompt (the F-209-2 staleness the H10 audit found:
    13 commands, incl. /dashboard and /view, unlisted).

    The pre-authorization now lives in `permission.bash` as a map of command
    pattern -> action, so coverage is what matters, not one entry per command: a
    single `python -m sentinel *` covers the whole CLI and removes the staleness
    class by construction. This check therefore matches each runtime command
    against the patterns instead of grepping for its name. WARN, not FAIL: a gap
    costs a prompt, it does not break governance. Sibling `.kilo/commands/*.md`
    doc coverage stays owned by the manifest sync (out_of_sync).
    """
    label = "kilo.jsonc pre-authorizes the Sentinel CLI"
    parsed, error = _kilo_config(root)
    if error:
        return {"name": label, "status": "WARN", "detail": error}
    permission = parsed.get("permission")
    rules = permission.get("bash") if isinstance(permission, dict) else None
    patterns = [str(key) for key, action in rules.items() if action == "allow"] if isinstance(rules, dict) else []
    commands = sorted(runtime_command_names())
    # Probe the invocation the adapters actually emit, so a pattern that only
    # matches the bare command name does not look like coverage.
    missing = [
        command
        for command in commands
        if not any(
            _glob_matches(pattern, f"python -m sentinel /{command} PROJECT_ID", path_semantics=False)
            for pattern in patterns
        )
    ]
    if missing:
        return {"name": label, "status": "WARN", "detail": "not pre-authorized: " + ", ".join(f"/{command}" for command in missing)}
    return {"name": label, "status": "PASS", "detail": f"{len(commands)} commands pre-authorized"}


def _glob_matches(pattern: str, path: str, *, path_semantics: bool = True) -> bool:
    """Match a permission glob against a repo-relative path or a command line.

    Not `fnmatch`: there `*` crosses `/`, so a shallow `.agents/*.md` would count
    as covering `.agents/skills/x/references/y.md` — the exact false PASS this
    guard exists to catch. With `path_semantics` (the default) `*`/`?` stay inside
    a path segment and only `**` spans separators, which is how Kilo (and every
    other permission glob) reads them.

    IMP-235: `permission.bash` patterns are matched against a **command line**,
    not a path, and there `/` is an ordinary character — `python -m sentinel *`
    has to cover `python -m sentinel /doctor PROJECT_ID`. Pass
    `path_semantics=False` for those, so `*` is unrestricted.
    Case-sensitive by design in both modes: the verdict must not depend on the OS.
    """
    single = "[^/]" if path_semantics else "."
    parts: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if pattern[index + 1 : index + 2] == "*":
                parts.append(".*")
                index += 2
                continue
            parts.append(f"{single}*")
        elif char == "?":
            parts.append(single)
        else:
            parts.append(re.escape(char))
        index += 1
    return re.match("".join(parts) + r"\Z", path) is not None


def kilo_config_schema_check(root: Path) -> dict[str, str]:
    """IMP-235 (H12): the Kilo config must conform to the schema Kilo publishes.

    This replaces IMP-231's `kilo_skill_read_allowlist_check`, whose premise was
    false: `permissions.file.read` is not a key Kilo knows, so the allowlist it
    guarded never applied. Kilo's config is the opencode lineage — the extension
    declares SCHEMA = https://app.kilo.ai/config.json and rejects unknown
    top-level keys with `Unrecognized key: <name>`, which is how the defect was
    finally found: in the VS Code terminal, by eye, seven weeks after the fact.

    So this check guards the shape, not our intent: `$schema` must be declared
    (that is what makes the editor validate the file), every top-level key must
    be one the schema publishes, and inside `permission` every sub-key and every
    action must be known. Unknown keys are WARN rather than FAIL because a
    third-party schema can grow and this list is a snapshot — but they can no
    longer pass silently.

    What this check deliberately does NOT claim: that Kilo *enforces* the rules.
    A structural check over someone else's config is exactly what gave false
    confidence before. Enforcement is proven only by observing Kilo's behaviour
    with auto-approve off (doc 45 §3.2).
    """
    label = "kilo.jsonc conforms to Kilo's published schema"
    parsed, error = _kilo_config(root)
    if error:
        return {"name": label, "status": "WARN", "detail": error}
    problems: list[str] = []
    if "$schema" not in parsed:
        problems.append("no $schema declared (the editor cannot validate this file)")
    unknown = sorted(key for key in parsed if key not in KILO_CONFIG_TOP_LEVEL_KEYS)
    if unknown:
        problems.append("unrecognized top-level key(s): " + ", ".join(unknown))
    permission = parsed.get("permission")
    if permission is not None and not isinstance(permission, (str, dict)):
        problems.append("permission must be an action string or an object")
    elif isinstance(permission, str) and permission not in KILO_PERMISSION_ACTIONS:
        problems.append(f"permission action '{permission}' is not allow/ask/deny")
    elif isinstance(permission, dict):
        known = KILO_PERMISSION_RULE_KEYS | KILO_PERMISSION_ACTION_KEYS | {"*"}
        for key, rule in permission.items():
            if key not in known:
                problems.append(f"unrecognized permission sub-key: {key}")
                continue
            actions = rule.values() if isinstance(rule, dict) else [rule]
            if isinstance(rule, dict) and key in KILO_PERMISSION_ACTION_KEYS:
                problems.append(f"permission.{key} takes a bare action, not a pattern map")
            for action in actions:
                if action not in KILO_PERMISSION_ACTIONS:
                    problems.append(f"permission.{key}: '{action}' is not allow/ask/deny")
    if problems:
        return {"name": label, "status": "WARN", "detail": "; ".join(problems)}
    return {"name": label, "status": "PASS", "detail": f"{len(parsed)} top-level key(s), all published"}


def kilo_governed_deny_check(root: Path) -> dict[str, str]:
    """IMP-235 (H12): the Kilo config must declare a `deny` for every governed
    artifact glob, so the three surfaces protect the same set (the Claude
    `PreToolUse` hook and the Codex pre-tool-use policy already do).

    Scope of the claim, stated because IMP-235 exists precisely for over-claiming:
    this verifies the rule is **declared** in the shape Kilo publishes. It cannot
    verify Kilo enforces it — the schema documents no matching semantics for these
    patterns (glob syntax, relative vs absolute paths, precedence), and none is
    discoverable in the shipped extension. That is confirmed by behaviour, not
    here. WARN because the deterministic enforcement all surfaces share is the
    CLI itself; Kilo's config is defence in depth.
    """
    from .hooks_logic import GOVERNED_ARTIFACT_GLOBS

    label = "kilo.jsonc denies editing governed artifacts"
    parsed, error = _kilo_config(root)
    if error:
        return {"name": label, "status": "WARN", "detail": error}
    permission = parsed.get("permission")
    rules = permission.get("edit") if isinstance(permission, dict) else None
    denied = {str(key) for key, action in rules.items() if action == "deny"} if isinstance(rules, dict) else set()
    missing = [glob for glob in GOVERNED_ARTIFACT_GLOBS if glob not in denied]
    if missing:
        return {"name": label, "status": "WARN", "detail": "permission.edit does not deny " + ", ".join(missing)}
    return {"name": label, "status": "PASS", "detail": f"{len(GOVERNED_ARTIFACT_GLOBS)} governed globs denied"}


class SurfaceContract(NamedTuple):
    """One path in this repo that a third-party agent reads as configuration.

    `observed` is the ISO date on which a person watched the surface honour this
    file, or `""` when nobody ever has. It is maintainer-asserted: no check can
    confirm it (see `surface_contract_registry_check`).
    """

    surfaces: tuple[str, ...]
    live_check: str
    observed: str
    note: str = ""
    shipped: bool = True  # False = git-ignored and per-machine; the repo makes no claim about it


# IMP-236 (H12) — the registry of surface contracts.
#
# Why a constant and not a table in a document: our unit suite cannot cross the
# surface boundary. Nothing in it invokes Kilo Code, Claude Code or Codex — and
# nothing can, a unittest does not open VS Code — so every assertion about these
# paths has the form "our file says what we believe" and none has the form "the
# tool did what the file says". `kilo.jsonc` is the precedent: it carried a
# top-level `permissions` key Kilo does not recognize from 2026-06-03 to
# 2026-07-26, four items were built on top of it, `/doctor` stayed green the
# whole time, and one minimal manual check in Kilo found it in a minute. Every
# contract that ever had a live observation survived; the only one that never
# had one rotted. A Markdown table of this rots the same way — a constant a
# check guards does not.
SURFACE_CONTRACTS: dict[str, SurfaceContract] = {
    ".github/workflows": SurfaceContract(
        surfaces=("GitHub Actions",),
        live_check="Open a pull request and confirm both ci-fast and every ci-full job finish green in the PR's Checks tab (a workflow that parses proves nothing; IMP-246).",
        observed="2026-11-06",
        note="Read by GitHub, not by us: the only proof is a run observed on GitHub. First green run: PR #241, run 42260645975 (ci-fast + 5 ci-full jobs, real mcp 1.30.0 / 2.3.0 and lancedb 0.41.0).",
    ),
    ".github/dependabot.yml": SurfaceContract(
        surfaces=("GitHub Dependabot",),
        live_check="After merging, open Insights -> Dependency graph -> Dependabot: the `github-actions` ecosystem is listed with a recent successful check (or a grouped `ci` PR bumping a pinned SHA appears).",
        observed="",
        note="IMP-289. Read by GitHub, not by us: a file that parses proves nothing until Dependabot reports a run.",
    ),
    "AGENTS.md": SurfaceContract(
        surfaces=("Codex", "any agent honouring the AGENTS.md convention"),
        live_check="Start a Codex session at the repo root and confirm the operating rules are in context (ask it to state a non-negotiable rule it did not read from a file you named).",
        observed="",
    ),
    "CLAUDE.md": SurfaceContract(
        surfaces=("Claude Code", "Claude Desktop"),
        live_check="Start a Claude Code session at the repo root; the file is auto-loaded into the session context.",
        observed="2026-07-26",
    ),
    "CLAUDE.local.md": SurfaceContract(
        surfaces=("Claude Code",),
        live_check="Same session start as CLAUDE.md: the local file is loaded alongside it.",
        observed="2026-07-26",
        note="Git-ignored maintainer memory. Registered because Claude Code loads it, not because the repo ships it.",
        shipped=False,
    ),
    ".agents/skills": SurfaceContract(
        surfaces=("Codex", "Kilo Code"),
        live_check="Invoke `sentinel-backlog` on the surface and have it read `references/handoff-contracts.md`; the text must match the repo byte for byte.",
        observed="2026-07-26",
        note="Observed on both surfaces: Kilo Code lists the 24 skills and reads the `references/` layer; Codex surfaces them on `/`.",
    ),
    ".claude/agents": SurfaceContract(
        surfaces=("Claude Code",),
        live_check="`ignite-verifier` appears in the subagent list; with the opt-in PostToolUse hook enabled it runs after a Write/Edit on a governed artifact.",
        observed="",
        note="The hand-written inventory that motivated this registry listed 13 contracts and missed this one. Discovery below found it.",
    ),
    ".claude/commands": SurfaceContract(
        surfaces=("Claude Code",),
        live_check="Open a session whose folder is this repo, then type `/gap`: the command appears as `/gaps ... (project)`. Filter rather than scanning the raw `/` list — with plugins installed the project entries sit well below the built-ins.",
        observed="2026-07-26",
        note="Discovery reads `.claude/commands` under each workspace directory and the result is memoized per session, so a folder added to a session already running does not surface its commands until the session restarts. The first attempt failed that way and looked like a defect in the files, which were fine.",
    ),
    ".claude/hooks": SurfaceContract(
        surfaces=("Claude Code",),
        live_check="Attempt a Write/Edit on a governed artifact; the deny hook blocks it with an actionable message naming the owning command.",
        observed="2026-07-07",
        note="Observed by the IMP-178 smoke (H6). Same observation covers `.claude/settings.json`, which registers the hook.",
    ),
    ".claude/settings.json": SurfaceContract(
        surfaces=("Claude Code",),
        live_check="Same as `.claude/hooks`: if the deny fires, Claude Code read and applied this file.",
        observed="2026-07-07",
    ),
    ".claude/settings.local.json": SurfaceContract(
        surfaces=("Claude Code",),
        live_check="Per-machine file. A permission listed here stops prompting; the opt-in verifier hook enabled here fires after a governed Write/Edit.",
        observed="",
        note="Git-ignored, per-machine. Registered because Claude Code reads it; the repo cannot make a claim about its contents.",
        shipped=False,
    ),
    ".claude/skills": SurfaceContract(
        surfaces=("Claude Code",),
        live_check="In a session whose folder is this repo, the 24 `sentinel-*` skills are listed as available and scoped to this directory; invoking one loads SKILL.md and can read its `references/` layer.",
        observed="2026-07-26",
        note="Same discovery path and per-session memoization as `.claude/commands`.",
    ),
    ".claude-plugin/marketplace.json": SurfaceContract(
        surfaces=("Claude Code", "Codex"),
        live_check="In an empty project run `/plugin marketplace add jmatzkin1980/ignite-sentinel` and `/plugin install ignite-sentinel@ignite-sentinel`; `claude plugin list` shows ignite-sentinel enabled and ignite-sentinel-mcp disabled (IMP-279).",
        observed="2026-11-07",
        note="Observed with Claude Code 2.1.305 in an isolated CLAUDE_CONFIG_DIR, marketplace added from the local checkout: both plugins install, the MCP one disabled by default. `claude plugin validate --strict` passes on the root and both plugins. Generated by `python -m sentinel.adapters --plugin`. Codex also reads this file: with Codex CLI 0.142.4 (isolated CODEX_HOME, 2026-11-08) the marketplace adds and ignite-sentinel installs, but no plugin skill has been run in Codex, so the plugin is unsupported there (IMP-280, see user_guide/08-codex-adapter.md).",
    ),
    "plugins/ignite-sentinel": SurfaceContract(
        surfaces=("Claude Code",),
        live_check="After installing, `claude plugin details ignite-sentinel` lists 24 skills and 1 PreToolUse hook; `/ignite-sentinel:sentinel-views` writes the dashboard into the project, not the plugin; a hand Write to `workspaces/<id>/03_specs/*.md` is denied.",
        observed="2026-11-07",
        note="Observed: details shows Skills (24) and Hooks (1) PreToolUse. A skill run inside a signed-in session from the GitHub marketplace is still to be watched; the bundled runtime and hook are exercised from a copied plugin folder by tests/test_claude_plugin.py.",
    ),
    "plugins/ignite-sentinel-mcp": SurfaceContract(
        surfaces=("Claude Code",),
        live_check="`claude plugin enable ignite-sentinel-mcp@ignite-sentinel` with `mcp` installed; `/mcp` lists the ignite-sentinel server and `sentinel_doctor` answers.",
        observed="",
        note="Installs disabled by default (observed 2026-11-07). The enabled server has not been watched in a session yet.",
    ),
    ".codex/hooks": SurfaceContract(
        surfaces=("Codex",),
        live_check="Attempt a write to a governed artifact in Codex; `pre_tool_use_policy.py` must refuse it.",
        observed="",
    ),
    ".kilo/agents": SurfaceContract(
        surfaces=("Kilo Code",),
        live_check="Settings -> Agent Behaviour lists the agents as `custom` with the `description` verbatim from the file.",
        observed="2026-07-26",
    ),
    ".kilo/commands": SurfaceContract(
        surfaces=("Kilo Code",),
        live_check="Type `/` in Kilo Code: the commands appear and running one executes the CLI from the repo root.",
        observed="",
    ),
    ".kilocodeignore": SurfaceContract(
        surfaces=("Kilo Code",),
        live_check="Ask Kilo Code for a path this file excludes; it must not be read or indexed.",
        observed="",
    ),
    "kilo.jsonc": SurfaceContract(
        surfaces=("Kilo Code",),
        live_check="Open the repo in Kilo Code with auto-approve off: no `Configuration is invalid at kilo.jsonc` warning at startup, an edit to a governed artifact is stopped, an unlisted command asks and a listed one does not.",
        observed="2026-07-26",
        note="Enforcement confirmed by behaviour on 2026-07-26 with auto-approve off: no startup warning, the edit to a governed artifact stopped, an unlisted command asked and the pre-authorized CLI did not. Before that the block had been inert for seven weeks with /doctor green, which is why this registry exists.",
    ),
}

# Paths inside the surface roots that are NOT contracts, with the reason. Kept
# separate from the registry so "we own this" is a stated decision rather than
# an omission.
SURFACE_CONTRACT_EXEMPT: dict[str, str] = {
    ".codex/skills": "canonical authoring source read by no agent (IMP-233); mirrored byte-identical to .agents/skills and .claude/skills, which are the contracts",
    ".claude/worktrees": "session worktrees the Claude desktop app creates on a maintainer's machine (git-ignored scratch, not configuration any surface reads); IMP-246",
}

# Directories a third-party agent owns: every immediate child is a contract
# until stated otherwise. This is where surfaces actually grow (a new
# `.claude/output-styles/`, a new `.kilo/rules/`), so discovery here is
# exhaustive rather than curated.
SURFACE_CONTRACT_ROOTS = (".agents", ".claude", ".claude-plugin", ".codex", ".kilo", ".github", "plugins")

# Repo-root files agent tools read by convention. Unlike the directories above
# this list IS curated — a brand-new vendor's root file is only discovered once
# its name is added here — so it carries names we do not ship yet.
SURFACE_CONTRACT_ROOT_FILES = (
    "AGENTS.md", "CLAUDE.md", "CLAUDE.local.md", "GEMINI.md",
    "kilo.jsonc", "kilo.json", "opencode.jsonc", "opencode.json",
    ".kilocodeignore", ".cursorrules", ".windsurfrules", ".aiderignore", ".mcp.json",
)


def discover_surface_contracts(root: Path) -> list[str]:
    """Return the repo-relative paths that look like a third-party surface contract.

    Two sources: every immediate child of `SURFACE_CONTRACT_ROOTS` (exhaustive)
    and the curated `SURFACE_CONTRACT_ROOT_FILES` (only what is named). Dotfiles
    and `__pycache__` inside a surface root are tooling residue, not contracts.
    """
    found: list[str] = []
    for name in SURFACE_CONTRACT_ROOTS:
        base = root / name
        if not base.is_dir():
            continue
        for child in base.iterdir():
            if child.name.startswith(".") or child.name == "__pycache__":
                continue
            found.append(child.relative_to(root).as_posix())
    for name in SURFACE_CONTRACT_ROOT_FILES:
        if (root / name).exists():
            found.append(name)
    return sorted(found)


def surface_contract_registry_check(root: Path) -> dict[str, str]:
    """IMP-236 (H12): every surface contract in the repo must be registered with
    the live check that proves it, so adding one without saying how it is
    verified is visible instead of waiting for someone to trip over it.

    What this check can assert: that no path this repo hands to Kilo Code,
    Claude Code or Codex is missing from `SURFACE_CONTRACTS`, and that no
    registered path has silently disappeared.

    What it cannot assert, stated here because over-claiming is the exact defect
    that produced this item: **that an `observed` date is true.** Nothing in a
    Python process can confirm a person watched VS Code behave. The date is a
    maintainer's word; this check only guarantees there is a field to put it in
    and a procedure written next to it. Treat an entry with `observed=""` as
    "never verified", not as "verified and undated".

    WARN, not FAIL: an unregistered contract is a gap in method, and the
    lifecycle keeps working while it is open. It must be loud, not blocking.
    This is maintainer scope (the `workspaces/` two-audiences rule of IMP-212
    applies): a user who adds their own file under `.claude/` in their clone
    trips it too, so the detail points at MAINTAINERS.md rather than assuming
    the reader is evolving the framework.
    """
    label = "surface contracts are registered with a live check"
    discovered = discover_surface_contracts(root)
    unregistered = [
        path for path in discovered
        if path not in SURFACE_CONTRACTS and path not in SURFACE_CONTRACT_EXEMPT
    ]
    vanished = [
        path for path, contract in sorted(SURFACE_CONTRACTS.items())
        if contract.shipped and not (root / path).exists()
    ]
    problems: list[str] = []
    if unregistered:
        problems.append(
            "read by a third-party surface, with no live check declared (see MAINTAINERS.md, "
            "\"Surface contracts are verified in the tool\"): " + ", ".join(sorted(unregistered))
        )
    if vanished:
        problems.append("registered but absent from the repo: " + ", ".join(vanished))
    if problems:
        return {"name": label, "status": "WARN", "detail": "; ".join(problems)}
    never = sum(1 for contract in SURFACE_CONTRACTS.values() if not contract.observed)
    detail = f"{len(SURFACE_CONTRACTS)} contracts registered"
    if never:
        detail += f"; {never} never observed live (maintainer-asserted field, not machine-verifiable)"
    return {"name": label, "status": "PASS", "detail": detail}


# Published by SchemaStore, matched to `**/.claude/settings.json` in its catalog.
# IMP-236 looked for a vendor schema the way IMP-235 did with Kilo — in the
# shipped binary, not by assumption — and the verdict is written down because a
# negative result rots as fast as a positive one:
#   * Anthropic publishes NO settings-schema URL of its own. The Claude Code
#     2.1.208 binary references `anthropic.com/claude-code/plugin.schema.json`
#     for plugins and writes `schemastore.org/claude-code-keybindings.json` into
#     the keybindings file it generates, and has no settings equivalent.
#   * The settings parser DOES accept the key: its schema opens with
#     `$schema: A.string().optional().describe("JSON Schema reference for Claude
#     Code settings")`, and the object ends in `.passthrough()`, so declaring it
#     cannot invalidate the file.
#   * SchemaStore's catalog carries "Claude Code Settings" with fileMatch
#     `**/.claude/settings.json` and `additionalProperties: true` (our `_comment`
#     from IMP-179 stays valid). Community-maintained, not vendor-authoritative
#     — which is why the URL lives here with its provenance instead of being
#     mistaken for a vendor guarantee.
CLAUDE_SETTINGS_SCHEMA_URL = "https://www.schemastore.org/claude-code-settings.json"


def claude_settings_schema_check(root: Path) -> dict[str, str]:
    """IMP-236 (H12): `.claude/settings.json` must declare the published
    `$schema`, the same cheap signal IMP-235 added to `kilo.jsonc`.

    It is one line per file and it moves a whole class of failure — a key the
    tool does not recognize — from "silent for seven weeks" to "underlined in
    the editor while you type it". WARN: a missing declaration costs the editor
    hint, it does not break governance.
    """
    from .core.io import read_json

    label = "Claude settings declare the published $schema"
    path = root / ".claude" / "settings.json"
    if not path.exists():
        return {"name": label, "status": "WARN", "detail": ".claude/settings.json missing"}
    try:
        parsed = read_json(path)
    except ValueError as exc:  # JSONDecodeError is a ValueError
        return {"name": label, "status": "WARN", "detail": f"unparseable JSON: {exc}"}
    declared = parsed.get("$schema") if isinstance(parsed, dict) else None
    if declared == CLAUDE_SETTINGS_SCHEMA_URL:
        return {"name": label, "status": "PASS", "detail": CLAUDE_SETTINGS_SCHEMA_URL}
    if declared:
        return {"name": label, "status": "WARN", "detail": f"declares {declared}, expected {CLAUDE_SETTINGS_SCHEMA_URL}"}
    return {"name": label, "status": "WARN", "detail": f"no $schema declared; expected {CLAUDE_SETTINGS_SCHEMA_URL}"}


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
