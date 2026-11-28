"""IMP-406 (H27 inc 1) final fix wave: one test per reviewer scenario (I1 to I8 and the cheap minors)."""
from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import (  # noqa: E402
    IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, class_deferred, complete_extraction, reproposal_block, run_ok,
    waive_crosses,
)
from test_h27_export_v2 import PID as EXPORT_PID, ExportCase, hu01_block  # noqa: E402

from sentinel.cli import main  # noqa: E402
from sentinel.changes import deferred_gaps, list_changes  # noqa: E402
from sentinel.core.io import forget_read_snapshots, read_json, write_json  # noqa: E402
from sentinel.extraction import extraction_dir, run_extract  # noqa: E402
from sentinel.extraction.confirm import confirm_item  # noqa: E402
from sentinel.extraction.coverage import extraction_coverage  # noqa: E402
from sentinel.extraction.inventory import (  # noqa: E402
    PART_MAX_CHARS,
    PART_MAX_LINES,
    _assign_parts,
    build_inventory,
    element_text,
    load_inventory,
    parse_request_elements,
)
from sentinel.extraction.proposals import load_proposals, record_proposals  # noqa: E402
from sentinel.extraction.verify import sample_size, verification_needed, verification_status  # noqa: E402
from sentinel.readiness_verdict import build_change_verdict, change_next_step  # noqa: E402
from sentinel.status import change_status  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LARGO = FIXTURES / "change_extraction" / "pedido_largo.md"
CID = "CHG-001"


def sentence_line(count: int) -> str:
    return " ".join(f"El analista revisa el paso numero {i} del proceso de alta." for i in range(count))


class SplitUnits(unittest.TestCase):
    """I1 and I3 at the parser: what is cut, and what keeps its id."""

    def test_one_long_line_is_cut_in_pieces_of_one_line(self):
        text = "## Proceso\n" + sentence_line(500) + "\n"
        parts = parse_request_elements(text, "F-01", "x.md")
        self.assertGreater(len(parts), 5)
        self.assertTrue(all(p["id"].startswith("SEC-proceso.p") and p["lines"] == [2, 2] for p in parts))
        self.assertTrue(all(0 < p["chars"] <= PART_MAX_CHARS for p in parts), [p["chars"] for p in parts])
        edges = [p["cspan"] for p in parts]
        self.assertEqual(edges[0][0], 0)
        self.assertTrue(all(a[1] == b[0] for a, b in zip(edges, edges[1:])), edges)  # nothing left out, nothing repeated
        line = text.split("\n")[1]
        self.assertEqual(edges[-1][1], len(line))

    def test_id_led_element_with_a_long_body_is_cut(self):
        body = "\n".join(f"Linea {i}: la jefa de Compras revisa el caso numero {i}." for i in range(120))
        parts = parse_request_elements(f"## RN-07 Aprobacion\n{body}\n", "F-01", "x.md")
        self.assertGreater(len(parts), 5)
        self.assertTrue(all(p["id"].startswith("RN-07.p") and p["parent"] == "RN-07" and p["kind"] == "rule" for p in parts))
        self.assertTrue(all(p["lines"][1] - p["lines"][0] + 1 <= PART_MAX_LINES for p in parts))
        self.assertEqual(parts[0]["lines"][0], 1)
        self.assertEqual(parts[-1]["lines"][1], 121)

    def test_short_id_elements_are_not_cut(self):
        parts = parse_request_elements("## RN-07 Aprobacion\nLa jefa revisa el caso.\n", "F-01", "x.md")
        self.assertEqual([p["id"] for p in parts], ["RN-07"])

    def test_an_edit_above_leaves_the_parts_after_it_with_their_text_and_id(self):
        """I3: a living request gets a line near the top; the confirmed parts after it stay the same elements."""
        items = [f"- paso {i}: la jefa de Compras revisa el caso numero {i}" for i in range(1, 61)]
        before = parse_request_elements("## Proceso\n" + "\n".join(items) + "\n", "F-01", "x.md")
        edited = ["- paso 0: se agrega un paso nuevo al principio", *items]
        after = parse_request_elements("## Proceso\n" + "\n".join(edited) + "\n", "F-01", "x.md")
        _assign_parts(after, {"elements": before})
        old = {p["sha"]: p["id"] for p in before}
        kept = [p for p in after if p["sha"] in old]
        self.assertGreaterEqual(len(kept), len(after) - 2, [p["id"] for p in after])
        self.assertTrue(all(old[p["sha"]] == p["id"] for p in kept))
        self.assertEqual(len({p["id"] for p in after}), len(after))  # still unique
        # the changed part takes a free slot or a new number, never the id of a part that kept its text
        taken = {p["id"] for p in kept}
        self.assertTrue(all(p["id"] not in taken for p in after if p not in kept))


