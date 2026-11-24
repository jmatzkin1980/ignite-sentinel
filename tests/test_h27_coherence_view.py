"""IMP-410 (H27 inc 3) task 4: the lens view of a change and the deterministic checks of IMP-260 over it."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_ok, waive_crosses  # noqa: E402
from test_brief_v2_compiler import inputs  # noqa: E402
from test_h26_cross_record import CID, PID, CrossCase  # noqa: E402

from sentinel.change_coherence import (  # noqa: E402
    CHANGE_CROSS_CHECKS, coherence_dir, coherence_state, coherence_view, refresh_coherence,
)
from sentinel.compilers.brief_v2 import render_brief_v2  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.cross_checks import run_cross_checks  # noqa: E402
from sentinel.cross_review import _body as body  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402
from sentinel.health import collect_health  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402


class CoherenceView(CrossCase):
    def view(self) -> str:
        waive_crosses(PID, CID)
        result = refresh_coherence(PID, CID)
        self.assertIsNotNone(result)
        return Path(result["view_path"]).read_text(encoding="utf-8")

    def test_view_places(self):
        text = self.view()
        expected = {
            "2.2": ("RN-02", "5.000.000"),
            "3.2": ("HU-01", "La jefa aprueba o rechaza con un motivo"),
            "1.5": ("CA-03",),
            "4.3": ("PD-01",),
            "2.1": ("Analista de Compras",),
            "3.1": ("imprime el resumen",),
            "6.2": ("Alta de monto bajo", "sigue habilitándose en el acto"),
            "4.1": ("pantalla — Bandeja de aprobaciones",),
            "5.7": ("endpoint — Alta de proveedores",),
            "1.3": ("La migración de las altas históricas en papel.",),
        }
        for place, needles in expected.items():
            found = body(text, place)
            self.assertIsNotNone(found, place)
            for needle in needles:
                self.assertIn(needle, found, (place, needle))
        self.assertEqual(json.loads((coherence_dir(workspace_path(PID), CID) / "checks.json")
                                    .read_text(encoding="utf-8"))["unplaced"], [])

    def test_checks_subset(self):
        self.view()
        checks = json.loads((coherence_dir(workspace_path(PID), CID) / "checks.json").read_text(encoding="utf-8"))
        self.assertEqual([c["id"] for c in checks["checks"]], list(CHANGE_CROSS_CHECKS))
        rules = next(c for c in checks["checks"] if c["id"] == "rules_have_steps")
        self.assertEqual(rules["status"], "WARN")
        self.assertIn("business rule RN-01 of 2.2 has no step in 3.2", rules["issues"])
        self.assertEqual(refresh_coherence(PID, CID)["unplaced"], [])

    def test_fingerprint_stable_and_moves(self):
        waive_crosses(PID, CID)
        first = coherence_view(PID, CID)["fingerprint"]
        self.assertEqual(first, coherence_view(PID, CID)["fingerprint"])
        result = record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        sed = next(g for g in result["gaps"] if g.startswith("GAP-SED-"))
        forget_read_snapshots()
        run_ok(["cross", PID, "--change", CID, "--accept-new", sed, "--type", "pantalla",
                "--name", "Delegación de aprobaciones"])
        self.assertNotEqual(first, coherence_view(PID, CID)["fingerprint"])
        text = (coherence_dir(workspace_path(PID), CID) / "view.md").read_text(encoding="utf-8")
        self.assertIn("pantalla — Delegación de aprobaciones", text)
        state = coherence_state(PID, CID)
        self.assertEqual(state["state"], "missing")
        self.assertTrue(state["view_current"])

    def test_not_ready_before_crosses(self):
        self.assertIsNone(refresh_coherence(PID, CID))
        self.assertFalse(coherence_dir(workspace_path(PID), CID).exists())

    def test_view_does_not_dirty_health(self):
        self.view()
        forget_read_snapshots()
        for finding in collect_health(PID)["findings"]:
            self.assertNotIn("view.md", json.dumps(finding, ensure_ascii=False))


class ProjectChecksUnchanged(unittest.TestCase):
    def test_project_cross_checks_unchanged(self):
        text = render_brief_v2(inputs())[0]
        every = run_cross_checks(text)
        self.assertEqual(every, run_cross_checks(text, only=None))
        self.assertEqual(len(every), 14)
        one = run_cross_checks(text, only=("rules_have_steps",))
        self.assertEqual([r["id"] for r in one], ["rules_have_steps"])


if __name__ == "__main__":
    unittest.main()
