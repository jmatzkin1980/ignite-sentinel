"""IMP-282 (H14): one version, release checks and the plugin archive.

- ``tools/release.py check``: ``pyproject.toml``, ``sentinel.__version__`` and every
  ``plugin.json`` carry the same version; a ``vX.Y.Z`` tag must equal that version
  (a tag without a bump fails) and have a dated CHANGELOG section; on ``main`` the
  version must be tagged (a bump without a tag fails).
- ``tools/release.py notes``: the CHANGELOG section of a version, used as release notes.
- ``tools/release.py zip``: one deterministic ``.zip`` per plugin plus ``SHA256SUMS``,
  the input of an ``archive`` plugin source (``url`` + ``sha256``).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))
import release  # noqa: E402

WORKFLOWS = REPO_ROOT / ".github" / "workflows"

CHANGELOG = """# Changelog

## [Unreleased]

### Added
- Something not released yet.

## [1.0.0] — 2026-01-02

### Added
- First stable cut.

## [0.9.0] — 2025-12-01

- Older.
"""


def _make_root(base: Path, *, pyproject: str = "1.0.0", package: str = "1.0.0", plugin: str = "1.0.0") -> Path:
    (base / "sentinel").mkdir(parents=True)
    (base / "pyproject.toml").write_text(
        f'[build-system]\nrequires = ["setuptools>=68"]\n\n[project]\nname = "demo"\nversion = "{pyproject}"\n',
        encoding="utf-8",
    )
    (base / "sentinel" / "__init__.py").write_text(f'"""Demo."""\n\n__version__ = "{package}"\n', encoding="utf-8")
    for name in ("alpha", "alpha-mcp"):
        manifest = base / "plugins" / name / ".claude-plugin" / "plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"name": name, "version": plugin}), encoding="utf-8")
        (base / "plugins" / name / "launcher.py").write_bytes(b"print('hi')\n")
        cache = base / "plugins" / name / "lib" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "x.cpython-313.pyc").write_bytes(b"\x00junk")
    (base / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    return base


class _TmpRoot(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="imp282-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)


class SingleVersionTests(_TmpRoot):
    def test_the_repository_has_one_version(self) -> None:
        versions = release.version_sources(REPO_ROOT)
        self.assertIn("pyproject.toml", versions)
        self.assertIn("sentinel/__init__.py", versions)
        self.assertIn("plugins/ignite-sentinel/.claude-plugin/plugin.json", versions)
        self.assertIn("plugins/ignite-sentinel-mcp/.claude-plugin/plugin.json", versions)
        self.assertEqual(len(set(versions.values())), 1, versions)

    def test_the_package_reports_the_project_version(self) -> None:
        import sentinel

        self.assertEqual(sentinel.__version__, release.version_sources(REPO_ROOT)["pyproject.toml"])

    def test_a_package_version_that_disagrees_fails(self) -> None:
        root = _make_root(self.tmp, package="0.1.0")
        issues = release.check(root)
        self.assertTrue(any("sentinel/__init__.py" in issue and "0.1.0" in issue for issue in issues), issues)

    def test_a_stale_plugin_manifest_fails(self) -> None:
        root = _make_root(self.tmp, plugin="0.9.0")
        issues = release.check(root)
        self.assertTrue(any("plugin.json" in issue for issue in issues), issues)

    def test_agreeing_sources_pass(self) -> None:
        self.assertEqual(release.check(_make_root(self.tmp)), [])


class TagTests(_TmpRoot):
    def test_tag_matching_the_version_passes(self) -> None:
        self.assertEqual(release.check(_make_root(self.tmp), tag="v1.0.0"), [])

    def test_a_tag_without_a_bump_fails(self) -> None:
        issues = release.check(_make_root(self.tmp), tag="v1.0.1")
        self.assertTrue(any("tag without a bump" in issue for issue in issues), issues)

    def test_a_tag_that_is_not_semver_fails(self) -> None:
        issues = release.check(_make_root(self.tmp), tag="release-1")
        self.assertTrue(any("vX.Y.Z" in issue for issue in issues), issues)

    def test_a_tag_needs_a_dated_changelog_section(self) -> None:
        root = _make_root(self.tmp, pyproject="1.1.0", package="1.1.0", plugin="1.1.0")
        issues = release.check(root, tag="v1.1.0")
        self.assertTrue(any("CHANGELOG" in issue for issue in issues), issues)


class BumpWithoutTagTests(_TmpRoot):
    def test_an_untagged_version_fails_when_a_tag_is_required(self) -> None:
        issues = release.check(_make_root(self.tmp), tags=["v0.9.0"], require_tagged=True)
        self.assertTrue(any("bump without a tag" in issue for issue in issues), issues)

    def test_a_tagged_version_passes(self) -> None:
        self.assertEqual(release.check(_make_root(self.tmp), tags=["v0.9.0", "v1.0.0"], require_tagged=True), [])

    def test_untagged_is_fine_when_not_required(self) -> None:
        self.assertEqual(release.check(_make_root(self.tmp), tags=[]), [])


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *args],
        cwd=root, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


class ReleasePlanTests(_TmpRoot):
    """On main the tag is created by CI on the commit that introduced the version."""

    def setUp(self) -> None:
        super().setUp()
        self.root = _make_root(self.tmp / "repo")
        _git(self.root, "init", "-q", "-b", "main")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "1.0.0")
        self.bump = _git(self.root, "rev-parse", "HEAD")

    def _commit_other_change(self) -> str:
        (self.root / "notes.txt").write_text("x", encoding="utf-8")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "other")
        return _git(self.root, "rev-parse", "HEAD")

    def test_the_bump_commit_itself_is_tagged_and_published(self) -> None:
        plan = release.release_plan(self.root)
        self.assertEqual(plan["issues"], [])
        self.assertEqual((plan["tag"], plan["commit"], plan["create_tag"], plan["publish"]), ("v1.0.0", self.bump, True, True))

    def test_a_later_commit_tags_the_bump_commit_without_publishing(self) -> None:
        self._commit_other_change()
        plan = release.release_plan(self.root)
        self.assertEqual((plan["commit"], plan["create_tag"], plan["publish"]), (self.bump, True, False))

    def test_an_existing_tag_needs_nothing(self) -> None:
        _git(self.root, "tag", "v1.0.0")
        plan = release.release_plan(self.root)
        self.assertEqual((plan["create_tag"], plan["publish"], plan["issues"]), (False, False, []))

    def test_a_bump_without_a_dated_changelog_section_fails(self) -> None:
        for path in ("pyproject.toml", "sentinel/__init__.py"):
            target = self.root / path
            target.write_text(target.read_text(encoding="utf-8").replace("1.0.0", "1.1.0"), encoding="utf-8")
        for manifest in (self.root / "plugins").glob("*/.claude-plugin/plugin.json"):
            manifest.write_text(manifest.read_text(encoding="utf-8").replace("1.0.0", "1.1.0"), encoding="utf-8")
        _git(self.root, "commit", "-q", "-am", "bump")
        plan = release.release_plan(self.root)
        self.assertFalse(plan["create_tag"])
        self.assertTrue(any("CHANGELOG" in issue for issue in plan["issues"]), plan["issues"])

    def test_the_plan_is_printed_as_github_outputs(self) -> None:
        lines = release.format_outputs(release.release_plan(self.root))
        self.assertIn("tag=v1.0.0", lines)
        self.assertIn(f"commit={self.bump}", lines)
        self.assertIn("create_tag=true", lines)
        self.assertIn("publish=true", lines)


class NotesTests(_TmpRoot):
    def test_notes_are_the_version_section_only(self) -> None:
        notes = release.changelog_section(_make_root(self.tmp), "1.0.0")
        self.assertIsNotNone(notes)
        self.assertIn("First stable cut.", notes)
        self.assertNotIn("Older.", notes)
        self.assertNotIn("not released yet", notes)
        self.assertNotIn("## [1.0.0]", notes)

    def test_unreleased_is_never_a_release_section(self) -> None:
        self.assertIsNone(release.changelog_section(_make_root(self.tmp), "Unreleased"))

    def test_the_real_changelog_has_the_current_version(self) -> None:
        version = release.version_sources(REPO_ROOT)["pyproject.toml"]
        self.assertTrue(release.changelog_section(REPO_ROOT, version))


class ArchiveTests(_TmpRoot):
    def setUp(self) -> None:
        super().setUp()
        self.root = _make_root(self.tmp / "repo")

    def _build(self, out: str) -> list[Path]:
        return release.build_archives(self.root, self.tmp / out, epoch=1_767_225_600)

    def test_one_zip_per_plugin_named_with_the_version_plus_sums(self) -> None:
        names = sorted(path.name for path in self._build("dist"))
        self.assertEqual(names, ["SHA256SUMS", "alpha-mcp-v1.0.0.zip", "alpha-v1.0.0.zip"])

    def test_the_plugin_sits_one_folder_down_without_caches(self) -> None:
        self._build("dist")
        with zipfile.ZipFile(self.tmp / "dist" / "alpha-v1.0.0.zip") as archive:
            names = archive.namelist()
        self.assertIn("alpha/.claude-plugin/plugin.json", names)
        self.assertIn("alpha/launcher.py", names)
        self.assertFalse([name for name in names if "__pycache__" in name or name.endswith(".pyc")], names)
        self.assertTrue(all(name.startswith("alpha/") for name in names), names)

    def test_archives_are_reproducible(self) -> None:
        self._build("one")
        self._build("two")
        for name in ("alpha-v1.0.0.zip", "alpha-mcp-v1.0.0.zip", "SHA256SUMS"):
            with self.subTest(name=name):
                self.assertEqual((self.tmp / "one" / name).read_bytes(), (self.tmp / "two" / name).read_bytes())

    def test_sums_match_the_archives(self) -> None:
        self._build("dist")
        sums = (self.tmp / "dist" / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(sums), 2)
        for line in sums:
            digest, name = line.split("  ")
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            self.assertEqual(hashlib.sha256((self.tmp / "dist" / name).read_bytes()).hexdigest(), digest)

    def test_line_endings_do_not_change_the_archive(self) -> None:
        self._build("lf")
        launcher = self.root / "plugins" / "alpha" / "launcher.py"
        launcher.write_bytes(launcher.read_bytes().replace(b"\n", b"\r\n"))
        self._build("crlf")
        self.assertEqual(
            (self.tmp / "lf" / "alpha-v1.0.0.zip").read_bytes(),
            (self.tmp / "crlf" / "alpha-v1.0.0.zip").read_bytes(),
        )


class WorkflowTests(unittest.TestCase):
    def test_main_tags_every_bump_and_publishes_it(self) -> None:
        text = (WORKFLOWS / "release-check.yml").read_text(encoding="utf-8")
        self.assertIn("tools/release.py check", text)
        self.assertIn("tools/release.py plan --github-output", text)
        self.assertIn("refs/heads/main", text)
        self.assertIn("fetch-depth: 0", text)
        self.assertIn('git push origin "refs/tags/$TAG"', text)
        self.assertIn("uses: ./.github/workflows/release-attest.yml", text)
        self.assertIn("needs.tag.outputs.publish == 'true'", text)

    def test_the_tag_workflow_checks_publishes_and_attests_the_zip(self) -> None:
        text = (WORKFLOWS / "release-attest.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_call:", text)
        self.assertIn('tools/release.py check --tag "$TAG"', text)
        self.assertIn("tools/release.py zip", text)
        self.assertIn("tools/release.py notes", text)
        self.assertIn("gh release create", text)
        self.assertIn("dist/*.zip", text)
        self.assertIn("SHA256SUMS", text)
        self.assertIn("plugin validate --strict", text)
        self.assertIn("refs/heads/stable", text)


if __name__ == "__main__":
    unittest.main()