class LongUnits(SnapshotWorkspaceCase):
    """I1 end to end: a request of one long paragraph and a heading with 120 lines of prose."""

    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        body = "\n".join(f"Linea {i}: la jefa de Compras revisa el caso numero {i} del alta." for i in range(120))
        (root / "pedido.md").write_text(
            "# Pedido de cambio\n\n## Objetivo\nQueremos que el alta de proveedores pase por una bandeja de aprobaciones.\n\n"
            f"## Proceso\n{sentence_line(500)}\n\n## RN-07 Aprobacion de altas\n{body}\n", encoding="utf-8")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", "LNG"])
        run_ok(["ingest", "LNG", "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", "LNG", "--source", "scope.md", "--change", CID])
        run_ok(["sources", "LNG", "--load", str(FIXTURES / "change_baseline" / "sad-compras.md"),
                "--role", "linea_de_base", "--change", CID])
        waive_crosses("LNG", CID)
        build_inventory("LNG", CID)

    def elements(self) -> dict[str, dict]:
        forget_read_snapshots()
        return {e["id"]: e for e in load_inventory(workspace_path("LNG"), CID)["elements"]}

    def submit(self, text: str) -> dict:
        path = Path.cwd() / "p.md"
        path.write_text(text, encoding="utf-8")
        return record_proposals("LNG", CID, path)

    def quote(self, element_id: str, start: int = 0, size: int = 60) -> str:
        element = self.elements()[element_id]
        flat = " ".join((element_text(workspace_path("LNG"), element) or "").split())
        return flat[start : start + size].strip()

    def test_no_element_is_bigger_than_a_reading(self):
        found = self.elements()
        self.assertTrue(all(e["chars"] <= PART_MAX_CHARS for e in found.values()), {k: v["chars"] for k, v in found.items()})
        self.assertIn("SEC-objetivo", found)
        self.assertNotIn("SEC-proceso", found)
        self.assertNotIn("RN-07", found)
        self.assertTrue([i for i in found if i.startswith("SEC-proceso.p")])
        self.assertTrue([i for i in found if i.startswith("RN-07.p")])

    def test_one_quote_and_the_line_does_not_cover_a_long_line(self):
        """The reviewer's scenario: one `Cita` and the line of the paragraph used to be `completa`."""
        first, second = "SEC-proceso.p1", "SEC-proceso.p2"
        line = self.elements()[first]["lines"][0]
        block = (f"### {first}\n- Tratamiento: seccion\n- Líneas: {line}-{line}\n- Seccion: proceso\n"
                 f'- Cita: "{self.quote(first)}"\n')
        result = self.submit(block)
        self.assertEqual(result["recorded"], [first], result)
        forget_read_snapshots()
        self.assertEqual(run_extract("LNG", CID, confirm="all")["confirmed"], [first])
        coverage = extraction_coverage("LNG", CID)
        self.assertEqual(coverage["covered"], 1)
        self.assertFalse(coverage["complete"])
        self.assertGreater(coverage["pending"], 10)
        # the quote of the next piece is not in this one: the second piece cannot ride on the first reading
        bad = block.replace(first, second).replace(self.quote(first), self.quote(first))
        rejected = self.submit(bad)
        self.assertEqual(rejected["recorded"], [], rejected)
        self.assertIn("la cita no aparece literal", " ".join(rejected["rejected"][second]))

    def test_one_quote_does_not_cover_a_heading_with_120_lines(self):
        found = self.elements()
        first = found["RN-07.p1"]
        first_line, last_line = found["RN-07.p1"]["lines"][0], found["RN-07.p1"]["lines"][1]
        final_line = max(e["lines"][1] for i, e in found.items() if i.startswith("RN-07.p"))
        block = (f"### RN-07.p1\n- Tratamiento: descarte\n- Líneas: {first_line}-{final_line}\n"
                 f'- Motivo: se trata en otro cambio\n- Cita: "{self.quote("RN-07.p1")}"\n')
        rejected = self.submit(block)
        self.assertEqual(rejected["recorded"], [], rejected)
        self.assertIn("fuera del elemento", " ".join(rejected["rejected"]["RN-07.p1"]))
        self.assertLess(last_line, final_line)
        ok = self.submit(block.replace(f"{first_line}-{final_line}", f"{first_line}-{last_line}"))
        self.assertEqual(ok["recorded"], ["RN-07.p1"], ok)

    def test_verbatim_part_text_is_the_piece_of_the_line(self):
        first = "SEC-proceso.p1"
        line = self.elements()[first]["lines"][0]
        self.submit(f"### {first}\n- Tratamiento: seccion\n- Líneas: {line}-{line}\n- Seccion: proceso\n"
                    f'- Cita: "{self.quote(first)}"\n')
        run_extract("LNG", CID, confirm="all")
        forget_read_snapshots()
        entries = read_json(extraction_dir(workspace_path("LNG"), CID) / "sections.json", {})["entries"]
        content = next(e["content"] for e in entries if e["element"] == first)
        self.assertEqual(" ".join(content.split()), " ".join((element_text(workspace_path("LNG"), self.elements()[first]) or "").split()))
        self.assertLessEqual(len(content), PART_MAX_CHARS)


