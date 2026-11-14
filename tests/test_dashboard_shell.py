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

import contextlib
import io
import re
import shutil
import subprocess

from sentinel import themes
from sentinel.shell import content_fingerprint
from sentinel.cli import main
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
            digest = content_fingerprint((self.temp / path).read_bytes())
            self.assertEqual(sources[path], digest)

    def test_two_collections_are_identical(self) -> None:
        pin_mtimes(self.temp)
        first = json.dumps(collect_dashboard_model(self.temp), sort_keys=True)
        second = json.dumps(collect_dashboard_model(self.temp), sort_keys=True)
        self.assertEqual(first, second)

    def test_empty_portfolio_has_empty_provenance(self) -> None:
        model = collect_dashboard_model(self.temp / "nowhere")
        self.assertEqual(model["provenance"], {"cutoff": "", "sources": []})


class CrossPlatformFingerprintTests(unittest.TestCase):
    """IMP-246 (found by CI): provenance fingerprints must not depend on the OS line ending."""

    def test_crlf_and_lf_give_the_same_fingerprint(self) -> None:
        from sentinel.shell import content_fingerprint

        self.assertEqual(content_fingerprint(b'{\r\n  "a": 1\r\n}\r\n'), content_fingerprint(b'{\n  "a": 1\n}\n'))
        self.assertEqual(len(content_fingerprint(b"x")), 12)
        self.assertNotEqual(content_fingerprint(b"a"), content_fingerprint(b"b"))


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

    def test_page_content_fits_narrow_screens(self) -> None:
        css = package_resource("themes", "templates", "dashboard.css").read_text(encoding="utf-8")
        self.assertIn("minmax(min(360px,100%),1fr)", css, "cards must not force a 360px minimum on a 400px screen")
        self.assertRegex(css, r"@media \(max-width: 900px\)\{[^@]*\.kpis\{grid-template-columns:repeat\(2,")

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



class DashboardThemeFlagTests(DashboardFixtureMixin, unittest.TestCase):
    def _run(self, *extra: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["/dashboard", *extra])
        return code, out.getvalue(), err.getvalue()

    def test_theme_neutral_flag(self) -> None:
        code, out, _ = self._run("--theme", "neutral")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["theme"], "neutral")
        html = (self.temp / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn("--theme neutral", html)

    def test_theme_from_local_file(self) -> None:
        theme = copy.deepcopy(themes.load_theme())
        theme["name"] = "local-test"
        theme["tokens"]["light"]["--accent"] = "#123456"
        path = self.temp / "local-test.json"
        path.write_text(json.dumps(theme), encoding="utf-8")
        code, out, _ = self._run("--theme", str(path))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["theme"], "local-test")
        self.assertIn("--accent:#123456", (self.temp / "dashboard.html").read_text(encoding="utf-8"))

    def test_unknown_theme_fails_without_writing(self) -> None:
        code, _, err = self._run("--theme", "nope")
        self.assertEqual(code, 3)  # IMP-302: invalid input
        self.assertIn("neutral", err)
        self.assertFalse((self.temp / "dashboard.html").exists())

    def test_mcp_dashboard_arguments_forward_theme(self) -> None:
        from sentinel.mcp import dashboard_arguments

        self.assertEqual(dashboard_arguments(False, ""), ["dashboard"])
        self.assertEqual(dashboard_arguments(True, "neutral"), ["dashboard", "--open", "--theme", "neutral"])



