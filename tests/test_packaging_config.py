"""IMP-242: static guard that keeps the wheel complete.

A non-editable install only ships what ``pyproject.toml`` declares. These
tests read the config as text (no setuptools, no tomllib: neither is
guaranteed on Python 3.10 inside ``.venv``) and check it against the real
``sentinel/`` tree, so a new subpackage or data folder cannot silently drop
out of the wheel again.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "sentinel"
PYPROJECT = ROOT / "pyproject.toml"

IGNORED_DIRS = {"__pycache__"}
# Documentation next to data, never read at runtime.
IGNORED_DATA_FILES = {"README.md"}


def _subdirs(base: Path = PACKAGE) -> list[Path]:
    found: list[Path] = []
    for path in sorted(base.rglob("*")):
        if not path.is_dir():
            continue
        relative = path.relative_to(base)
        if any(part in IGNORED_DIRS for part in relative.parts):
            continue
        found.append(path)
    return found


def _package_dirs(base: Path = PACKAGE) -> set[str]:
    """Folders under ``sentinel/`` that contain ``.py`` files."""
    return {
        path.relative_to(base).as_posix()
        for path in _subdirs(base)
        if any(child.suffix == ".py" for child in path.iterdir() if child.is_file())
    }


def _data_dirs(base: Path = PACKAGE) -> dict[str, set[str]]:
    """Folder -> file extensions present, for folders without ``.py`` files."""
    code_dirs = _package_dirs(base)
    result: dict[str, set[str]] = {}
    for path in _subdirs(base):
        name = path.relative_to(base).as_posix()
        if name in code_dirs:
            continue
        extensions = {
            child.suffix
            for child in path.iterdir()
            if child.is_file() and child.name not in IGNORED_DATA_FILES and child.suffix
        }
        if extensions:
            result[name] = extensions
    return result


def _package_data_globs(text: str) -> list[str]:
    """Globs of ``sentinel = [...]`` inside ``[tool.setuptools.package-data]``."""
    section = re.search(
        r"^\[tool\.setuptools\.package-data\]\s*$(.*?)(?=^\[|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if section is None:
        return []
    entry = re.search(r"^sentinel\s*=\s*\[(.*?)\]", section.group(1), flags=re.MULTILINE | re.DOTALL)
    if entry is None:
        return []
    return re.findall(r"\"([^\"]+)\"", entry.group(1))


class PackagingConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pyproject = PYPROJECT.read_text(encoding="utf-8")

    def test_uses_package_discovery(self) -> None:
        self.assertIn("[tool.setuptools.packages.find]", self.pyproject)
        self.assertIn('include = ["sentinel*"]', self.pyproject)
        self.assertNotIn('packages = ["sentinel"]', self.pyproject)

    def test_every_code_dir_is_a_regular_package(self) -> None:
        missing = sorted(name for name in _package_dirs() if not (PACKAGE / name / "__init__.py").is_file())
        self.assertEqual([], missing, f"code folders without __init__.py (find would skip them): {missing}")

    def test_every_data_dir_and_extension_has_a_glob(self) -> None:
        globs = set(_package_data_globs(self.pyproject))
        self.assertTrue(globs, "no sentinel globs found in [tool.setuptools.package-data]")
        missing = sorted(
            f"{name}/*{ext}"
            for name, extensions in _data_dirs().items()
            for ext in extensions
            if f"{name}/*{ext}" not in globs
        )
        self.assertEqual([], missing, f"data files that would not ship in the wheel: {missing}")

    def test_pycache_is_ignored(self) -> None:
        self.assertNotIn("__pycache__", _package_dirs())
        self.assertNotIn("__pycache__", _data_dirs())


class PackagingGuardHelperTests(unittest.TestCase):
    """The helpers catch the failure modes on a synthetic tree."""

    def setUp(self) -> None:
        import tempfile

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)

    def _write(self, relative: str, content: str = "") -> None:
        path = self.base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_code_dir_without_init_is_listed(self) -> None:
        self._write("newpkg/module.py")
        self._write("okpkg/__init__.py")

        self.assertEqual({"newpkg", "okpkg"}, _package_dirs(self.base))
        self.assertFalse((self.base / "newpkg" / "__init__.py").exists())

    def test_data_dir_reports_every_extension(self) -> None:
        self._write("themes/neutral.json", "{}")
        self._write("themes/base.css", "")
        self._write("themes/README.md", "docs")

        self.assertEqual({"themes": {".json", ".css"}}, _data_dirs(self.base))

    def test_pycache_and_compiled_files_are_not_dirs_of_interest(self) -> None:
        self._write("__pycache__/cli.cpython-312.pyc")
        self._write("core/__init__.py")
        self._write("core/__pycache__/io.cpython-312.pyc")

        self.assertEqual({"core"}, _package_dirs(self.base))
        self.assertEqual({}, _data_dirs(self.base))

    def test_globs_are_read_from_the_package_data_section_only(self) -> None:
        text = (
            '[tool.setuptools.packages.find]\ninclude = ["sentinel*"]\n\n'
            '[tool.setuptools.package-data]\nsentinel = [\n  "schemas/*.json",\n  "themes/*.css"\n]\n\n'
            '[tool.other]\nsentinel = ["nope/*.json"]\n'
        )

        self.assertEqual(["schemas/*.json", "themes/*.css"], _package_data_globs(text))


if __name__ == "__main__":
    unittest.main()
