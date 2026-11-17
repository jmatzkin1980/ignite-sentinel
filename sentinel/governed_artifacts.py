"""IMP-343: the one list of governed artifacts and the commands that own them.

A governed artifact changes only through a Sentinel command. Two guards read
this list, so they always agree:

- the deny hook (``sentinel.hooks_logic``) refuses an agent's hand Write/Edit of
  these files on Claude Code and Codex, and ``kilo.jsonc`` declares the same
  globs for Kilo Code;
- ``/health`` (``sentinel.protocols``) snapshots their checksums after each
  mutating command and flags a later hand edit (IMP-147, IMP-332).

Globs are relative to ``workspaces/PROJECT_ID/``. ``*`` matches one path
segment, so ``03_specs/*.md`` covers ``03_specs/prd.md`` and not
``03_specs/units/SPEC-U-001.md``. Raw drops, answer files and the JSON inputs
that commands read with ``--source`` or ``--analysis`` are not on the list:
the BA and the agent write those.

Stdlib only and import-free: the hook loads this on every Write/Edit.
"""

from __future__ import annotations

# (glob relative to the workspace, the commands that own the file)
GOVERNED_ARTIFACTS: tuple[tuple[str, str], ...] = (
    (
        "01_discovery/gaps.md",
        "`/ingest`, `/gaps` and `/resolve-gaps` (and the commands that add gaps, "
        "such as `/annotate`, `/challenge`, `/scrutinize`, `/harvest`, `/sync` and `/self-review`)",
    ),
    ("02_requirements/requirements.md", "`/ingest` and `/resolve-gaps`"),
    ("02_requirements/project-brief.md", "`/brief`"),
    ("03_specs/*.md", "`/specs` (and `/compose` for the PRD)"),
    ("04_backlog/*.md", "`/backlog`, `/refine-backlog` and `/story-status`"),
)

# Workspace-relative globs, in list order.
WORKSPACE_GLOBS: tuple[str, ...] = tuple(glob for glob, _ in GOVERNED_ARTIFACTS)
