"""IMP-400 (H26 inc 2): a request that cites another version of a loaded source opens GAP-VER-*."""
from __future__ import annotations

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
from sentinel.source_versions import check_change_versions, cited_references, version_key  # noqa: E402
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

    def test_borrador_fixture_unchanged(self):
        shutil.copy(BORRADOR, Path.cwd() / "borrador.md")
        run_ok(["init", "BRD"])
        run_ok(["ingest", "BRD", "--source", "borrador.md", "--change"])
        self.assertEqual(
            gap_ids("BRD"), ["GAP-OBJECTIVE", "GAP-USERS", "GAP-SCOPE", "GAP-PRODUCT-ASIS-TOBE"])
        self.assertEqual(blocking("BRD"), 3)


if __name__ == "__main__":
    unittest.main()
