"""IMP-240: /view on the common shell with a deduplicated, reproducible model.

The embedded model drops ``blocks`` (unused by the page), moves trace nodes and
source fragments into shared tables, keeps every path workspace-relative and
replaces the wall clock with the source cut-off and a 12-char sha256. The feedback
export keeps consuming exactly the same fields, so it stays byte-identical.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sentinel import themes
from sentinel.shell import content_fingerprint
from sentinel.cli import main
from sentinel.view import ViewModelError, collect_artifact_model, render_artifact_view, validate_view_model

ROOT = Path(__file__).parent
GOLDEN = ROOT / "fixtures" / "golden"
FIXED_EPOCH = 1_781_481_600  # 2026-06-15T00:00:00Z


def pin_mtimes(root: Path, epoch: int = FIXED_EPOCH) -> None:
    for folder, _dirs, files in os.walk(root / "workspaces"):
        for name in files:
            os.utime(os.path.join(folder, name), (epoch, epoch))


def embedded_view_model(html: str) -> dict:
    """The model embedded in a /view page (pre-IMP-240 inline or IMP-240 JSON script)."""
    marker = '<script id="view-data" type="application/json">'
    if marker in html:
        start = html.index(marker) + len(marker)
        end = html.index("</script>", start)
    else:
        start = html.index("const model = ") + len("const model = ")
        end = html.index(";\n", start)
    raw = html[start:end].replace("<\\/", "</").replace("<\\u0021--", "<!--")
    return json.loads(raw)


def export_projection(model: dict) -> dict:
    """Fields buildFeedbackExport / buildGuidedResponseExport read from the model."""
    return {
        "project_id": model.get("project_id"),
        "artifact": model.get("artifact"),
        "source_path": model.get("source_path"),
        "source_relative_path": model.get("source_relative_path"),
        "ba_email": model.get("ba_email"),
        "sections": [{k: s.get(k) for k in ("id", "section_path", "line_start", "line_end")} for s in model.get("sections", [])],
        "markers": [{k: m.get(k) for k in ("id", "marker", "section_id")} for m in model.get("markers", [])],
        "guided": [
            {k: i.get(k) for k in ("id", "question", "statement", "expected_format", "audience", "response_needed")}
            for i in (model.get("guided_response") or {}).get("items", [])
        ],
    }


class _ViewWorkspace(unittest.TestCase):
    project_id = "VIEWSHELL"

    @classmethod
    def setUpClass(cls) -> None:
        cls.old_cwd = Path.cwd()
        cls.temp = Path(tempfile.mkdtemp(prefix="sentinel_view_"))
        os.chdir(cls.temp)
        fixture = ROOT / "fixtures" / "complete_requirement.md"
        for argv in (["init", cls.project_id], ["ingest", cls.project_id, "--source", str(fixture)], ["maturity", cls.project_id], ["specs", cls.project_id]):
            assert main(argv) == 0, argv
        pin_mtimes(cls.temp)

    @classmethod
    def tearDownClass(cls) -> None:
        os.chdir(cls.old_cwd)
        shutil.rmtree(cls.temp, ignore_errors=True)


class ViewModelShapeTests(_ViewWorkspace):
    def setUp(self) -> None:
        self.model = collect_artifact_model(self.project_id, "prd")

    def test_blocks_are_not_embedded(self) -> None:
        self.assertNotIn("blocks", self.model)
        for section in self.model["sections"]:
            self.assertNotIn("blocks", section)
            self.assertIn("html", section)
            self.assertIn("markdown", section)

    def test_trace_nodes_and_fragments_live_in_shared_tables(self) -> None:
        self.assertIn("graph_nodes", self.model)
        self.assertIn("source_fragments", self.model)
        cited = [c for c in self.model["citations"] if c.get("trace_id")]
        self.assertTrue(cited)
        for citation in self.model["citations"]:
            self.assertNotIn("trace_node", citation)
            self.assertNotIn("source_fragment", citation)
            for node_id in citation["mini_graph"]["node_ids"]:
                self.assertIn(node_id, self.model["graph_nodes"])
        with_fragment = [c for c in cited if self.model["source_fragments"].get(c["trace_id"], {}).get("available")]
        self.assertTrue(with_fragment)

    def test_no_clock_and_provenance_from_source(self) -> None:
        self.assertNotIn("generated_at", self.model)
        source = self.temp / self.model["source_path"]
        expected_sha = content_fingerprint(source.read_bytes())
        self.assertEqual(self.model["provenance"]["source_sha256"], expected_sha)
        self.assertEqual(self.model["provenance"]["cutoff"], datetime.fromtimestamp(FIXED_EPOCH, timezone.utc).isoformat())

    def test_no_absolute_paths_in_model(self) -> None:
        text = json.dumps(self.model, ensure_ascii=False)
        self.assertNotIn(self.temp.as_posix(), text)
        self.assertNotIn(str(self.temp).replace("\\", "\\\\"), text)
        self.assertIsNone(re.search(r'"[A-Za-z]:[\\/]', text))

    def test_two_collections_are_identical(self) -> None:
        again = collect_artifact_model(self.project_id, "prd")
        self.assertEqual(json.dumps(self.model, sort_keys=True), json.dumps(again, sort_keys=True))


class ViewValidationTests(_ViewWorkspace):
    def setUp(self) -> None:
        self.model = collect_artifact_model(self.project_id, "prd")

    def _errors(self, mutate) -> list[str]:
        model = copy.deepcopy(self.model)
        mutate(model)
        return validate_view_model(model)

    def test_collected_model_is_valid(self) -> None:
        self.assertEqual(validate_view_model(self.model), [])

    def test_duplicate_section_id(self) -> None:
        errors = self._errors(lambda m: m["sections"].append(copy.deepcopy(m["sections"][0])))
        self.assertTrue(any("duplicate section" in e for e in errors), errors)

    def test_dangling_graph_node(self) -> None:
        def mutate(m):
            citation = next(c for c in m["citations"] if c["mini_graph"]["node_ids"])
            citation["mini_graph"]["node_ids"].append("NOPE-999")

        errors = self._errors(mutate)
        self.assertTrue(any("NOPE-999" in e for e in errors), errors)

    def test_summary_must_match_lists(self) -> None:
        errors = self._errors(lambda m: m["summary"].__setitem__("citations", 999))
        self.assertTrue(any("summary.citations" in e for e in errors), errors)

    def test_render_refuses_invalid_model(self) -> None:
        model = copy.deepcopy(self.model)
        model["summary"]["sections"] = 0
        with self.assertRaises(ViewModelError):
            render_artifact_view(model, themes.load_theme())

    def test_error_is_value_error(self) -> None:
        self.assertTrue(issubclass(ViewModelError, ValueError))


class ViewShellRenderTests(_ViewWorkspace):
    def setUp(self) -> None:
        self.model = collect_artifact_model(self.project_id, "prd")
        self.theme = themes.load_theme()
        self.html = render_artifact_view(self.model, self.theme)

    def test_shell_and_theme(self) -> None:
        self.assertIn('<a class="skip-link" href="#main">', self.html)
        self.assertIn('aria-expanded="false"', self.html)
        self.assertIn(themes.emit_root_css(self.theme), self.html)
        self.assertIn(themes.legend_html(self.theme, "en"), self.html)
        self.assertIn('id="provenance"', self.html)
        self.assertIn(self.model["provenance"]["source_sha256"], self.html)

    def test_model_is_embedded_as_json_script(self) -> None:
        self.assertEqual(embedded_view_model(self.html), json.loads(json.dumps(self.model)))

    def test_existing_feedback_loop_survives(self) -> None:
        for needle in ("Export Markdown", "Draft Email To BA", "buildGuidedResponseExport", "## Guided Responses",
                       "sentinel /resolve-gaps", "sentinel /sync", "Client progress", "Source Fragment", "Mini Trace",
                       "ignite-sentinel:view-feedback:", "ignite-sentinel:view-guided-response:"):
            self.assertIn(needle, self.html)

    def test_feedback_export_functions_unchanged(self) -> None:
        # Frozen from the pre-IMP-240 golden: the export JS must stay byte-identical.
        frozen = (GOLDEN / "view_export_functions.js").read_text(encoding="utf-8").split("\n// ----\n")
        for fn, expected in zip(("function buildFeedbackExport(comments) {", "function buildGuidedResponseExport() {"), frozen):
            self.assertEqual(_js_function(self.html, fn), expected.strip("\n"))

    def test_every_local_storage_access_is_guarded(self) -> None:
        for match in re.finditer(r"localStorage\.(?:get|set)Item", self.html):
            before = self.html[max(0, match.start() - 160) : match.start()]
            self.assertIn("try", before, self.html[match.start() - 80 : match.start() + 40])

    def test_source_change_banner_and_orphans(self) -> None:
        self.assertIn('id="sourceChanged" hidden', self.html)
        self.assertIn(":source-sha", self.html)
        self.assertIn("orphaned: target no longer exists", self.html)

    def test_reader_edition_toggle(self) -> None:
        self.assertIn('id="provToggle"', self.html)
        self.assertIn("body:not(.show-prov) .prov", self.html)
        self.assertIn("ignite-sentinel:view-provenance", self.html)

    def test_no_external_urls_and_no_hex_in_view_css(self) -> None:
        self.assertNotRegex(self.html, r"https?://|@import|<script src=")
        from sentinel.resources import package_resource

        css = package_resource("themes", "templates", "view.css").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", css), [])

    def test_render_is_byte_identical(self) -> None:
        again = render_artifact_view(collect_artifact_model(self.project_id, "prd"), themes.load_theme())
        self.assertEqual(self.html, again)

    def test_cli_theme_flag_and_config(self) -> None:
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["view", self.project_id, "--artifact", "prd", "--theme", "neutral"]), 0)
        self.assertEqual(json.loads(out.getvalue())["theme"], "neutral")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["view", self.project_id, "--artifact", "prd", "--theme", "nope"]), 1)

    def test_mcp_view_arguments_forward_theme(self) -> None:
        from sentinel.mcp import view_arguments

        self.assertEqual(view_arguments("P", "prd"), ["view", "P", "--artifact", "prd"])
        self.assertEqual(view_arguments("P", "prd", True, "neutral"), ["view", "P", "--artifact", "prd", "--open", "--theme", "neutral"])


class ReaderEditionMarkupTests(unittest.TestCase):
    def test_inline_provenance_is_wrapped_not_removed(self) -> None:
        from sentinel.view import markdown_to_html

        rendered = markdown_to_html("- Show open queues _(`GAP-ACCEPTANCE` / `CHG-001`)_ [Fuente: acta 3]")
        self.assertIn('<span class="prov">_(<code>GAP-ACCEPTANCE</code> / <code>CHG-001</code>)_</span>', rendered)
        self.assertIn('<span class="prov">[Fuente: acta 3]</span>', rendered)
        self.assertIn("Show open queues", rendered)


class ViewReviewFixTests(_ViewWorkspace):
    """Final-review findings for IMP-240 (each failed before its fix)."""

    def test_absolute_root_inside_embedded_text_is_relativized(self) -> None:
        from sentinel.view import relativize_text

        root = self.temp.resolve()
        for raw in (root.as_posix(), str(root), str(root).replace("\\", "/")):
            text = f"(Anchor: {raw}/workspaces/{self.project_id}/03_specs/specs.md:1-4)"
            self.assertEqual(relativize_text(self.project_id, text), f"(Anchor: workspaces/{self.project_id}/03_specs/specs.md:1-4)")

    def test_regenerate_command_does_not_leak_theme_directory(self) -> None:
        theme_path = self.temp / "my themes" / "brand.json"
        html = render_artifact_view(collect_artifact_model(self.project_id, "prd"), themes.load_theme(), theme_arg=str(theme_path))
        self.assertNotIn(str(self.temp), html)
        self.assertNotIn(self.temp.as_posix(), html)
        self.assertIn("--theme &quot;brand.json&quot;", html)

    def test_dashboard_regenerate_command_does_not_leak_theme_directory(self) -> None:
        from sentinel.dashboard import _provenance_section

        section = _provenance_section({"cutoff": "", "sources": []}, str(self.temp / "brand.json"))
        self.assertNotIn(str(self.temp), section)
        self.assertIn("brand.json", section)

    def test_configured_theme_quotes_and_comments_are_accepted(self) -> None:
        from sentinel.view import resolve_view_theme
        from sentinel.workspace import config_path

        path = config_path(self.project_id)
        original = path.read_text(encoding="utf-8")
        self.addCleanup(path.write_text, original, encoding="utf-8")
        path.write_text(original + '\ntheme: "neutral"  # house style\n', encoding="utf-8")
        theme, warning = resolve_view_theme(self.project_id, None)[0], resolve_view_theme(self.project_id, None)[2]
        self.assertEqual(theme["name"], "neutral")
        self.assertIsNone(warning)

    def test_broken_configured_theme_falls_back_with_warning(self) -> None:
        from sentinel.view import resolve_view_theme
        from sentinel.workspace import config_path

        path = config_path(self.project_id)
        original = path.read_text(encoding="utf-8")
        self.addCleanup(path.write_text, original, encoding="utf-8")
        path.write_text(original + "\ntheme: does-not-exist\n", encoding="utf-8")
        theme, _arg, warning = resolve_view_theme(self.project_id, None)
        self.assertEqual(theme["name"], "neutral")
        self.assertIn("does-not-exist", warning)

    def test_orphan_detection_compares_content_not_only_position(self) -> None:
        html = render_artifact_view(collect_artifact_model(self.project_id, "prd"), themes.load_theme())
        body = _js_function(html, "function targetExists(item) {")
        self.assertIn("m.marker === item.marker", body)
        self.assertIn("s.section_path === item.section_path", body)

    def test_print_shows_provenance_and_deep_links_reveal(self) -> None:
        html = render_artifact_view(collect_artifact_model(self.project_id, "prd"), themes.load_theme())
        self.assertIn("body .prov { display: inline !important; }", html)
        self.assertIn("revealIfHidden(location.hash.slice(1));", html)
        self.assertIn("scroll-margin-top: calc(var(--shell-top) + 16px)", html)

    def test_source_sha_is_recorded_on_first_load_with_notes(self) -> None:
        html = render_artifact_view(collect_artifact_model(self.project_id, "prd"), themes.load_theme())
        body = _js_function(html, "function checkSourceChanged() {")
        self.assertIn("rememberSourceSha()", body)

    def test_title_is_escaped(self) -> None:
        model = collect_artifact_model(self.project_id, "prd")
        model["label"] = "PRD <b>"
        html = render_artifact_view(model, themes.load_theme())
        self.assertIn("PRD &lt;b&gt;", html[: html.index("</title>")])

    def test_provenance_wrap_never_crosses_tags(self) -> None:
        from sentinel.view import markdown_to_html

        rendered = markdown_to_html("Text [Source: `a]b`] end")
        self.assertNotIn('<span class="prov">[Source: <code>a]</span>', rendered)

    def test_display_path_treats_both_path_styles_as_absolute(self) -> None:
        from sentinel.view import display_path

        self.assertNotIn("/home/someone", display_path(self.project_id, "/home/someone/x/notes.md"))
        self.assertNotIn("C:/Users", display_path(self.project_id, "C:/Users/someone/notes.md"))

    def test_linkish_class_has_no_literal_backslashes(self) -> None:
        from sentinel.view import markdown_to_html

        self.assertIn('<span class="linkish">site</span>', markdown_to_html("see [site](x)"))


def _js_function(html: str, signature: str) -> str:
    start = html.find(signature)
    if start < 0:
        return ""
    depth, index = 0, start
    while index < len(html):
        char = html[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return html[start : index + 1]
        index += 1
    return ""


if __name__ == "__main__":
    unittest.main()
