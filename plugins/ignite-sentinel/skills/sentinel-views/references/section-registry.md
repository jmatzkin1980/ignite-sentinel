# Dashboard Section Registry

This reference is for maintainers extending `/dashboard` without letting the HTML drift from the runtime model. The dashboard is local-first, stdlib-only, read-only, and presentation-only. It must not mutate workspace state, call `/status` in a way that changes behavior, introduce network calls, or add mandatory dependencies.

## Runtime Map

- `sentinel/dashboard.py` is the dashboard runtime.
- `collect_dashboard_model(root=".")` scans `workspaces/*`, skips `_template` and entries without `state.json`, and builds the JSON model embedded in the HTML.
- `LIFECYCLE_STAGES` defines the readiness pipeline shown for every workspace.
- `SECTION_REGISTRY` declares which logical sections are exposed by the model and UI.
- `render_html(model)` renders the self-contained HTML snapshot.
- `generate_dashboard(root=".", open_browser=False)` writes `dashboard.html` and optionally opens it.

The source of truth for project facts remains each workspace plus the existing status model. Do not duplicate `/status` contracts or silently reinterpret lifecycle gates in the dashboard.

## Adding A Readiness Stage

1. Confirm the stage already exists in governed runtime state or can be derived from existing artifacts without mutation.
2. Add the stage to `LIFECYCLE_STAGES` with stable `key`, display label, order, and blocked/complete logic compatible with existing workspace state.
3. If the client-side pipeline has a mirrored step list in the HTML template, update it in the same patch.
4. Add or update a synthetic fixture in `tests/fixtures/dashboard/` so the new stage appears in both positive and blocked/empty states.
5. Extend `tests/test_dashboard.py` to assert the model and rendered HTML expose the stage.
6. Update user-facing docs when the stage changes how BA/PM users interpret readiness.

## Adding A Section

1. Add a small extractor or normalizer in `collect_dashboard_model`; prefer existing structured artifacts over parsing rendered Markdown.
2. Add a `Section(...)` entry to `SECTION_REGISTRY` with a stable key, user-facing title, source fields, visibility rule, and render type.
3. Keep empty or unavailable data explicit in the model, but hide purely empty UI sections with a `visible_when` rule.
4. If the section needs a new render type, add the smallest possible renderer in the HTML template and cover it with tests.
5. Include synthetic fixture data that proves the section handles normal, empty, and missing-artifact cases.
6. Document the interpretation in `user_guide/14-dashboard.md` when a BA/PM needs to act on the new section.

## Guardrails

- Preserve stdlib-only runtime. Do not add Jinja2, frontend build tooling, package managers, CDNs, or remote assets.
- Preserve local-first privacy. `dashboard.html` may contain embedded workspace markdown and must remain git-ignored.
- Preserve read-only behavior. The dashboard may suggest prompts and commands, but it must not execute mutating project commands.
- Preserve `/status`. Dashboard collection may reuse its public model but must not change `/status` output or semantics for this item.
- Keep the visual contract aligned with `docs/evolution/07-dashboard-prototype-reference.html` unless a later approved proposal supersedes it.
