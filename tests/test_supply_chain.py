"""Supply chain guards (IMP-289).

- ``tools/check_constraints.py``: every optional extra has a hash-pinned lock in
  ``constraints/<extra>.txt``; a requirement without ``==`` or without a hash fails.
- ``tools/sbom.py``: a CycloneDX SBOM built (stdlib only) from ``pyproject.toml``
  and the constraints.
- Static checks over ``.github``: actions pinned by commit SHA, explicit
  ``permissions``, Dependabot for GitHub Actions.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))
import check_constraints  # noqa: E402
import sbom  # noqa: E402

HASH_A = "a" * 64
HASH_B = "b" * 64

PYPROJECT = """[build-system]
requires = ["setuptools>=68"]

[project]
name = "demo-pkg"
version = "1.2.3"
license = {text = "MIT"}
dependencies = []

[project.optional-dependencies]
alpha = [
  "Foo_Bar>=1"
]
beta = ["baz"]

[project.scripts]
demo = "demo:main"
"""

ALPHA_LOCK = f"""# header comment
foo-bar==1.4.0 \\
    --hash=sha256:{HASH_A} \\
    --hash=sha256:{HASH_B}
colorama==0.4.6 ; sys_platform == 'win32' \\
    --hash=sha256:{HASH_B}
"""

BETA_LOCK = f"baz==2.0 --hash=sha256:{HASH_A}\n"


class TempRepo:
    def __init__(self, files: dict[str, str]):
        self.files = files

    def __enter__(self) -> Path:
        self.root = Path(tempfile.mkdtemp(prefix="sentinel_supply_"))
        for rel, text in self.files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return self.root

    def __exit__(self, *exc) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def demo_repo(**overrides: str) -> TempRepo:
    files = {
        "pyproject.toml": PYPROJECT,
        "constraints/alpha.txt": ALPHA_LOCK,
        "constraints/beta.txt": BETA_LOCK,
    }
    files.update(overrides)
    return TempRepo({k: v for k, v in files.items() if v is not None})


class ParseRequirementsTests(unittest.TestCase):
    def test_joins_continuations_and_reads_markers_and_hashes(self) -> None:
        entries = check_constraints.parse_requirements(ALPHA_LOCK)
        self.assertEqual([e.name for e in entries], ["foo-bar", "colorama"])
        self.assertEqual(entries[0].version, "1.4.0")
        self.assertEqual(entries[0].hashes, [f"sha256:{HASH_A}", f"sha256:{HASH_B}"])
        self.assertEqual(entries[1].marker, "sys_platform == 'win32'")
        self.assertEqual(entries[0].line, 2)

    def test_normalizes_names(self) -> None:
        self.assertEqual(check_constraints.normalize_name("Foo_Bar.baz"), "foo-bar-baz")


class CheckFileTests(unittest.TestCase):
    def check(self, text: str) -> list[str]:
        with TempRepo({"c.txt": text}) as root:
            return check_constraints.check_file(root / "c.txt")

    def test_hash_pinned_file_passes(self) -> None:
        self.assertEqual(self.check(ALPHA_LOCK), [])

    def test_dependency_without_hash_fails(self) -> None:
        errors = self.check(ALPHA_LOCK + "requests==2.0\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("requests", errors[0])
        self.assertIn("hash", errors[0])

    def test_unpinned_dependency_fails(self) -> None:
        errors = self.check(f"requests>=2 --hash=sha256:{HASH_A}\n")
        self.assertTrue(any("==" in e for e in errors), errors)

    def test_weak_or_malformed_hash_fails(self) -> None:
        self.assertTrue(self.check("requests==2.0 --hash=md5:abc\n"))
        self.assertTrue(self.check("requests==2.0 --hash=sha256:xyz\n"))

    def test_editable_url_and_index_options_fail(self) -> None:
        self.assertTrue(self.check("-e .\n"))
        self.assertTrue(self.check(f"pkg @ https://example.invalid/pkg.whl --hash=sha256:{HASH_A}\n"))
        self.assertTrue(self.check("--index-url https://example.invalid/simple\n"))

    def test_empty_file_fails(self) -> None:
        self.assertTrue(self.check("# nothing\n"))


class CheckRepoTests(unittest.TestCase):
    def test_demo_repo_passes(self) -> None:
        with demo_repo() as root:
            self.assertEqual(check_constraints.check_repo(root), [])

    def test_extra_without_lock_fails(self) -> None:
        with demo_repo(**{"constraints/beta.txt": None}) as root:
            errors = check_constraints.check_repo(root)
        self.assertTrue(any("beta" in e for e in errors), errors)

    def test_lock_missing_a_direct_requirement_fails(self) -> None:
        with demo_repo(**{"constraints/beta.txt": f"other==1 --hash=sha256:{HASH_A}\n"}) as root:
            errors = check_constraints.check_repo(root)
        self.assertTrue(any("baz" in e for e in errors), errors)

    def test_orphan_lock_fails(self) -> None:
        with demo_repo(**{"constraints/gamma.txt": BETA_LOCK}) as root:
            errors = check_constraints.check_repo(root)
        self.assertTrue(any("gamma" in e for e in errors), errors)

    def test_cli_exit_codes(self) -> None:
        with demo_repo() as root:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(check_constraints.main(["--root", str(root)]), 0)
        with demo_repo(**{"constraints/beta.txt": "baz==2.0\n"}) as root:
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                self.assertEqual(check_constraints.main(["--root", str(root)]), 1)
            self.assertIn("baz", out.getvalue())

    def test_real_repo_constraints_are_hash_pinned(self) -> None:
        self.assertEqual(check_constraints.check_repo(REPO_ROOT), [])


class PyprojectTests(unittest.TestCase):
    def test_fallback_parser_matches_tomllib_on_real_pyproject(self) -> None:
        text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        fallback = check_constraints.parse_pyproject_minimal(text)
        try:
            import tomllib
        except ImportError:  # Python 3.10: nothing to compare against
            self.assertEqual(fallback["name"], "ignite-sentinel")
            return
        data = tomllib.loads(text)["project"]
        self.assertEqual(fallback["name"], data["name"])
        self.assertEqual(fallback["version"], data["version"])
        self.assertEqual(fallback["optional-dependencies"], data["optional-dependencies"])

    def test_fallback_parser_on_demo(self) -> None:
        meta = check_constraints.parse_pyproject_minimal(PYPROJECT)
        self.assertEqual(meta["name"], "demo-pkg")
        self.assertEqual(meta["version"], "1.2.3")
        self.assertEqual(meta["optional-dependencies"], {"alpha": ["Foo_Bar>=1"], "beta": ["baz"]})


class SbomTests(unittest.TestCase):
    def test_cyclonedx_document_from_demo_repo(self) -> None:
        with demo_repo() as root:
            doc = sbom.build_sbom(root)
        self.assertEqual(doc["bomFormat"], "CycloneDX")
        self.assertEqual(doc["specVersion"], "1.6")
        self.assertRegex(doc["serialNumber"], r"^urn:uuid:[0-9a-f-]{36}$")
        root_component = doc["metadata"]["component"]
        self.assertEqual(root_component["name"], "demo-pkg")
        self.assertEqual(root_component["version"], "1.2.3")
        self.assertEqual(root_component["purl"], "pkg:pypi/demo-pkg@1.2.3")
        by_ref = {c["bom-ref"]: c for c in doc["components"]}
        self.assertEqual(sorted(by_ref), ["pkg:pypi/baz@2.0", "pkg:pypi/colorama@0.4.6", "pkg:pypi/foo-bar@1.4.0"])
        foo = by_ref["pkg:pypi/foo-bar@1.4.0"]
        self.assertEqual(foo["type"], "library")
        self.assertEqual(foo["hashes"], [{"alg": "SHA-256", "content": HASH_A}, {"alg": "SHA-256", "content": HASH_B}])
        props = {(p["name"], p["value"]) for p in foo["properties"]}
        self.assertIn(("ignite-sentinel:extra", "alpha"), props)
        colorama_props = {(p["name"], p["value"]) for p in by_ref["pkg:pypi/colorama@0.4.6"]["properties"]}
        self.assertIn(("ignite-sentinel:marker", "sys_platform == 'win32'"), colorama_props)
        deps = {d["ref"]: d.get("dependsOn", []) for d in doc["dependencies"]}
        self.assertEqual(deps[root_component["bom-ref"]], ["pkg:pypi/baz@2.0", "pkg:pypi/foo-bar@1.4.0"])

    def test_component_shared_by_extras_is_listed_once(self) -> None:
        with demo_repo(**{"constraints/beta.txt": BETA_LOCK + f"foo-bar==1.4.0 --hash=sha256:{HASH_A}\n"}) as root:
            doc = sbom.build_sbom(root)
        foo = [c for c in doc["components"] if c["name"] == "foo-bar"]
        self.assertEqual(len(foo), 1)
        extras = sorted(p["value"] for p in foo[0]["properties"] if p["name"] == "ignite-sentinel:extra")
        self.assertEqual(extras, ["alpha", "beta"])

    def test_deterministic_and_timestamp_from_source_date_epoch(self) -> None:
        with demo_repo() as root:
            first = sbom.build_sbom(root)
            second = sbom.build_sbom(root)
            stamped = sbom.build_sbom(root, source_date_epoch=0)
        self.assertEqual(first, second)
        self.assertNotIn("timestamp", first["metadata"])
        self.assertEqual(stamped["metadata"]["timestamp"], "1970-01-01T00:00:00Z")

    def test_cli_writes_json(self) -> None:
        with demo_repo() as root:
            out = root / "dist" / "sbom.cdx.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(sbom.main(["--root", str(root), "-o", str(out)]), 0)
            doc = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(doc["metadata"]["component"]["name"], "demo-pkg")

    def test_real_repo_sbom(self) -> None:
        doc = sbom.build_sbom(REPO_ROOT)
        self.assertEqual(doc["metadata"]["component"]["name"], "ignite-sentinel")
        names = {c["name"] for c in doc["components"]}
        self.assertTrue({"lancedb", "mcp", "model2vec", "sentence-transformers"} <= names, names)
        for component in doc["components"]:
            self.assertTrue(component["hashes"], component["name"])


WORKFLOWS = REPO_ROOT / ".github" / "workflows"
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)


class GithubConfigTests(unittest.TestCase):
    def test_every_action_is_pinned_by_commit_sha(self) -> None:
        offenders = []
        for workflow in sorted(WORKFLOWS.glob("*.yml")):
            for ref in USES.findall(workflow.read_text(encoding="utf-8")):
                if ref.startswith("./"):
                    continue
                if not re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", ref):
                    offenders.append(f"{workflow.name}: {ref}")
        self.assertEqual(offenders, [])

    def test_every_workflow_declares_top_level_read_permissions(self) -> None:
        for workflow in sorted(WORKFLOWS.glob("*.yml")):
            text = workflow.read_text(encoding="utf-8")
            self.assertRegex(text, r"(?m)^permissions:\n\s+contents: read$", workflow.name)

    def test_security_workflow_covers_the_imp289_checks(self) -> None:
        text = (WORKFLOWS / "security.yml").read_text(encoding="utf-8")
        for needle in ("dependency-review-action", "codeql-action/init", "codeql-action/analyze",
                       "pip-audit", "--require-hashes", "tools/check_constraints.py", "security-events: write"):
            self.assertIn(needle, text)

    def test_release_workflow_attests_the_wheel_and_sbom(self) -> None:
        text = (WORKFLOWS / "release-attest.yml").read_text(encoding="utf-8")
        self.assertIn("tags:", text)
        self.assertIn("'v*'", text)
        self.assertIn("attest-build-provenance", text)
        self.assertIn("tools/sbom.py", text)
        self.assertIn("id-token: write", text)
        self.assertIn("attestations: write", text)
        self.assertIn("IMP-279", text)  # hook point for the plugin zip / validation

    def test_dependabot_tracks_github_actions(self) -> None:
        text = (REPO_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        self.assertIn("version: 2", text)
        self.assertIn('package-ecosystem: "github-actions"', text)


if __name__ == "__main__":
    unittest.main()
