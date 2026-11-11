"""IMP-26w: a new project compiles the brief v2; older workspaces stay on v1."""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


class DefaultVersionTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.tmp = Path(tempfile.mkdtemp())
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def state(self, pid):
        return json.loads((self.tmp / "workspaces" / pid / "state.json").read_text(encoding="utf-8"))

    def test_init_defaults_to_v2_and_the_flag_keeps_v1(self):
        from sentinel.brief_schema import brief_settings
        from sentinel.cli import main

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["init", "NEWV2"]), 0)
            self.assertEqual(main(["init", "KEEPV1", "--brief-version", "1"]), 0)
        self.assertEqual(self.state("NEWV2")["brief_settings"], {"brief_version": 2})
        self.assertEqual(self.state("KEEPV1")["brief_settings"], {"brief_version": 1})
        # a workspace from before IMP-26w has no brief_settings and reads as v1
        legacy = self.tmp / "workspaces" / "NEWV2" / "state.json"
        data = self.state("NEWV2")
        data.pop("brief_settings")
        legacy.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(int(brief_settings("NEWV2").get("brief_version", 1)), 1)

    def test_a_new_project_blocks_until_the_ba_confirms_profile_and_genesis(self):
        from sentinel.cli import main
        from sentinel.memory import ContextBroker
        from test_golden_artifacts import SCENARIOS

        scenario = SCENARIOS["en"]
        pid = "DEFAULTV2"
        with patch.object(ContextBroker, "_connect_lancedb", lambda self: None), contextlib.redirect_stdout(io.StringIO()):
            raw = self.tmp / "raw.md"
            raw.write_text(scenario["raw"], encoding="utf-8")
            self.assertEqual(main(["init", pid]), 0)
            self.assertEqual(main(["ingest", pid, "--source", str(raw)]), 0)
            for index, statement in enumerate(scenario["ears"], start=1):
                answer = self.tmp / f"answer-{index}.md"
                answer.write_text(scenario["answer"].format(s=statement, i=index), encoding="utf-8")
                self.assertEqual(main(["resolve-gaps", pid, "--source", str(answer)]), 0)
            self.assertEqual(main(["brief", pid]), 0)
            base = self.tmp / "workspaces" / pid
            gaps = (base / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
            self.assertRegex(gaps, r"\| `?GAP-BRIEF-PROFILE`? \|[^\n]*\| critical \| OPEN \|")
            self.assertEqual(self.state(pid)["readiness_stage"], "CLIENT_RESPONSE_NEEDED")
            self.assertNotEqual(main(["specs", pid]), 0)  # blocked until the BA confirms

            self.assertEqual(main(["brief", pid, "--profile", "UI", "--genesis", "greenfield"]), 0)
            brief = (base / "02_requirements" / "project-brief.md").read_text(encoding="utf-8")
            self.assertTrue(brief.startswith("<!-- sentinel-artifact: v2 -->"))
            self.assertEqual(main(["specs", pid]), 0)


if __name__ == "__main__":
    unittest.main()
