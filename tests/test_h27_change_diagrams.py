"""H27 inc 7a task 5: `/view --change --artifact diagrams|prototype|prototype-manual|prototype-trace`."""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SyncCase, run_ok  # noqa: E402

from sentinel.cli import main  # noqa: E402
from sentinel.diagrams import COPY, change_asis_components, collect_diagrams_model  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = "CDIA"
CID = "CHG-001"


def run_code(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(list(argv))
    return code, out.getvalue()


class ChangeDiagramsCase(SyncCase):
    PID = PID

    def asis_card(self) -> dict:
        model = collect_diagrams_model(PID, CID)
        return next(c for c in model["cards"] if c["id"] == "architecture-asis")

    def test_change_diagrams_need_no_project_brief(self) -> None:
        run_ok(["view", PID, "--artifact", "diagrams", "--change", CID])
        views = workspace_path(PID) / "08_context_packs" / "views"
        self.assertTrue((views / f"{CID}-diagrams.html").is_file())
        self.assertFalse((views / "diagrams.html").exists())
        self.assertFalse((workspace_path(PID) / "02_requirements" / "project-brief.md").exists())

    def read_code(self) -> None:
        """A second harvest of the change that reads code: `repo:` makes `sad-compras` a system that exists."""
        path = Path.cwd() / "harvest_codigo.md"
        path.write_text(
            "# Harvest\n\n## B0 Inventario\n- repo: sad-compras — 00_raw/06_baseline/src\n\n"
            "## B1 Arquitectura y componentes\n"
            "- [HECHO sad-compras:src/alta.py] El alta de proveedor se valida en el backoffice.\n", encoding="utf-8")
        run_ok(["harvest", PID, "--source", str(path), "--change", CID])

    def test_doc_only_harvest_draws_no_component(self) -> None:
        self.assertEqual(change_asis_components(PID, CID, []), [])

    def test_asis_status_only_registered(self) -> None:
        self.read_code()
        card = self.asis_card()
        language = collect_diagrams_model(PID, CID)["language"]
        self.assertIn("sad-compras", card["mermaid"])
        self.assertIn(COPY[language]["no_status"], card["mermaid"])
        for word in ("unchanged", "extends", "retired"):
            self.assertNotIn(word, card["mermaid"])

    def test_registered_status_is_transcribed(self) -> None:
        self.read_code()
        got = change_asis_components(PID, CID, [{"name": "sad-compras", "status": "extends"}])
        self.assertEqual(got, [{"name": "sad-compras", "status": "extends"}])
        got = change_asis_components(PID, CID, [])
        self.assertEqual([c["name"] for c in got], ["sad-compras"])
        self.assertEqual(got[0]["status"], "")

    def test_provenance_hashes_what_was_drawn(self) -> None:
        first = collect_diagrams_model(PID, CID)["provenance"]
        self.assertTrue(any("deliverable (working)" in f["path"] for f in first["sources"]), first["sources"])
        self.assertEqual(first, collect_diagrams_model(PID, CID)["provenance"])
        self.read_code()
        self.assertNotEqual(first["source_sha256"], collect_diagrams_model(PID, CID)["provenance"]["source_sha256"])

    def test_no_series_card_in_change(self) -> None:
        model = collect_diagrams_model(PID, CID)
        self.assertNotIn("series", [c["kind"] for c in model["cards"]])

    def test_change_prototype_views(self) -> None:
        run_ok(["prototype", PID, "--inventory", "--change", CID])
        run_ok(["view", PID, "--artifact", "prototype", "--change", CID])
        self.assertTrue((workspace_path(PID) / "08_context_packs" / "views" / f"{CID}-prototype.html").is_file())
        code, text = run_code(["view", PID, "--artifact", "prd", "--change", CID])
        self.assertNotEqual(code, 0)
        self.assertIn("--change sólo admite", text)

    def test_change_manual_and_trace_views(self) -> None:
        run_ok(["prototype", PID, "--inventory", "--change", CID])
        inventory = json.loads((workspace_path(PID) / "02_requirements" / CID / "prototype" / "inventory.json").read_text(encoding="utf-8"))
        proto = inventory["prototypes"][0]
        screen = proto["screens"][0]
        purpose = "Review the approvals from {{" + screen["elements"][0]["id"] + "}}."
        manual = Path.cwd() / "manual.json"
        manual.write_text(json.dumps({"prototype": proto["source"], "screens": [{"screen": screen["id"], "purpose": purpose}]}), encoding="utf-8")
        run_ok(["prototype", PID, "--manual", "--source", str(manual), "--change", CID])
        run_ok(["view", PID, "--artifact", "prototype-manual", "--change", CID])
        self.assertTrue((workspace_path(PID) / "08_context_packs" / "views" / f"{CID}-prototype-manual.html").is_file())

    def test_project_view_of_a_change_only_workspace_still_refused(self) -> None:
        code, _ = run_code(["view", PID, "--artifact", "diagrams"])
        self.assertNotEqual(code, 0)