class VerifyCase(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(LARGO, root / "pedido.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", "FIN"])
        run_ok(["ingest", "FIN", "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", "FIN", "--source", "scope.md", "--change", CID])
        run_ok(["sources", "FIN", "--load", str(FIXTURES / "change_baseline" / "sad-compras.md"),
                "--role", "linea_de_base", "--change", CID])
        complete_extraction("FIN", CID)

    def setUp(self):
        super().setUp()
        forget_read_snapshots()

    def results(self, sample: list[str], name: str = "r.md") -> Path:
        path = Path.cwd() / name
        path.write_text("\n".join(["## Resultados", *(f"- {i}: igual" for i in sample), ""]), encoding="utf-8")
        return path

    def test_legacy_confirmed_items_are_listed_and_hold_the_verdict(self):
        """I2: items confirmed under 0.26 (no `Líneas`) stay confirmed but are named, and READY is out of reach."""
        path = extraction_dir(workspace_path("FIN"), CID) / "proposals.json"
        data = read_json(path, None)
        legacy = sorted(data["items"])[:3]
        for element_id in legacy:
            data["items"][element_id]["lines"] = []
            data["items"][element_id].pop("reading", None)
        write_json(path, data)
        forget_read_snapshots()
        coverage = extraction_coverage("FIN", CID)
        self.assertEqual(sorted(coverage["legacy_ids"]), legacy)
        self.assertEqual(coverage["covered"], coverage["total"])  # confirmed work is not lost
        verdict = build_change_verdict("FIN", CID)
        self.assertTrue(any("sin control de líneas" in w and legacy[0] in w for w in verdict["warnings"]), verdict["warnings"])
        self.assertNotEqual(verdict["verdict"], "READY")
        warnings = [w for w in change_status("FIN", CID)["warnings"] if w["trigger"] == "legacy_confirmed"]
        self.assertEqual(len(warnings), 1)
        self.assertIn(legacy[1], warnings[0]["message"])
        # the sample draws them first
        sample = run_extract("FIN", CID, verify=True, sample=3)["sample"]
        self.assertEqual(sorted(sample), legacy)

    def test_the_default_sample_scales_and_a_big_extraction_is_led_to_verify(self):
        """I5: `/next` names the verification step, the sample is 5 % of the confirmed, and a stale run asks again."""
        self.assertEqual((sample_size(100), sample_size(300), sample_size(1000)), (10, 15, 50))
        with patch("sentinel.extraction.verify.VERIFY_ABOVE", 5):
            self.assertEqual(change_next_step("FIN", CID)["key"], "extract_verify")
            step = change_next_step("FIN", CID)
            self.assertEqual(step["command"], f"/extract FIN --change {CID} --verify")
            self.assertIn("No frena el veredicto", step["text"])
            self.assertEqual(verification_needed("FIN", CID)["sample"], 10)
            sample = run_extract("FIN", CID, verify=True)["sample"]
            self.assertEqual(len(sample), 10)  # max(10, 5 % of the 26 confirmed)
            step = change_next_step("FIN", CID)
            self.assertEqual((step["key"], step["command"]), ("extract_verify", f"/extract FIN --change {CID} --verify-result PATH"))
            run_extract("FIN", CID, verify_result=str(self.results(sample)))
            forget_read_snapshots()
            self.assertEqual(change_next_step("FIN", CID)["key"], "brief")
            last = verification_status("FIN", CID)["last"]
            self.assertEqual(last["confirmed_count"], 26)
            self.assertTrue(last["fingerprint"])
            # 300 more confirmed later: the old run no longer covers what is confirmed now
            path = extraction_dir(workspace_path("FIN"), CID) / "verification.json"
            store = read_json(path, None)
            store["runs"][-1]["confirmed_count"] = 10
            write_json(path, store)
            forget_read_snapshots()
            self.assertEqual(change_next_step("FIN", CID)["key"], "extract_verify")
            warnings = [w for w in change_status("FIN", CID)["warnings"] if w["trigger"] == "verification_missing"]
            self.assertEqual(len(warnings), 1)
            self.assertIn("la última verificación vio 10 de 26 confirmados", warnings[0]["message"])
        self.assertEqual(change_next_step("FIN", CID)["key"], "brief")  # a small extraction is never led here

    def test_bare_note_after_the_verdict_and_not_reopened(self):
        """M6 and M8: `- ID: difiere falta algo` is a result; an element taken out meanwhile is reported."""
        sample = run_extract("FIN", CID, verify=True, sample=2)["sample"]
        path = Path.cwd() / "r.md"
        path.write_text(f"## Resultados\n- {sample[0]}: difiere falta el plazo\n- {sample[1]}: igual\n", encoding="utf-8")
        out = run_extract("FIN", CID, verify_result=str(path))
        self.assertEqual(out["reopened"], [sample[0]])
        again = run_extract("FIN", CID, verify=True, sample=2)["sample"]
        store_path = extraction_dir(workspace_path("FIN"), CID) / "proposals.json"
        data = read_json(store_path, None)
        data["items"][again[0]]["status"] = "proposed"  # nothing to reopen any more
        write_json(store_path, data)
        forget_read_snapshots()
        path.write_text(f"## Resultados\n- {again[0]}: difiere — cambió\n- {again[1]}: igual\n", encoding="utf-8")
        out = run_extract("FIN", CID, verify_result=str(path))
        self.assertEqual((out["differs"], out["reopened"], out["not_reopened"]), ([again[0]], [], [again[0]]))
        self.assertIn(f"no se reabrieron (ya no estaban confirmados): {again[0]}", out["message"])


