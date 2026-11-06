"""IMP-239: /dashboard on the model -> validate -> render pipeline, common shell.

The model is reproducible (no clock, no absolute paths) and declares its
provenance: the cut-off date is the newest mtime among the sources read and
every state.json is fingerprinted with a 12-char sha256.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path

import re

from sentinel import themes
from sentinel.dashboard import DashboardModelError, collect_dashboard_model, render_dashboard, render_html, validate_dashboard_model
from sentinel.resources import package_resource
from tests.test_dashboard import DashboardFixtureMixin

FIXED_EPOCH = 1_781_481_600  # 2026-06-15T00:00:00Z
GOLDEN = Path(__file__).resolve().parent / "fixtures" / "golden" / "dashboard" / "portfolio.html"
UPDATE = os.environ.get("SENTINEL_UPDATE_GOLDEN") == "1"


def pin_mtimes(root, epoch: int = FIXED_EPOCH) -> None:
    for folder, _dirs, files in os.walk(root / "workspaces"):
        for name in files:
            os.utime(os.path.join(folder, name), (epoch, epoch))


class DashboardProvenanceTests(DashboardFixtureMixin, unittest.TestCase):
    def test_model_has_no_clock_or_absolute_root(self) -> None:
        model = collect_dashboard_model(self.temp)
        self.assertNotIn("generated_at", model)
        self.assertNotIn("root", model)
        self.assertNotIn(str(self.temp), json.dumps(model, ensure_ascii=False))

    def test_cutoff_is_newest_source_mtime(self) -> None:
        pin_mtimes(self.temp)
        newer = FIXED_EPOCH + 3600
        gaps = self.temp / "workspaces" / "DASH_CLIENT_WAIT" / "01_discovery" / "gaps.md"
        os.utime(gaps, (newer, newer))
        model = collect_dashboard_model(self.temp)
        expected = datetime.fromtimestamp(newer, timezone.utc).isoformat()
        self.assertEqual(model["provenance"]["cutoff"], expected)

    def test_every_state_json_is_fingerprinted(self) -> None:
        model = collect_dashboard_model(self.temp)
        sources = {item["path"]: item["sha256"] for item in model["provenance"]["sources"]}
        for project_id in ("DASH_BACKLOG_READY", "DASH_CLIENT_WAIT"):
            path = f"workspaces/{project_id}/state.json"
            digest = hashlib.sha256((self.temp / path).read_bytes()).hexdigest()[:12]
            self.assertEqual(sources[path], digest)

    def test_two_collections_are_identical(self) -> None:
        pin_mtimes(self.temp)
        first = json.dumps(collect_dashboard_model(self.temp), sort_keys=True)
        second = json.dumps(collect_dashboard_model(self.temp), sort_keys=True)
        self.assertEqual(first, second)

    def test_empty_portfolio_has_empty_provenance(self) -> None:
        model = collect_dashboard_model(self.temp / "nowhere")
        self.assertEqual(model["provenance"], {"cutoff": "", "sources": []})


class DashboardValidationTests(DashboardFixtureMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.model = collect_dashboard_model(self.temp)

    def test_collected_model_is_valid(self) -> None:
        self.assertEqual(validate_dashboard_model(self.model), [])

    def _errors(self, mutate) -> list[str]:
        model = copy.deepcopy(self.model)
        mutate(model)
        return validate_dashboard_model(model)

    def test_duplicate_workspace_ids(self) -> None:
        errors = self._errors(lambda m: m["workspaces"].append(copy.deepcopy(m["workspaces"][0])))
        self.assertTrue(any("duplicate workspace" in e for e in errors), errors)

    def test_duplicate_gap_ids(self) -> None:
        def mutate(m):
            ws = next(w for w in m["workspaces"] if w["gaps_detail"])
            ws["gaps_detail"].append(copy.deepcopy(ws["gaps_detail"][0]))

        errors = self._errors(mutate)
        self.assertTrue(any("duplicate gap" in e for e in errors), errors)

    def test_hand_written_kpi_is_rejected(self) -> None:
        errors = self._errors(lambda m: m["kpis"].__setitem__("blocking_gaps", 99))
        self.assertTrue(any("kpis.blocking_gaps" in e for e in errors), errors)

    def test_summary_open_gaps_must_match_counts(self) -> None:
        errors = self._errors(lambda m: m["workspaces"][0]["summary"].__setitem__("Gaps abiertos", 42))
        self.assertTrue(any("Gaps abiertos" in e for e in errors), errors)

    def test_missing_fingerprint_is_rejected(self) -> None:
        errors = self._errors(lambda m: m["provenance"]["sources"].pop())
        self.assertTrue(any("provenance" in e for e in errors), errors)

    def test_error_type_is_value_error(self) -> None:
        self.assertTrue(issubclass(DashboardModelError, ValueError))



class DashboardShellTests(DashboardFixtureMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        pin_mtimes(self.temp)
        self.model = collect_dashboard_model(self.temp)
        self.theme = themes.load_theme()
        self.html = render_dashboard(self.model, self.theme)

    def test_shell_accessibility_landmarks(self) -> None:
        self.assertIn('<a class="skip-link" href="#main">', self.html)
        self.assertIn('<main id="main"', self.html)
        self.assertRegex(self.html, r'<button class="shell-burger"[^>]*aria-controls="sidebar"[^>]*aria-expanded="false"')
        self.assertIn('id="sidebar"', self.html)

    def test_mode_toggle_persists_with_guarded_storage(self) -> None:
        self.assertIn('id="modeToggle"', self.html)
        self.assertIn("ignite-sentinel:color-mode", self.html)
        for match in re.finditer(r"localStorage", self.html):
            before = self.html[max(0, match.start() - 120) : match.start()]
            self.assertIn("try", before, "every localStorage access sits inside try/catch")

    def test_responsive_and_print_rules(self) -> None:
        self.assertIn("@media (max-width: 900px)", self.html)
        self.assertIn("@media print", self.html)

    def test_theme_in_both_modes(self) -> None:
        self.assertIn(themes.emit_root_css(self.theme), self.html)
        self.assertIn(':root[data-theme="dark"]', self.html)
        self.assertIn("prefers-color-scheme: dark", self.html)

    def test_legend_comes_from_theme_semantics(self) -> None:
        self.assertIn('id="legend"', self.html)
        self.assertIn(themes.legend_html(self.theme, "es"), self.html)

    def test_provenance_section(self) -> None:
        provenance = self.model["provenance"]
        self.assertIn('id="provenance"', self.html)
        self.assertIn(provenance["cutoff"], self.html)
        for source in provenance["sources"]:
            self.assertIn(source["sha256"], self.html)
        self.assertIn("python -m sentinel /dashboard --theme neutral", self.html)

    def test_sidebar_lists_workspaces(self) -> None:
        for project_id in ("DASH_BACKLOG_READY", "DASH_CLIENT_WAIT"):
            self.assertIn(f'data-open-ws="{project_id}"', self.html)

    def test_existing_sections_survive(self) -> None:
        for needle in ("Ignite Sentinel - Workspaces", "dashboard-data", "section-registry", "mdToHtml", "openDrawer", "Project Brief"):
            self.assertIn(needle, self.html)

    def test_no_external_urls(self) -> None:
        self.assertNotRegex(self.html, r"https?://|@import|url\(")

    def test_view_stylesheets_use_only_theme_tokens(self) -> None:
        for name in ("shell.css", "dashboard.css"):
            css = package_resource("themes", "templates", name).read_text(encoding="utf-8")
            self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", css), [], name)

    def test_custom_theme_is_applied(self) -> None:
        theme = copy.deepcopy(self.theme)
        theme["tokens"]["light"]["--bg"] = "#FAFAF0"
        self.assertIn("--bg:#FAFAF0", render_dashboard(self.model, theme))

    def test_invalid_model_is_not_rendered(self) -> None:
        model = copy.deepcopy(self.model)
        model["kpis"]["total"] = 7
        with self.assertRaises(DashboardModelError):
            render_dashboard(model, self.theme)

    def test_render_html_alias_uses_neutral(self) -> None:
        self.assertEqual(render_html(self.model), self.html)

    def test_two_renders_are_byte_identical(self) -> None:
        again = render_dashboard(collect_dashboard_model(self.temp), themes.load_theme())
        self.assertEqual(self.html, again)



class DashboardGoldenTests(DashboardFixtureMixin, unittest.TestCase):
    """Byte-for-byte snapshot of the portfolio fixture with pinned mtimes."""

    def test_portfolio_matches_golden(self) -> None:
        pin_mtimes(self.temp)
        html = render_dashboard(collect_dashboard_model(self.temp), themes.load_theme())
        if UPDATE:
            GOLDEN.parent.mkdir(parents=True, exist_ok=True)
            GOLDEN.write_text(html, encoding="utf-8", newline="\n")
            return
        self.assertTrue(GOLDEN.exists(), f"missing golden {GOLDEN}; create it with SENTINEL_UPDATE_GOLDEN=1")
        self.assertEqual(
            html,
            GOLDEN.read_text(encoding="utf-8"),
            "dashboard drifted from its golden; if intended, regenerate with SENTINEL_UPDATE_GOLDEN=1 and review the diff",
        )


if __name__ == "__main__":
    unittest.main()
