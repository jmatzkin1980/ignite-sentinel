from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from sentinel.adapters import load_manifest
from sentinel.lens_registry import clear_cache as clear_lens_cache
from sentinel.lens_registry import load_lens_checks
from sentinel.resources import read_package_json
from sentinel.retrieval_plans import clear_cache as clear_plan_cache
from sentinel.retrieval_plans import load_retrieval_plan
from sentinel.slicing_model import clear_cache as clear_slicing_cache
from sentinel.slicing_model import load_slicing_model
from sentinel.technique_registry import clear_cache as clear_technique_cache
from sentinel.technique_registry import load_techniques


ROOT = Path(__file__).resolve().parents[1]
SENTINEL_ROOT = ROOT / "sentinel"


class PackageResourceLoadingTest(unittest.TestCase):
    def tearDown(self) -> None:
        clear_lens_cache()
        clear_plan_cache()
        clear_slicing_cache()
        clear_technique_cache()

    def test_default_loaders_match_filesystem_overrides(self) -> None:
        manifest_path = SENTINEL_ROOT / "templates" / "commands_manifest.json"
        self.assertEqual(load_manifest(), json.loads(manifest_path.read_text(encoding="utf-8")))

        default_lenses = load_lens_checks()
        filesystem_lenses = load_lens_checks(SENTINEL_ROOT / "lenses")
        self.assertEqual(default_lenses, filesystem_lenses)

        default_techniques = load_techniques()
        filesystem_techniques = load_techniques(SENTINEL_ROOT / "techniques")
        self.assertEqual(default_techniques, filesystem_techniques)

        default_plan = load_retrieval_plan("specs_generation")
        filesystem_plan = load_retrieval_plan("specs_generation", plans_dir=SENTINEL_ROOT / "retrieval_plans")
        self.assertEqual(default_plan, filesystem_plan)

        default_slicing = load_slicing_model()
        filesystem_slicing = load_slicing_model(SENTINEL_ROOT / "slicing")
        self.assertEqual(default_slicing, filesystem_slicing)

    def test_package_json_reader_loads_schemas(self) -> None:
        schema = read_package_json("schemas", "gap.schema.json")

        self.assertEqual("Ignite Sentinel Gap", schema["title"])

    def test_package_data_declares_resource_directories(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

        for pattern in (
            "schemas/*.json",
            "templates/*.json",
            "lenses/*.json",
            "techniques/*.json",
            "retrieval_plans/*.json",
            "slicing/*.json",
        ):
            self.assertIn(pattern, pyproject)

    def test_resource_loaders_work_from_zipimport(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            package_zip = temp / "sentinel_package.zip"
            self._write_package_zip(package_zip)
            code = "\n".join(
                [
                    "import json",
                    "from sentinel.adapters import load_manifest",
                    "from sentinel.lens_registry import load_lens_checks",
                    "from sentinel.resources import read_package_json",
                    "from sentinel.retrieval_plans import load_retrieval_plan",
                    "from sentinel.slicing_model import load_slicing_model",
                    "from sentinel.technique_registry import load_techniques",
                    "print(json.dumps({",
                    "  'commands': len(load_manifest()['commands']),",
                    "  'lens_count': len(load_lens_checks()),",
                    "  'technique_count': len(load_techniques()),",
                    "  'workflow': load_retrieval_plan('specs_generation')['workflow'],",
                    "  'slicing_model': load_slicing_model()['model'],",
                    "  'gap_schema': read_package_json('schemas', 'gap.schema.json')['title'],",
                    "}, sort_keys=True))",
                ]
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(package_zip)
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=temp,
                env=env,
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(0, result.returncode, result.stderr + result.stdout)

        payload = json.loads(result.stdout)
        self.assertEqual(len(load_manifest()["commands"]), payload["commands"])
        self.assertEqual(len(load_lens_checks()), payload["lens_count"])
        self.assertEqual(len(load_techniques()), payload["technique_count"])
        self.assertEqual("specs_generation", payload["workflow"])
        self.assertEqual("backlog_slicing", payload["slicing_model"])
        self.assertEqual("Ignite Sentinel Gap", payload["gap_schema"])

    def _write_package_zip(self, target: Path) -> None:
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(SENTINEL_ROOT.rglob("*")):
                if not path.is_file():
                    continue
                if "__pycache__" in path.parts or path.suffix == ".pyc":
                    continue
                archive.write(path, path.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    unittest.main()