class FinalGuards(ExportCase):
    """I6, I7 and I8 on the change of the export tests."""

    def final(self) -> tuple[int, str]:
        """`export --final`: the exit code and what it printed (stdout and stderr together)."""
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            code = main(["export", EXPORT_PID, "--artifact", "brief", "--change", CID, "--final"])
        return code, out.getvalue()

    def test_final_refuses_while_the_verdict_is_not_ready(self):
        """I6: the seal cannot say final and NOT_READY; the refusal names the items and the command."""
        held = [d["id"] for d in deferred_gaps(EXPORT_PID, CID) if d["impact"] == "construccion"]
        self.assertTrue(held)
        code, out = self.final()
        self.assertEqual(code, 4, out)  # gate refusal
        self.assertIn("NOT_READY", out)
        self.assertIn(held[0], out)
        self.assertIn(f"/gaps {EXPORT_PID} --change {CID} --id {held[0]} --impact operativo --reason TEXTO", out)
        self.assertEqual(self.final_export(), {})
        draft = json.loads(run_ok(["export", EXPORT_PID, "--artifact", "brief", "--change", CID]))
        self.assertIn("**Estado:** borrador", Path(draft["path"]).read_text(encoding="utf-8"))
        # /next leads to the fix, not to the refused export
        step = self.next_step()
        self.assertEqual(step["key"], "export_final")
        self.assertIn(f"/gaps {EXPORT_PID} --change {CID} --id {held[0]} --impact", step["command"])
        class_deferred(EXPORT_PID, CID)
        code, out = self.final()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.final_export()["verdict"], "READY_WITH_WARNINGS")

    def test_final_refuses_in_english(self):
        self.set_language("en")
        run_ok(["brief", EXPORT_PID, "--change", CID])
        code, out = self.final()
        self.assertEqual(code, 4, out)
        self.assertIn("/export --final refused: the verdict of CHG-001 is NOT_READY", out)
        self.assertIn("Items that hold back the build", out)

    def test_final_export_goes_stale_when_the_seal_inputs_change(self):
        """I7 A: same internal brief, but the deferred classes the seal printed are not the ones that stand now."""
        class_deferred(EXPORT_PID, CID)
        code, _ = self.final()
        self.assertEqual(code, 0)
        forget_read_snapshots()
        self.assertEqual(self.next_step()["key"], "specs")
        self.assertTrue(self.final_export()["seal_sha"])
        gap = deferred_gaps(EXPORT_PID, CID)[0]["id"]
        run_ok(["gaps", EXPORT_PID, "--change", CID, "--id", gap, "--impact", "construccion", "--reason", "cambió de idea"])
        forget_read_snapshots()
        status = json.loads(run_ok(["status", EXPORT_PID, "--change", CID]))
        self.assertFalse(status["final_export_current"])
        self.assertEqual(self.next_step()["key"], "export_final")
        # and classing it back makes the very same seal current again
        run_ok(["gaps", EXPORT_PID, "--change", CID, "--id", gap, "--impact", "operativo", "--reason", "otra vez"])
        forget_read_snapshots()
        status = json.loads(run_ok(["status", EXPORT_PID, "--change", CID]))
        self.assertTrue(status["final_export_current"])

    def test_final_refuses_pending_marks_in_the_exported_text(self):
        """I7 B: a confirmed statement that says «a definir» is a pending mark of the v2 text; `--final` does not seal it."""
        path = Path.cwd() / "tbd.md"
        path.write_text(reproposal_block(EXPORT_PID, CID, "HU-01").replace("en todos los casos", "con un monto a definir"),
                        encoding="utf-8")
        result = record_proposals(EXPORT_PID, CID, path)
        self.assertEqual(result["recorded"], ["HU-01"], result)
        confirm_item(EXPORT_PID, CID, "HU-01")
        run_ok(["brief", EXPORT_PID, "--change", CID])
        class_deferred(EXPORT_PID, CID)
        forget_read_snapshots()
        code, out = self.final()
        self.assertEqual(code, 4, out)
        self.assertIn("pending marks remain in the brief that would be exported", out)
        self.assertEqual(self.final_export(), {})

    def test_verdict_is_not_ready_when_the_brief_is_not_current(self):
        """I8: a brief that went stale after a reopen is not READY, and the verdict names the gate."""
        class_deferred(EXPORT_PID, CID)
        forget_read_snapshots()
        self.assertEqual(build_change_verdict(EXPORT_PID, CID)["verdict"], "READY_WITH_WARNINGS")
        sample = run_extract(EXPORT_PID, CID, verify=True, sample=1)["sample"]
        path = Path.cwd() / "r.md"
        path.write_text(f"## Resultados\n- {sample[0]}: difiere — falta algo\n", encoding="utf-8")
        run_extract(EXPORT_PID, CID, verify_result=str(path))
        forget_read_snapshots()
        verdict = build_change_verdict(EXPORT_PID, CID)
        self.assertEqual(verdict["verdict"], "NOT_READY")
        status = json.loads(run_ok(["status", EXPORT_PID, "--change", CID]))
        self.assertEqual(status["verdict"]["verdict"], "NOT_READY")
        self.assertTrue(any(g["gate"] == "extraction" and g["blocks"] for g in verdict["gate_matrix"]))

    def test_verdict_is_not_ready_without_requirement_rows(self):
        """I8: everything is discarded and the crosses are waived; /next says `requirements`, and so does the verdict."""
        class_deferred(EXPORT_PID, CID)
        with patch("sentinel.readiness_verdict._has_unit_rows", return_value=False):
            verdict = build_change_verdict(EXPORT_PID, CID)
            self.assertEqual(verdict["verdict"], "NOT_READY")
            self.assertIn("el cambio no tiene filas EARS con Delta ADDED, MODIFIED o REMOVED", verdict["blockers"])
            self.assertEqual(change_next_step(EXPORT_PID, CID)["key"], "requirements")
            code, out = self.final()
            self.assertEqual(code, 4, out)


class Minors(unittest.TestCase):
    def test_mcp_descriptions_mention_the_new_options(self):
        from sentinel import mcp as sentinel_mcp

        specs = {name: description for name, description, _ in sentinel_mcp.TOOL_SPECS}
        self.assertIn("impact", specs["gaps"])
        self.assertIn("final", specs["export"])
        self.assertIn("seal", specs["export"])


if __name__ == "__main__":
    unittest.main()
