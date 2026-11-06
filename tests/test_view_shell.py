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
        expected_sha = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
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


if __name__ == "__main__":
    unittest.main()
