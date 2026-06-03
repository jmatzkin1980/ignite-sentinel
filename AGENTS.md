# Ignite Sentinel vNext

## Working Agreements

- Treat this repository as a repo-local Codex framework for BA/Product requirements work in AI PODs.
- Keep the source of truth in versionable files under `workspaces/[PROJECT_ID]/`; memory indexes are retrieval aids only.
- Preserve traceability from raw input to requirements, gaps, decisions, specs, backlog, acceptance criteria, tests, and changes.
- Prefer small Codex skills with progressive disclosure: concise `SKILL.md`, deeper `references/`, reusable `assets/templates/`, deterministic scripts when possible.
- Do not reintroduce Roo-specific concepts such as `.roo`, `.roomodes`, `.roorules`, P3, or P5 as global architecture.

## Verification

- Run `python -m unittest discover -s tests` after changing Sentinel runtime code.
- If `python` is unavailable, use the bundled Codex Python runtime.
