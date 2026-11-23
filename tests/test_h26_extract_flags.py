"""IMP-402 (H26 inc 3) task 3: flags from the agent, open gaps and harvest divergences."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_h26_extract_proposals import CID, PID, ProposalsCase, block  # noqa: E402

from sentinel.changes import change_gaps_path, change_language  # noqa: E402
from sentinel.extraction.flags import element_flags, refresh_flags  # noqa: E402
from sentinel.gaps import count_gaps, merge_gaps_by_topic, parse_gap_rows, render_gaps  # noqa: E402
from sentinel.workspace import update_state, workspace_path  # noqa: E402
from sentinel.changes import get_change, list_changes  # noqa: E402

QUOTE = "La jefa de Compras no puede aprobar un alta que cargó ella misma"
TEXT = f"RN-04 | {QUOTE}."


def gap(gap_id: str, description: str, status: str = "OPEN") -> dict:
    return {"id": gap_id, "status": status, "description": description}


class Pure(unittest.TestCase):
    def flags(self, element_id="RN-04", gaps=(), entries=(), agent=()):
        return element_flags(element_id, TEXT, QUOTE, list(agent), list(gaps), list(entries))

    def test_agent_flag_kept(self):
        agent = [{"origin": "agent", "kind": "contradiccion", "ref": "", "note": "x"}]
        self.assertEqual(self.flags(agent=agent), agent)

    def test_open_gap_naming_id_flags(self):
        open_gap = gap("GAP-X-1", "La regla RN-04 no cierra con el SAD")
        found = self.flags(gaps=[open_gap])
        self.assertEqual([(f["origin"], f["kind"], f["ref"]) for f in found], [("gap", "pregunta_abierta", "GAP-X-1")])
        self.assertEqual(self.flags("RN-0", gaps=[open_gap]), [])
        self.assertEqual(self.flags("RN-04#2", gaps=[open_gap]), [])
        self.assertEqual(self.flags(gaps=[gap("GAP-X-1", "La regla RN-04 no cierra", "CLOSED")]), [])

    def test_open_gap_quoting_text_flags(self):
        found = self.flags("RN-99", gaps=[gap("GAP-VER-ABC123", f"El SAD dice otra cosa: {QUOTE}")])
        self.assertEqual([(f["kind"], f["ref"]) for f in found], [("divergencia", "GAP-VER-ABC123")])

    def test_harvest_divergence_flags(self):
        entry = {"kind": "divergence", "line": "12", "text": f"…{QUOTE}…"}
        found = self.flags(entries=[entry])
        self.assertEqual([(f["origin"], f["kind"], f["ref"]) for f in found], [("harvest", "divergencia", "harvest:12")])
        self.assertEqual(self.flags(entries=[{**entry, "kind": "fact"}]), [])

    def test_harvest_text_inside_element(self):
        entry = {"kind": "divergence", "line": "3", "text": "no puede aprobar un alta que cargó ella"}
        self.assertEqual(len(self.flags("RN-77", entries=[entry])), 1)


class FromWorkspace(ProposalsCase):
    def open_gap(self, description: str) -> None:
        base = workspace_path(PID)
        path = change_gaps_path(base, CID)
        existing = [g for g in parse_gap_rows(path.read_text(encoding="utf-8")) if g.get("id") != "NONE"]
        new = {"id": "GAP-TEST-RN05", "lens": "technical", "severity": "high", "status": "OPEN", "kind": "client",
               "description": description, "question": "¿Cuál rige?", "evidence_mention": "RN-05",
               "origin": "sources", "resolution_note": ""}
        rows = merge_gaps_by_topic(existing, [new])["gaps"]
        language = change_language(PID, get_change(PID, CID))
        path.write_text(render_gaps(PID, rows, CID, language, path.with_name("gap_elicitation.json")), encoding="utf-8")
        updated = {k: dict(v) for k, v in list_changes(PID).items()}
        updated[CID]["gap_counts"] = count_gaps(rows)
        update_state(PID, changes=updated)

    def test_record_flags_from_open_gap(self):
        self.open_gap("La regla RN-05 de notificación a la gerencia contradice el SAD")
        result = self.submit(block(
            "RN-05", "- Tratamiento: descarte", "- Motivo: x",
            '- Cita: "se notifica a la gerencia de Compras"',
        ))
        self.assertEqual(result["recorded"], ["RN-05"], result)
        self.assertEqual(result["flagged"], ["RN-05"])
        from sentinel.extraction.proposals import load_proposals
        item = load_proposals(workspace_path(PID), CID)["items"]["RN-05"]
        self.assertEqual([f["origin"] for f in item["flags"]], ["gap"])
        self.assertEqual(item["flags"][0]["ref"], "GAP-TEST-RN05")
        refreshed = refresh_flags(PID, CID, "RN-05", item)
        self.assertEqual([f["ref"] for f in refreshed], ["GAP-TEST-RN05"])


if __name__ == "__main__":
    unittest.main()
