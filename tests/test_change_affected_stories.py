"""IMP-393: the existing stories a MODIFIED/REMOVED row affects: not implemented -> Stale, implemented/in progress -> change request."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, build_matured_workspace, gap_acceptance_answer, run_ok  # noqa: E402
from sentinel.backlog.hooks import mark_stories_stale  # noqa: E402
from sentinel.id_registry import registry_path  # noqa: E402
from sentinel.core.markdown import parse_frontmatter  # noqa: E402
from sentinel.slice_plan import build_phases, build_story_rows  # noqa: E402
from sentinel.compilers.slicing import build_cross_cutting_enabler_specs  # noqa: E402
from sentinel.story_ids import carry_modificada_por  # noqa: E402
from sentinel.traceability import load_graph  # noqa: E402
from sentinel.workspace import read_json, workspace_path  # noqa: E402
from test_change_specs import PROJECT_EARS, PROJECT_RAW, open_change  # noqa: E402

MODIFIED_ROW = ("### GAP-OBJECTIVE\n- Respuesta: Cuando el comprador cambia el texto del aviso, el sistema debe mostrar el aviso nuevo.\n"
                "- Owner / fuente: Jefa de Compras\n- Delta: MODIFIED\n- Superficie: Tabla de proveedores\n- Afecta: US-001\n- Estado de decisión: confirmado\n")
REMOVED_ROW = ("### GAP-ACCEPTANCE\n- Respuesta: Cuando el comprador guarda el alta incompleta, el sistema debe conservar los datos cargados.\n"
               "- Owner / fuente: Jefa de Compras\n- Delta: REMOVED\n- Superficie: Tabla de proveedores\n- Afecta: US-002\n- Estado de decisión: confirmado\n")
UNCHANGED_ROW = ("### GAP-USERS\n- Respuesta: Cuando el comprador sigue enviando el alta completa, el sistema debe continuar validando los datos.\n"
                 "- Owner / fuente: Jefa de Compras\n- Delta: UNCHANGED\n- Superficie: Tabla de proveedores\n- Estado de decisión: confirmado\n")
ANSWERS = REMOVED_ROW + "\n" + MODIFIED_ROW + "\n" + UNCHANGED_ROW


def backlog_dir() -> Path:
    return workspace_path("MIX") / "04_backlog"


def story(story_id: str) -> str:
    return (backlog_dir() / f"{story_id}.md").read_text(encoding="utf-8")


def state() -> dict:
    return read_json(workspace_path("MIX") / "state.json", {})


def set_status(story_id: str, *statuses: str) -> None:
    for status in statuses:
        run_ok(["story-status", "MIX", "--story", story_id, "--set", status, "--owner", "ana"])


class ChangeAffectedStories(SnapshotWorkspaceCase):
    cid = "CHG-001"

    @classmethod
    def build_workspace(cls):
        build_matured_workspace("MIX", PROJECT_RAW, gap_acceptance_answer(PROJECT_EARS))
        cid = open_change("MIX")
        cls.cid = cid
        Path("a.md").write_text(ANSWERS, encoding="utf-8")
        run_ok(["resolve-gaps", "MIX", "--source", "a.md", "--change", cid])
        run_ok(["brief", "MIX", "--change", cid])
        run_ok(["specs", "MIX", "--change", cid])

    def run_backlog(self) -> dict:
        return json.loads(run_ok(["backlog", "MIX", "--change", self.cid]))

    def by_delta(self, res: dict) -> dict[str, str]:
        out = {}
        for story_id in res["stories"]:
            out[parse_frontmatter(story(story_id))["delta"]] = story_id
        return out

    def test_modified_on_draft_story_stales_it_and_adds_story(self):
        res = self.run_backlog()
        self.assertEqual(res["stale"], ["US-001", "US-002"])
        new = self.by_delta(res)["MODIFIED"]
        front = parse_frontmatter(story(new))
        self.assertEqual(front["type"], "value_story")
        self.assertNotIn("modifica", front)
        lifecycle = state()["story_lifecycle"]
        self.assertEqual(lifecycle["US-001"]["status"], "Stale")
        self.assertEqual(lifecycle[new]["status"], "Draft")
        self.assertIn("status: Stale", story("US-001"))
        self.assertEqual(res["change_requests"], [])
        self.assertEqual(res["warnings"], [])
        self.assertEqual(state()["changes"][self.cid]["backlog"]["stale"], ["US-001", "US-002"])

    def test_removed_on_draft_story_stales_it_without_new_story(self):
        res = self.run_backlog()
        self.assertEqual(sorted(self.by_delta(res)), ["MODIFIED"])
        self.assertEqual(len(res["stories"]), 1)
        self.assertEqual(state()["story_lifecycle"]["US-002"]["status"], "Stale")
        self.assertEqual(res["report"]["removed"], [])
        # the id of the unit that produced no story stays issued
        issued = json.loads(registry_path("MIX").read_text(encoding="utf-8"))["families"]["US"]["issued"]
        self.assertEqual(len(issued), 4)

    def test_modified_on_done_story_makes_change_request(self):
        set_status("US-001", "Ready", "In Progress", "In Review", "Done")
        before = story("US-001")
        res = self.run_backlog()
        new = self.by_delta(res)["MODIFIED"]
        front = parse_frontmatter(story(new))
        self.assertEqual(front["type"], "change_request")
        self.assertEqual(front["modifica"], ["US-001"])
        self.assertEqual(res["change_requests"], [new])
        self.assertEqual(res["warnings"], [])
        self.assertEqual(res["stale"], ["US-002"])
        self.assertEqual(state()["story_lifecycle"]["US-001"]["status"], "Done")
        after = story("US-001")
        self.assertEqual(parse_frontmatter(after)["modificada_por"], [new])
        self.assertEqual(after.replace(f"modificada_por:\n  - {new}\n", ""), before)
        self.assertIn({"from": new, "to": "US-001", "relation": "modifies"}, load_graph("MIX")["edges"])
        self.assertEqual(state()["changes"][self.cid]["backlog"]["change_requests"], [new])
        again = self.run_backlog()
        self.assertEqual(story("US-001"), after)
        self.assertEqual(again["change_requests"], [new])

    def test_in_progress_story_gets_change_request_and_warning(self):
        set_status("US-001", "Ready", "In Progress")
        before = story("US-001")
        res = self.run_backlog()
        new = self.by_delta(res)["MODIFIED"]
        self.assertEqual(parse_frontmatter(story(new))["type"], "change_request")
        self.assertEqual(len(res["warnings"]), 1)
        self.assertIn("US-001", res["warnings"][0])
        self.assertIn("In Progress", res["warnings"][0])
        self.assertEqual(state()["story_lifecycle"]["US-001"]["status"], "In Progress")
        self.assertEqual(story("US-001").replace(f"modificada_por:\n  - {new}\n", ""), before)
        self.assertIn("US-001", story(new))
        self.assertIn({"from": new, "to": "US-001", "relation": "modifies"}, load_graph("MIX")["edges"])

    def test_in_progress_warning_in_english(self):
        set_status("US-001", "Ready", "In Progress")
        changes = state()["changes"]
        changes[self.cid]["language"] = "en"
        from sentinel.workspace import update_state
        update_state("MIX", changes=changes)
        res = self.run_backlog()
        self.assertIn("in progress", res["warnings"][0].lower())
        self.assertNotIn("en curso", res["warnings"][0])

    def test_already_stale_story_untouched(self):
        set_status("US-002", "Stale")
        stamp = state()["story_lifecycle"]["US-002"]
        res = self.run_backlog()
        self.assertEqual(res["stale"], ["US-001"])
        self.assertEqual(state()["story_lifecycle"]["US-002"], stamp)
        self.assertEqual(mark_stories_stale("MIX", ["US-002"], "x", self.cid), [])

    def test_mixed_statuses_on_one_row(self):
        # one row affecting a Done story and a Draft one: stale the Draft one, change request for the Done one
        text = MODIFIED_ROW.replace("Afecta: US-001", "Afecta: US-001, US-002")
        Path("b.md").write_text(text, encoding="utf-8")
        run_ok(["resolve-gaps", "MIX", "--source", "b.md", "--change", self.cid])
        run_ok(["specs", "MIX", "--change", self.cid])
        set_status("US-001", "Ready", "In Progress", "In Review", "Done")
        res = self.run_backlog()
        new = self.by_delta(res)["MODIFIED"]
        front = parse_frontmatter(story(new))
        self.assertEqual(front["type"], "change_request")
        self.assertEqual(front["modifica"], ["US-001"])
        self.assertEqual(state()["story_lifecycle"]["US-002"]["status"], "Stale")
        self.assertIn("US-002", res["stale"])
        self.assertEqual(parse_frontmatter(story("US-001"))["modificada_por"], [new])
        self.assertNotIn("modificada_por", story("US-002"))
        self.assertIn({"from": new, "to": "US-001", "relation": "modifies"}, load_graph("MIX")["edges"])
        self.assertNotIn({"from": new, "to": "US-002", "relation": "modifies"}, load_graph("MIX")["edges"])

    def test_removed_on_done_story_makes_change_request(self):
        set_status("US-002", "Ready", "In Progress", "In Review", "Done")
        res = self.run_backlog()
        removed = self.by_delta(res)["REMOVED"]
        front = parse_frontmatter(story(removed))
        self.assertEqual((front["type"], front["modifica"]), ("change_request", ["US-002"]))
        self.assertEqual(state()["story_lifecycle"]["US-002"]["status"], "Done")
        self.assertEqual(parse_frontmatter(story("US-002"))["modificada_por"], [removed])
        self.assertEqual(res["stale"], ["US-001"])

    def test_missing_affected_story_warns(self):
        (backlog_dir() / "US-002.md").unlink()
        res = self.run_backlog()
        self.assertTrue(any("US-002" in w for w in res["warnings"]))
        self.assertEqual(res["stale"], ["US-001"])

    def test_modificada_por_survives_project_backlog(self):
        set_status("US-001", "Ready", "In Progress", "In Review", "Done")
        res = self.run_backlog()
        new = self.by_delta(res)["MODIFIED"]
        run_ok(["backlog", "MIX"])
        after = story("US-001")
        self.assertEqual(parse_frontmatter(after)["modificada_por"], [new])
        self.assertEqual(state()["story_lifecycle"]["US-001"]["status"], "Done")
        # only the frontmatter key is carried; the story is otherwise the project's own render
        front = parse_frontmatter(after)
        self.assertEqual((front["type"], front["parent_epic"], front["status"]), ("value_story", "EPIC-001", "Done"))
        rendered = "---\nid: US-001\ntrace:\n  - X\n---\n\nbody\n"
        path = backlog_dir() / "US-001.md"
        self.assertEqual(carry_modificada_por(path, rendered), rendered.replace("  - X\n", "  - X\nmodificada_por:\n  - " + new + "\n"))
        self.assertEqual(carry_modificada_por(backlog_dir() / "US-002.md", rendered), rendered)
        self.assertEqual(carry_modificada_por(backlog_dir() / "US-099.md", rendered), rendered)

    def test_change_request_enters_slice_plan(self):
        from unittest.mock import patch
        import sentinel.compilers.slicing as slicing

        stories = [{"id": "US-010", "type": "change_request", "title": "t"}, {"id": "US-011", "type": "value_story", "title": "u"}]
        phases = build_phases(build_story_rows(stories, {"stories": []}))
        waved = [item["story_id"] for wave in phases["implementation_waves"] for item in wave["stories"]]
        self.assertEqual(sorted(waved), ["US-010", "US-011"])
        enabler_word = slicing.ENABLER_CANDIDATES[0]["tokens"][0]
        with patch.object(slicing, "cross_cutting_enabler_evidence", lambda project_id: enabler_word):
            specs = build_cross_cutting_enabler_specs("MIX", [{"id": "US-010", "type": "change_request"}], {})
        self.assertTrue(specs)
        self.assertEqual(specs[0]["enables"], ["US-010"])


if __name__ == "__main__":
    unittest.main()
