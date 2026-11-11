"""IMP-262: brownfield harvest into the brief v2."""

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

from sentinel.harvest import HarvestError, parse_harvest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

CLOUD_KEY = "AKIA" + "IOSFODNN7EXAMPLE"  # split so no secret-shaped literal sits in the repo

HARVEST = f"""# Harvest — risk dashboard

## B0 Inventory
- repo: queue-api — services/queue-api
- repo: metrics-job — jobs/metrics

## B1 Architecture and components
- [HECHO queue-api:src/app.py] The queue API is a Flask app with three blueprints.
- [INFERIDO] The metrics job runs hourly, because its scheduler entry is named hourly.

## B3 Integrations
- [FACT metrics-job:config/settings.py] The job reads the support metrics service over HTTPS.
- [NO ENCONTRADO queue-api:src/clients/] No timeout is set for the metrics client.
- [FUERA DEL CÓDIGO owners] Who owns the metrics service integration.
- [DIVERGENCIA queue-api:README.md] README documents a v2 API; the code serves v1 routes only.

## B4 Security
- [HECHO queue-api:config/prod.env] The service reads its key from the environment ({CLOUD_KEY} appears in a sample file).
"""


class ParseTests(unittest.TestCase):
    def test_a_good_harvest(self):
        parsed = parse_harvest(HARVEST)
        self.assertEqual(parsed["errors"], [])
        self.assertEqual(parsed["repos"], ["queue-api", "metrics-job"])
        self.assertEqual(parsed["coverage"], {"fact": 3, "inferred": 1, "not_found": 1, "out_of_code": 1, "divergence": 1})

    def test_each_rule_is_enforced(self):
        cases = {
            "- [GUESS] something": "unknown tag",
            "- [HECHO] fact without ref": "needs `repo:file`",
            "- [HECHO other-repo:x.py] fact from an unknown repo": "not in the B0 inventory",
            "- [NO ENCONTRADO] nothing said where": "says where it should be",
            "- [FUERA DEL CÓDIGO budget] money": "out-of-code topic",
        }
        for line, needle in cases.items():
            with self.subTest(line=line):
                text = "## B0 Inventory\n- repo: queue-api — x\n## B1 Architecture\n" + line + "\n"
                self.assertTrue(any(needle in e for e in parse_harvest(text)["errors"]), parse_harvest(text)["errors"])
        self.assertTrue(any("outside any block" in e for e in parse_harvest("- [INFERIDO] floating\n")["errors"]))
        self.assertTrue(any("no repository" in e for e in parse_harvest("## B1 x\n- [INFERIDO] y\n")["errors"]))


class WorkspaceTests(unittest.TestCase):
    def test_harvest_feeds_the_brief_and_routes_what_the_code_cannot_say(self):
        from sentinel.anchors import anchor_report
        from sentinel.brief_integrity import brief_v2_integrity_findings
        from sentinel.cli import main
        from sentinel.core.io import read_json
        from sentinel.gaps import parse_gap_table
        from sentinel.memory import ContextBroker
        from test_golden_artifacts import SCENARIOS

        scenario = SCENARIOS["en"]
        pid = "HARVEST"
        old_cwd = Path.cwd()
        tmp = Path(tempfile.mkdtemp())
        os.chdir(tmp)
        out = io.StringIO()
        try:
            with patch.object(ContextBroker, "_connect_lancedb", lambda self: None), contextlib.redirect_stdout(out):
                raw = tmp / "raw.md"
                raw.write_text(scenario["raw"], encoding="utf-8")
                harvest = tmp / "harvest.md"
                harvest.write_text(HARVEST, encoding="utf-8")
                self.assertEqual(main(["init", pid]), 0)
                self.assertEqual(main(["ingest", pid, "--source", str(raw)]), 0)
                out.truncate(0); out.seek(0)
                self.assertEqual(main(["harvest", pid, "--source", str(harvest)]), 0)
                result = json.loads(out.getvalue())
                bad = tmp / "bad.md"
                bad.write_text("## B1 x\n- [HECHO] nope\n", encoding="utf-8")
                self.assertNotEqual(main(["harvest", pid, "--source", str(bad)]), 0)
                self.assertEqual(main(["brief", pid, "--profile", "UI", "--genesis", "brownfield-extension"]), 0)
            base = tmp / "workspaces" / pid
            stored = Path(result["path"]).read_text(encoding="utf-8")
            self.assertNotIn(CLOUD_KEY, stored)
            self.assertGreaterEqual(result["secrets_redacted"], 1)
            self.assertEqual(len(result["gaps_opened"]), 2)
            rows = {g["id"]: g for g in parse_gap_table((base / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))}
            opened = [rows[g] for g in result["gaps_opened"]]
            self.assertEqual(sorted(g["severity"] for g in opened), ["high", "low"])
            self.assertTrue(all(g["origin"] == "harvest" for g in opened))
            brief = (base / "02_requirements" / "project-brief.md").read_text(encoding="utf-8")
            source_id = result["source_id"]
            self.assertIn(f"The queue API is a Flask app with three blueprints. (queue-api:src/app.py) [[sources §", brief)
            self.assertIn(f"# {source_id} —", brief)
            self.assertIn("- (inferred) The metrics job runs hourly", brief)
            self.assertIn("Harvested repositories: `queue-api`, `metrics-job`", brief)
            self.assertIn("Harvest coverage: facts 3 · inferred 1 · not found 1 · out of code 1 · divergences 1", brief)
            self.assertEqual(brief_v2_integrity_findings(base), [])
            registry = read_json(base / "00_raw" / "source_manifest.json", {})["registry"]
            report = anchor_report(brief, registry)
            self.assertEqual(report["findings"], [])
            self.assertEqual(read_json(base / "01_discovery" / "harvest.json", {})["direction"], "built")
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
