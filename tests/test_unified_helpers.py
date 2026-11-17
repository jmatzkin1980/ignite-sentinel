"""IMP-346: the four helpers whose copies had diverged now have one implementation.

Each test pins the chosen behaviour, including the inputs where the old copies
disagreed (noted per case), and that every former owner uses the shared one.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sentinel import dashboard, development_readiness, diagrams, export, readiness_view, view
from sentinel.core import paths
from sentinel.knowledge import ledger
from sentinel.lens_registry import normalize_lens
from sentinel.shell import provenance_section


class NormalizeLensTests(unittest.TestCase):
    def test_one_implementation(self) -> None:
        self.assertIs(ledger.normalize_lens, normalize_lens)
        self.assertIs(development_readiness.normalize_lens, normalize_lens)

    def test_chosen_behaviour(self) -> None:
        cases = {
            "": "product",
            "  ": "product",
            None: "product",
            "Quality": "quality",
            "Technology": "technical",
            "unknown": "unknown",
            # old readiness copy: kept "n/a" / "-" as lens names that match nothing
            "n/a": "product",
            "N/A": "product",
            "-": "product",
            # old ledger copy: frontend/backend were kept as lenses that do not exist
            "frontend": "technical",
            "Backend": "technical",
            # old readiness copy: kept the whole "a/b" text as one unknown lens
            "business/product": "business",
            # old ledger copy: returned "technical " (trailing space)
            "technical / design": "technical",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(normalize_lens(value), expected)

    def test_readiness_still_expands_every_lens_of_a_list(self) -> None:
        self.assertEqual(development_readiness.lenses_for("Technology / design, frontend"), ["design", "technical"])


class CompactLinksTests(unittest.TestCase):
    def test_one_implementation(self) -> None:
        self.assertIs(development_readiness.compact_links, ledger.compact_links)

    def test_absent_values_are_dropped_never_stringified(self) -> None:
        # old readiness copy turned None / 0 into the targets "None" / "0"
        self.assertEqual(ledger.compact_links([{"type": "gap", "target": None}]), [])
        self.assertEqual(ledger.compact_links([{"type": None, "target": "X"}]), [])
        self.assertEqual(ledger.compact_links([{"type": "gap", "target": 0}]), [])
        self.assertEqual(ledger.compact_links([{"type": "gap"}]), [])

    def test_dedup_strip_and_placeholders(self) -> None:
        links = [
            {"type": "gap", "target": " GAP-1 "},
            {"type": "gap", "target": "GAP-1"},
            {"type": "gap", "target": "-"},
            {"type": "gap", "target": "N/A"},
            {"type": "area", "target": "DRA-01"},
        ]
        self.assertEqual(
            ledger.compact_links(links),
            [{"type": "gap", "target": "GAP-1"}, {"type": "area", "target": "DRA-01"}],
        )

    def test_assumption_without_gap_gets_no_none_link(self) -> None:
        cell = development_readiness.readiness_cell(
            "P1", "DRA-01", {"area": "a"}, "product", [], [], [{"id": "ASM-1", "lens": "product", "justification": "j"}]
        )
        self.assertEqual(cell["links"], [{"type": "assumption", "target": "ASM-1"}, {"type": "area", "target": "DRA-01"}])


class WorkspaceRelativeTests(unittest.TestCase):
    def test_export_uses_the_core_helper(self) -> None:
        self.assertIs(export.workspace_relative, paths.workspace_relative)

    def test_export_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = paths.workspace_path("P1", root) / "08_context_packs" / "exports" / "a.md"
            self.assertEqual(paths.workspace_relative("P1", target, root), "08_context_packs/exports/a.md")
            # old export copy raised ValueError for a relative path or one outside the workspace
            self.assertEqual(paths.workspace_relative("P1", Path("workspaces/P1/08_context_packs/a.md"), root), "08_context_packs/a.md")
            self.assertEqual(paths.workspace_relative("P1", Path("elsewhere/x.md"), root), "elsewhere/x.md")


class ProvenanceSectionTests(unittest.TestCase):
    def test_single_source_inline_in_page_language(self) -> None:
        en = provenance_section(language="en", command="python -m sentinel /view P --artifact prd", cutoff="2026-01-01T00:00:00+00:00",
                                sources=[{"path": "workspaces/P/03_specs/prd.md"}], digest="abc123abc123")
        self.assertIn('<h2 id="provenance-h">Provenance</h2>', en)
        self.assertIn("<p>Source: <code>workspaces/P/03_specs/prd.md</code> · sha256 <code>abc123abc123</code> · cut-off", en)
        self.assertIn("(the source file's modification time, not the build time).", en)
        self.assertIn("<p>Regenerate: <code>python -m sentinel /view P --artifact prd</code></p>", en)
        # old view/readiness copies wrote the body in English under a Spanish heading
        es = provenance_section(language="es-AR", command="c", cutoff="t", sources=[{"path": "p"}], digest="d")
        self.assertIn('<h2 id="provenance-h">Procedencia</h2>', es)
        self.assertIn("<p>Fuente: <code>p</code> · sha256 <code>d</code> · fecha de corte", es)
        self.assertIn("<p>Regenerar: <code>c</code></p>", es)
        self.assertNotIn("Source", es)

    def test_language_tag_detection_is_shared(self) -> None:
        # old readiness copy only recognised exactly "es"
        for tag in ("es", "ES", "es-AR"):
            self.assertIn("Procedencia", provenance_section(language=tag, command="c", cutoff="t", sources=[], digest="d"))
        for tag in ("en", "auto", None, ""):
            self.assertIn("Provenance", provenance_section(language=tag, command="c", cutoff="t", sources=[], digest="d"))

    def test_many_sources_inline(self) -> None:
        text = provenance_section(language="en", command="c", cutoff="t", sources=[{"path": "a"}, {"path": "b"}], digest="d")
        self.assertIn("<p>Sources: <code>a</code>, <code>b</code> · sha256", text)
        self.assertIn("(the newest source modification time, not the build time)", text)

    def test_table_layout_without_digest(self) -> None:
        text = provenance_section(language="es", command="c", cutoff="", sources=[{"path": "w/state.json", "sha256": "123"}], section_class="dash-section")
        self.assertIn('<section class="dash-section" id="provenance" aria-labelledby="provenance-h">', text)
        self.assertIn('<time datetime="-">-</time> <span id="provAge"></span>', text)
        self.assertIn("<tr><td><code>w/state.json</code></td><td><code>123</code></td></tr>", text)
        self.assertIn("<p>Sin fuentes.</p>", provenance_section(language="es", command="c", cutoff="", sources=[]))

    def test_escapes_everything(self) -> None:
        text = provenance_section(language="en", command="a<b", cutoff='"x"', sources=[{"path": "<p>"}], digest="<d>")
        self.assertNotIn("<p>:", text)
        self.assertIn("&lt;p&gt;", text)
        self.assertIn("a&lt;b", text)
        self.assertIn("&lt;d&gt;", text)
        self.assertIn("&quot;x&quot;", text)

    def test_remark_goes_before_the_regen_command(self) -> None:
        text = provenance_section(language="en", command="c", cutoff="t", sources=[{"path": "a"}], digest="d", remark="Mermaid <11>")
        self.assertIn("<p>Mermaid &lt;11&gt;</p><p>Regenerate: <code>c</code></p></section>", text)

    def test_every_page_uses_it(self) -> None:
        for module in (dashboard, diagrams, readiness_view, view):
            with self.subTest(module=module.__name__):
                self.assertIs(module.provenance_section, provenance_section)


if __name__ == "__main__":
    unittest.main()
