from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.dashboard import collect_dashboard_model
from sentinel.status import project_status


RAW = (
    "# Risk Dashboard\n\n"
    "Goal: reduce manual review time for support leads before standup. "
    "Users include support leads and operations managers. "
    "Scope includes a read-only dashboard for queue triage. "
    "The dashboard reads queue metrics from the existing support metrics service."
)


def assumption_payload(risk: str = "med") -> dict[str, object]:
    return {
        "assumptions": [
            {
                "id": "ASM-TECH-METRICS-SOURCE",
                "lens": "technical",
                "statement": "The dashboard will provisionally use the existing support metrics service as the source for queue risk.",
                "owner": "Technology Lead",
                "risk": risk,
                "justification": "The dashboard reads queue metrics from the existing support metrics service.",
                "closes_gap": "GAP-TECH-DATA-SOURCE",
            }
        ]
    }


class DevelopmentReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.source = self.temp / "risk-dashboard.md"
        self.source.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "READY"]), 0)
        self.assertEqual(main(["ingest", "READY", "--source", str(self.source)]), 0)
        self.ws = self.temp / "workspaces" / "READY"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _assume(self, risk: str = "med") -> None:
        path = self.temp / "assumptions.json"
        path.write_text(json.dumps(assumption_payload(risk)), encoding="utf-8")
        self.assertEqual(main(["assume", "READY", "--source", str(path)]), 0)

    def test_maturity_persists_development_readiness_matrix(self) -> None:
        self._assume()
        self.assertEqual(main(["maturity", "READY"]), 0)

        readiness_path = self.ws / "01_discovery" / "development_readiness.json"
        self.assertTrue(readiness_path.exists())
        payload = json.loads(readiness_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["artifact"], "development_readiness")
        self.assertEqual(payload["summary"]["areas_total"], 16)
        self.assertIn("crystallization_gate", payload["summary"])
        statuses = payload["summary"]["by_status"]
        self.assertGreater(statuses["CONFIRMED"], 0)
        self.assertGreater(statuses["ASSUMED"], 0)
        self.assertGreater(statuses["OPEN"], 0)
        self.assertEqual(payload["summary"]["crystallization_gate"]["state"], "NOT_READY_OPEN_UNCERTAINTY")

        data_area = next(area for area in payload["matrix"] if area["area"] == "Data and integrations")
        tech_cell = next(cell for cell in data_area["lenses"] if cell["lens"] == "technical")
        self.assertEqual(tech_cell["status"], "ASSUMED")
        self.assertEqual(tech_cell["evidence"]["assumption_id"], "ASM-TECH-METRICS-SOURCE")
        self.assertEqual(tech_cell["evidence"]["owner"], "Technology Lead")

        open_area = next(area for area in payload["matrix"] if area["area"] == "Design prototype readiness")
        self.assertEqual(open_area["status"], "OPEN")
        open_evidence = open_area["lenses"][0]["evidence"]
        self.assertTrue(
            open_evidence == {"note": "[PENDING INPUT]"}
            or (open_evidence.get("trace_id") and open_evidence.get("quote"))
        )

    def test_status_and_dashboard_expose_development_readiness(self) -> None:
        self._assume()
        self.assertEqual(main(["maturity", "READY"]), 0)

        status = project_status("READY")
        readiness = status["development_readiness"]
        self.assertEqual(readiness["summary"]["areas_total"], 16)
        self.assertEqual(
            readiness["summary"]["crystallization_gate"]["state"],
            "NOT_READY_OPEN_UNCERTAINTY",
        )

        dashboard = collect_dashboard_model(self.temp)
        workspace = dashboard["workspaces"][0]
        self.assertIn("development_readiness", workspace)
        self.assertIn("Certeza desarrollo", workspace["summary"])
        self.assertIn("NOT_READY_OPEN_UNCERTAINTY", workspace["summary"]["Certeza desarrollo"])


if __name__ == "__main__":
    unittest.main()
