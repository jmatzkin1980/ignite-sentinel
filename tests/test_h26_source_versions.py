"""IMP-400 (H26 inc 2): a request that cites another version of a loaded source opens GAP-VER-*."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402

from sentinel.changes import list_changes  # noqa: E402
from sentinel.core.hashing import file_content_hash  # noqa: E402
from sentinel.source_versions import (  # noqa: E402
    check_change_versions, cited_references, same_document, version_key, version_marks,
)
from sentinel.sources import open_source_row  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
VERSIONS = FIXTURES / "change_versions"
PEDIDO = VERSIONS / "pedido_con_citas.md"
SAD_V2 = VERSIONS / "sad-compras-v2.md"
BORRADOR = FIXTURES / "change_borrador.md"


def gap_ids(project_id: str, change: str = "CHG-001") -> list[str]:
    text = (workspace_path(project_id) / "01_discovery" / change / "gaps.md").read_text(encoding="utf-8")
    return re.findall(r"^\|\s*`?(GAP-[A-Z0-9-]+)`?\s*\|", text, re.M)


def load_baseline(project_id: str) -> dict:
    argv = ["sources", project_id, "--load", str(SAD_V2), "--role", "linea_de_base", "--change", "CHG-001"]
    return json.loads(run_ok(argv))


def blocking(project_id: str) -> int:
    return list_changes(project_id)["CHG-001"]["gap_counts"]["blocking_open"]


class CitedReferences(unittest.TestCase):
    def test_cited_references_names_and_sha(self):
        refs = cited_references(PEDIDO.read_text(encoding="utf-8"))
        sad = next(r for r in refs if r["name"] == "sad-compras-v3.md")
        self.assertEqual(sad["sha"], "3f2a9c1")
        manual = next(r for r in refs if r["name"] == "manual-compras.md")
        self.assertIsNone(manual["sha"])
        self.assertGreater(manual["line"], 0)

    def test_version_key_strips_versions(self):
        self.assertEqual(version_key("SAD-Compras_v3.1.docx"), "sad-compras")
        self.assertEqual(version_key("sad-compras-v2.md"), "sad-compras")
        self.assertEqual(version_key("sad-compras-v3.md"), version_key("SAD-Compras_v3.1.docx"))
        self.assertEqual(version_key("relevamiento-2026-10-01.md"), "relevamiento")


class VersionGaps(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        shutil.copy(PEDIDO, Path.cwd() / "pedido.md")
        run_ok(["init", "VER"])
        run_ok(["ingest", "VER", "--source", "pedido.md", "--change"])

    def _project_with_request(self, project_id: str, citation: str) -> None:
        text = PEDIDO.read_text(encoding="utf-8").split("## Fuentes consultadas")[0]
        (Path.cwd() / f"{project_id}.md").write_text(f"{text}\n## Fuentes consultadas\n\n- {citation}\n", encoding="utf-8")
        run_ok(["init", project_id])
        run_ok(["ingest", project_id, "--source", f"{project_id}.md", "--change"])

    def test_mismatched_version_opens_one_blocking_gap(self):
        before = blocking("VER")
        self.assertEqual([g for g in gap_ids("VER") if g.startswith("GAP-VER-")], [])
        result = load_baseline("VER")
        opened = [g for g in gap_ids("VER") if g.startswith("GAP-VER-")]
        self.assertEqual(len(opened), 1)
        self.assertEqual(result["version_gaps"], opened)
        self.assertEqual(blocking("VER"), before + 1)
        text = (workspace_path("VER") / "01_discovery" / "CHG-001" / "gaps.md").read_text(encoding="utf-8")
        self.assertIn("sad-compras-v3.md", text)
        self.assertIn("sad-compras-v2.md", text)
        again = load_baseline("VER")  # the same content: the same id, no second row
        self.assertEqual(again["version_gaps"], [])
        self.assertEqual([g for g in gap_ids("VER") if g.startswith("GAP-VER-")], opened)
        self.assertEqual(blocking("VER"), before + 1)

    def test_matching_name_and_sha_opens_nothing(self):
        self._project_with_request("OKV", f"Arquitectura vigente: sad-compras-v2.md (sha256: {file_content_hash(SAD_V2)[:12]})")
        result = load_baseline("OKV")
        self.assertEqual(result["version_gaps"], [])
        self.assertEqual([g for g in gap_ids("OKV") if g.startswith("GAP-VER-")], [])
        report = check_change_versions("OKV", "CHG-001")
        self.assertEqual([m["cited"] for m in report["matched"]], ["sad-compras-v2.md"])
        self.assertEqual(report["mismatched"], [])

    def test_sha_mismatch_opens_gap(self):
        self._project_with_request("SHA", "Arquitectura vigente: sad-compras-v2.md (sha256: deadbeef12)")
        result = load_baseline("SHA")
        self.assertEqual(len(result["version_gaps"]), 1)
        self.assertEqual([g for g in gap_ids("SHA") if g.startswith("GAP-VER-")], result["version_gaps"])
        report = check_change_versions("SHA", "CHG-001")
        self.assertEqual(report["mismatched"][0]["reason"], "sha")

    def test_not_loaded_opens_nothing(self):
        load_baseline("VER")
        report = check_change_versions("VER", "CHG-001")
        self.assertEqual([r["cited"] for r in report["not_loaded"]], ["manual-compras.md"])
        self.assertEqual([r["cited"] for r in report["mismatched"]], ["sad-compras-v3.md"])
        self.assertEqual(report["mismatched"][0]["reason"], "version")
        self.assertEqual(len([g for g in gap_ids("VER") if g.startswith("GAP-VER-")]), 1)

    def _ver(self, project_id):
        return [g for g in gap_ids(project_id) if g.startswith("GAP-VER-")]

    def _request(self, project_id: str, body: str) -> None:
        (Path.cwd() / f"{project_id}.md").write_text(
            PEDIDO.read_text(encoding="utf-8").split("## Fuentes consultadas")[0] + "\n## Fuentes consultadas\n\n" + body, encoding="utf-8")

    def test_two_stale_documents_open_two_distinct_gaps(self):
        proto = VERSIONS / "prototipo-alta.md"
        self._request("TWO", "- sad-compras-v3.md\n- prototipo-alta-v2.md\n")
        run_ok(["init", "TWO"])
        run_ok(["sources", "TWO", "--load", str(SAD_V2), "--role", "linea_de_base"])
        run_ok(["sources", "TWO", "--load", str(proto), "--role", "diseno_nuevo"])
        out = json.loads(run_ok(["ingest", "TWO", "--source", "TWO.md", "--change"]))
        ids = self._ver("TWO")
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(out["gap_counts"]["blocking_open"], 3 + 2)
        self.assertEqual(blocking("TWO"), 5)
        gaps = workspace_path("TWO") / "01_discovery" / "CHG-001" / "gaps.md"
        gaps.write_text("\n".join(l for l in gaps.read_text(encoding="utf-8").splitlines() if "GAP-VER-" not in l) + "\n", encoding="utf-8")
        self.assertEqual(sorted(check_change_versions("TWO", "CHG-001")["opened"]), sorted(ids))

    def test_load_without_change_checks_every_change(self):
        out = json.loads(run_ok(["sources", "VER", "--load", str(SAD_V2), "--role", "linea_de_base"]))
        self.assertEqual(len(out["version_gaps"]), 1)
        self.assertEqual(self._ver("VER"), out["version_gaps"])
        self.assertEqual(blocking("VER"), 4)

    def test_baseline_loaded_before_the_change_opens_gap_at_ingest(self):
        self._request("PRE", "- sad-compras-v3.md (sha256: 3f2a9c1)\n")
        run_ok(["init", "PRE"])
        run_ok(["sources", "PRE", "--load", str(SAD_V2), "--role", "linea_de_base"])
        out = json.loads(run_ok(["ingest", "PRE", "--source", "PRE.md", "--change"]))
        self.assertEqual(len(self._ver("PRE")), 1)
        self.assertEqual(out["gap_counts"]["blocking_open"], 4)

    def test_sha_of_another_row_does_not_match_the_name(self):
        proto = VERSIONS / "prototipo-alta.md"
        self._request("OTH", f"- sad-compras-v2.md (sha256: {file_content_hash(proto)[:12]})\n")
        run_ok(["init", "OTH"])
        run_ok(["sources", "OTH", "--load", str(proto), "--role", "diseno_nuevo"])
        run_ok(["ingest", "OTH", "--source", "OTH.md", "--change"])
        out = json.loads(run_ok(["sources", "OTH", "--load", str(SAD_V2), "--role", "linea_de_base", "--change", "CHG-001"]))
        self.assertEqual(len(out["version_gaps"]), 1)
        report = check_change_versions("OTH", "CHG-001")
        self.assertEqual(report["matched"], [])
        self.assertEqual(report["mismatched"][0]["reason"], "sha")

    def _gap_line(self, project_id: str) -> str:
        text = (workspace_path(project_id) / "01_discovery" / "CHG-001" / "gaps.md").read_text(encoding="utf-8")
        lines = [line for line in text.splitlines() if "GAP-VER-" in line and line.lstrip().startswith("|")]
        self.assertEqual(len(lines), 1, lines)
        return lines[0]

    def test_option_b_names_the_loaded_role(self):  # final review 2
        proto = VERSIONS / "prototipo-alta.md"
        self._request("DIS", "- prototipo-alta-v2.md\n")
        run_ok(["init", "DIS"])
        run_ok(["ingest", "DIS", "--source", "DIS.md", "--change"])
        out = json.loads(run_ok(["sources", "DIS", "--load", str(proto), "--role", "diseno_nuevo", "--change", "CHG-001"]))
        self.assertEqual(len(out["version_gaps"]), 1)
        line = self._gap_line("DIS")
        self.assertIn("--role diseno_nuevo", line)
        self.assertNotIn("--role linea_de_base", line)

    def test_raw_sha_of_a_crlf_file_matches(self):  # final review 3
        crlf = Path.cwd() / "sad-compras-v2.md"
        crlf.write_bytes(SAD_V2.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        raw = hashlib.sha256(crlf.read_bytes()).hexdigest()
        self.assertNotEqual(raw, file_content_hash(crlf))
        self._request("CRL", f"- sad-compras-v2.md (sha256: {raw[:12]})\n")
        run_ok(["init", "CRL"])
        run_ok(["ingest", "CRL", "--source", "CRL.md", "--change"])
        out = json.loads(run_ok(["sources", "CRL", "--load", str(crlf), "--role", "linea_de_base", "--change", "CHG-001"]))
        self.assertEqual(out["version_gaps"], [])
        self.assertEqual(self._ver("CRL"), [])
        report = check_change_versions("CRL", "CHG-001", write=False)
        self.assertEqual([m["cited"] for m in report["matched"]], ["sad-compras-v2.md"])
        self.assertEqual(report["mismatched"], [])

    def test_same_document_in_another_format_matches(self):  # final review 5
        self.assertTrue(same_document("SAD_Compras_v3.pdf", "sad compras v3.docx"))
        self.assertFalse(same_document("SAD_Compras_v3.pdf", "sad compras v2.docx"))
        self.assertEqual(version_marks("SAD_Compras_v3.1.pdf"), ("v3.1",))
        loaded = Path.cwd() / "SAD Compras v3.md"
        loaded.write_text(SAD_V2.read_text(encoding="utf-8"), encoding="utf-8")
        self._request("FMT", "- SAD_Compras_v3.pdf\n")
        run_ok(["init", "FMT"])
        run_ok(["ingest", "FMT", "--source", "FMT.md", "--change"])
        out = json.loads(run_ok(["sources", "FMT", "--load", str(loaded), "--role", "linea_de_base", "--change", "CHG-001"]))
        self.assertEqual(out["version_gaps"], [])
        report = check_change_versions("FMT", "CHG-001", write=False)
        self.assertEqual([m["cited"] for m in report["matched"]], ["SAD_Compras_v3.pdf"])

    def test_role_fix_rechecks_versions(self):  # final review 8
        folder = workspace_path("VER") / "00_raw" / "04_quality_context"
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy(SAD_V2, folder / "sad-compras-v2.md")
        # A registered row with no role (the way /sync opens it) is not compared yet.
        source_id = open_source_row("VER", folder / "sad-compras-v2.md", "synced")
        self.assertEqual(check_change_versions("VER", "CHG-001", write=False)["mismatched"], [])
        out = json.loads(run_ok(["sources", "VER", "--id", source_id, "--role", "linea_de_base"]))
        self.assertEqual(len(out["version_gaps"]), 1)
        self.assertEqual(self._ver("VER"), out["version_gaps"])

    def test_role_fix_from_plan_previo_reopens_a_missing_gap(self):  # final review 8
        first = json.loads(run_ok(["sources", "VER", "--load", str(SAD_V2), "--role", "plan_previo", "--change", "CHG-001"]))
        gaps = workspace_path("VER") / "01_discovery" / "CHG-001" / "gaps.md"
        gaps.write_text("\n".join(l for l in gaps.read_text(encoding="utf-8").splitlines() if "GAP-VER-" not in l) + "\n",
                        encoding="utf-8")
        out = json.loads(run_ok(["sources", "VER", "--id", first["source_id"], "--role", "linea_de_base"]))
        self.assertEqual(out["version_gaps"], first["version_gaps"])
        self.assertIn("--role linea_de_base", self._gap_line("VER"))

    def test_gap_id_ignores_the_case_of_the_cited_name(self):  # final review 11
        v2 = Path.cwd() / "sad-v2.md"
        v2.write_text(SAD_V2.read_text(encoding="utf-8"), encoding="utf-8")
        self._request("CAS", "- SAD-v3.md\n- sad-v3.md\n")
        run_ok(["init", "CAS"])
        run_ok(["ingest", "CAS", "--source", "CAS.md", "--change"])
        out = json.loads(run_ok(["sources", "CAS", "--load", str(v2), "--role", "linea_de_base", "--change", "CHG-001"]))
        expected = "GAP-VER-" + hashlib.sha256("CHG-001|sad-v3.md".encode("utf-8")).hexdigest()[:6].upper()
        self.assertEqual(out["version_gaps"], [expected])
        self.assertEqual(self._ver("CAS"), [expected])

    def test_borrador_fixture_unchanged(self):
        shutil.copy(BORRADOR, Path.cwd() / "borrador.md")
        run_ok(["init", "BRD"])
        run_ok(["ingest", "BRD", "--source", "borrador.md", "--change"])
        self.assertEqual(
            gap_ids("BRD"), ["GAP-OBJECTIVE", "GAP-USERS", "GAP-SCOPE", "GAP-PRODUCT-ASIS-TOBE"])
        self.assertEqual(blocking("BRD"), 3)


if __name__ == "__main__":
    unittest.main()
