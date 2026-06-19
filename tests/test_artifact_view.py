from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.view import collect_artifact_model


ROOT = Path(__file__).parent


class ArtifactViewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp)

    def test_view_model_reconstructs_prd_sections_and_signals(self) -> None:
        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "VIEW"]), 0)
        self.assertEqual(main(["ingest", "VIEW", "--source", str(fixture)]), 0)
        self.assertEqual(main(["maturity", "VIEW"]), 0)
        self.assertEqual(main(["specs", "VIEW"]), 0)

        model = collect_artifact_model("VIEW", "prd")
        source = (self.temp / model["source_path"]).read_text(encoding="utf-8")
        reconstructed = "\n".join(section["markdown"] for section in model["sections"])

        self.assertEqual(reconstructed, source)
        self.assertEqual(model["artifact"], "prd")
        self.assertGreater(model["summary"]["sections"], 1)
        self.assertGreater(model["summary"]["citations"], 0)
        self.assertTrue(any(node["type"] == "prd" for node in model["trace"]["nodes"]))

    def test_view_command_generates_self_contained_html_for_gaps(self) -> None:
        fixture = ROOT / "fixtures" / "incomplete_requirement.md"
        self.assertEqual(main(["init", "GAPVIEW"]), 0)
        self.assertEqual(main(["ingest", "GAPVIEW", "--source", str(fixture)]), 0)
        self.assertEqual(main(["view", "GAPVIEW", "--artifact", "gaps"]), 0)

        view_path = self.temp / "workspaces" / "GAPVIEW" / "08_context_packs" / "views" / "gaps.html"
        self.assertTrue(view_path.exists())
        html = view_path.read_text(encoding="utf-8")
        self.assertIn("read-only derived view", html)
        self.assertIn("const model =", html)
        self.assertIn("GAPVIEW", html)
        self.assertNotIn("__ARTIFACT_DATA__", html)
        self.assertNotIn("<script src=", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)

        state = json.loads((self.temp / "workspaces" / "GAPVIEW" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["last_command"], "view")


if __name__ == "__main__":
    unittest.main()
