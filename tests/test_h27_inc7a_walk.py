"""H27 inc 7a walk: a change with a non-textual prototype, from its derived source to the manual and the diagrams."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SyncCase, run_ok  # noqa: E402

from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.prototype import load_inventory  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = "W7A"
CID = "CHG-001"
INC7 = SyncCase.FIXTURES / "change_inc7"


class Inc7aWalk(SyncCase):
    PID = PID

    def next_key(self) -> str:
        forget_read_snapshots()
        return json.loads(run_ok(["next", PID, "--change", CID]))["key"]

    def test_walk(self) -> None:
        origin = json.loads(run_ok(["sources", PID, "--load", str(INC7 / "prototipo-alta-proveedor.html"),
                                    "--role", "diseno_nuevo", "--change", CID]))["source_id"]
        before = self.next_key()
        derived = json.loads(run_ok(["sources", PID, "--load", str(INC7 / "prototipo-alta-proveedor.md"),
                                     "--role", "diseno_nuevo", "--change", CID, "--derived-from", origin]))
        self.assertEqual(derived["derived_from"], origin)
        # loading the derived source did not change where the change goes next
        self.assertEqual(self.next_key(), before)
        # the cross-read cites the derived source; its origin shows next to the citation
        text = (INC7 / "cruce_diseno_derivado.md").read_text(encoding="utf-8")
        text = text.replace("F-PED", self._ids()["pedido"]).replace("F-DER", derived["source_id"])
        claims = Path.cwd() / "cruce_diseno_derivado.md"
        claims.write_text(text, encoding="utf-8")
        run_ok(["cross", PID, "--change", CID, "--kind", "diseno", "--claims", str(claims)])
        from sentinel.crosses import crosses_dir

        report = (crosses_dir(workspace_path(PID), CID) / "crosses.md").read_text(encoding="utf-8")
        self.assertTrue(f"(derivado de {origin})" in report or f"(derived from {origin})" in report)
        # the change inventories its prototype and writes a manual for one screen
        run_ok(["prototype", PID, "--inventory", "--change", CID])
        forget_read_snapshots()
        proto = next(p for p in load_inventory(PID, CID)["prototypes"] if p["screens"])
        screen = proto["screens"][0]
        manual = Path.cwd() / "manual.json"
        manual.write_text(json.dumps({"prototype": proto["source"], "screens": [
            {"screen": screen["id"], "purpose": "Review the approvals from {{" + screen["elements"][0]["id"] + "}}."}]}), encoding="utf-8")
        run_ok(["prototype", PID, "--manual", "--source", str(manual), "--change", CID])
        base = workspace_path(PID) / "02_requirements" / CID / "prototype"
        self.assertTrue((base / "inventory.json").is_file())
        self.assertTrue((base / "manual.md").is_file())
        # the diagrams of the change, with no project brief
        run_ok(["view", PID, "--artifact", "diagrams", "--change", CID])
        self.assertTrue((workspace_path(PID) / "08_context_packs" / "views" / f"{CID}-diagrams.html").is_file())


if __name__ == "__main__":
    unittest.main()
