"""IMP-398: optional short alias as 4th field of a border line; Superficie accepts name or alias, stores the name."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sentinel.change_requirements import parse_surfaces, propose_surfaces  # noqa: E402
from sentinel.changes import parse_border  # noqa: E402
from sentinel.errors import InputError  # noqa: E402

LONG = "Continuidad hacia la caja destino de llaves, valores en custodia, comisiones"


def block(*lines: str) -> str:
    return "- Borde:\n" + "\n".join(f"  - {line}" for line in lines) + "\n"


class SurfaceAlias(unittest.TestCase):
    def test_alias_resolves_to_canonical_name(self):
        border = parse_border(block(f"nuevo | proceso | {LONG} | Continuidad", "preservado | dato | Padrón | padron2"), "c")
        self.assertEqual(border[0], {"zone": "nuevo", "type": "proceso", "name": LONG, "alias": "Continuidad", "cite": "c"})
        self.assertEqual(parse_surfaces("continuidad", border), ([LONG], []))
        self.assertEqual(parse_surfaces(f"PADRON2; {LONG.upper()}; otra", border), (["Padrón", LONG], ["otra"]))
        self.assertEqual(parse_surfaces("continuidad; " + LONG, border)[0], [LONG])

    def test_duplicate_alias_rejected(self):
        with self.assertRaises(InputError) as ctx:
            parse_border(block("nuevo | proceso | Uno | corto", "nuevo | proceso | Dos | CORTO"), "c")
        self.assertIn("alias", str(ctx.exception).lower())
        with self.assertRaises(InputError) as ctx:
            parse_border(block("nuevo | proceso | Uno | corto", "nuevo | proceso | Dos | corto"), "c", "en")
        self.assertIn("alias", str(ctx.exception).lower())
        self.assertIn("already", str(ctx.exception))

    def test_invalid_alias_rejected(self):
        for bad in ("a;b", "a|b", "x" * 41, "Corté", ""):
            with self.assertRaises(InputError, msg=bad):
                parse_border(block(f"nuevo | proceso | Uno | {bad}"), "c")
        with self.assertRaises(InputError) as ctx:
            parse_border(block("nuevo | proceso | Uno | a;b"), "c", "en")
        self.assertIn("alias", str(ctx.exception).lower())
        parse_border(block(f"nuevo | proceso | Uno | {'x' * 40}"), "c")

    def test_border_without_alias_unchanged(self):
        border = parse_border(block("nuevo | pantalla | Listado", "adyacente | dato | Padrón"), "c")
        self.assertEqual(border, [
            {"zone": "nuevo", "type": "pantalla", "name": "Listado", "cite": "c"},
            {"zone": "adyacente", "type": "dato", "name": "Padrón", "cite": "c"},
        ])
        self.assertEqual(parse_surfaces("listado", border), (["Listado"], []))
        self.assertEqual(propose_surfaces("abre el listado", border), ["Listado"])


if __name__ == "__main__":
    unittest.main()