class DashboardReviewFixTests(DashboardFixtureMixin, unittest.TestCase):
    """Final-review findings for IMP-239 (each failed before its fix)."""

    def test_every_template_is_tracked_by_git(self) -> None:
        root = Path(__file__).resolve().parents[1]
        if shutil.which("git") is None or not (root / ".git").exists():
            self.skipTest("not a git checkout")
        templates = root / "sentinel" / "themes" / "templates"
        tracked = subprocess.run(
            ["git", "ls-files", "--", "sentinel/themes/templates"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.split()
        on_disk = sorted(f"sentinel/themes/templates/{item.name}" for item in templates.iterdir() if item.is_file())
        self.assertEqual(sorted(tracked), on_disk, "a template on disk is not tracked (check .gitignore)")

    def test_knowledge_ledger_path_is_relative(self) -> None:
        ledger = self.temp / "workspaces" / "DASH_CLIENT_WAIT" / "01_discovery" / "knowledge_state.json"
        ledger.write_text(json.dumps({"summary": {"total": 1, "by_status": {"OPEN": 1}, "by_lens": {}}}), encoding="utf-8")
        text = json.dumps(collect_dashboard_model(self.temp), ensure_ascii=False)
        self.assertNotIn(self.temp.as_posix(), text)
        self.assertNotIn(str(self.temp).replace("\\", "\\\\"), text)
        self.assertIn("workspaces/DASH_CLIENT_WAIT/01_discovery/knowledge_state.json", text)

    def test_drawer_and_scrim_sit_above_the_sticky_bar(self) -> None:
        css = package_resource("themes", "templates", "dashboard.css").read_text(encoding="utf-8")
        shell = package_resource("themes", "templates", "shell.css").read_text(encoding="utf-8")
        bar = int(re.search(r"\.shell-top\{[^}]*z-index:(\d+)", shell).group(1))
        for selector in ("drawer", "scrim"):
            z = int(re.search(r"\." + selector + r"\{[^}]*z-index:(\d+)", css).group(1))
            self.assertGreater(z, bar, selector)

    def test_closed_sidebar_leaves_the_tab_order(self) -> None:
        shell = package_resource("themes", "templates", "shell.css").read_text(encoding="utf-8")
        narrow = shell[shell.index("@media (max-width: 900px)") :]
        self.assertRegex(narrow, r"\.shell-side\{[^}]*visibility:hidden")
        self.assertRegex(narrow, r"\.shell-side\.open\{[^}]*visibility:visible")

    def test_written_file_uses_lf_on_every_os(self) -> None:
        from sentinel.dashboard import generate_dashboard

        generate_dashboard(self.temp)
        self.assertNotIn(b"\r\n", (self.temp / "dashboard.html").read_bytes())

    def test_html_comment_opener_in_documents_cannot_break_the_data_block(self) -> None:
        model = collect_dashboard_model(self.temp)
        model["workspaces"][0]["documents"].append({"key": "x", "label": "X", "path": "x.md", "content": "a <!-- <script> b"})
        html = render_dashboard(model, themes.load_theme())
        data = html[html.index('id="dashboard-data"') : html.index('id="section-registry"')]
        self.assertNotIn("<!--", data)

    def test_gap_copy_template_uses_real_newlines(self) -> None:
        js = package_resource("themes", "templates", "dashboard.js").read_text(encoding="utf-8")
        body = js[js.index("function gapTemplate") : js.index("function openGaps")]
        self.assertNotIn("\\\\n", body.replace("\\n", ""), "literal backslash-n would be copied")
        self.assertNotIn('"\\\\n', body)

    def test_escape_only_closes_an_open_sidebar(self) -> None:
        js = package_resource("themes", "templates", "shell.js").read_text(encoding="utf-8")
        self.assertRegex(js, r'e\.key==="Escape"&&side&&side\.classList\.contains\("open"\)')
        self.assertNotIn("aria-pressed", js)

    def test_doctor_rejects_unknown_files_in_templates(self) -> None:
        from sentinel.doctor import themes_check

        root = self.temp / "fake"
        source = Path(__file__).resolve().parents[1] / "sentinel" / "themes"
        shutil.copytree(source, root / "sentinel" / "themes", ignore=shutil.ignore_patterns("__pycache__"))
        self.assertEqual(themes_check(root)["status"], "PASS")
        (root / "sentinel" / "themes" / "templates" / "logo.svg").write_text("<svg/>", encoding="utf-8")
        result = themes_check(root)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("logo.svg", result["detail"])


if __name__ == "__main__":
    unittest.main()
