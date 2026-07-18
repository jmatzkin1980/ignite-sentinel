from __future__ import annotations

import argparse
import shutil
import tempfile
import zipapp
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "sentinel"
DEFAULT_TARGET = ROOT / "dist" / "sentinel.pyz"


def build_pyz(target: Path | str = DEFAULT_TARGET) -> Path:
    target_path = Path(target).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sentinel_pyz_build_") as temp_dir:
        staging = Path(temp_dir) / "app"
        shutil.copytree(PACKAGE_DIR, staging / "sentinel", ignore=_ignore_build_artifacts)
        (staging / "__main__.py").write_text(
            "from sentinel.cli import main\n\nraise SystemExit(main())\n",
            encoding="utf-8",
        )
        license_file = ROOT / "LICENSE"
        if license_file.exists():
            shutil.copy2(license_file, staging / "LICENSE")
        zipapp.create_archive(
            staging,
            target=target_path,
            interpreter="/usr/bin/env python3",
            compressed=True,
        )
    return target_path


def _ignore_build_artifacts(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name == "__pycache__" or name.endswith(".pyc") or name.endswith(".pyo")
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Ignite Sentinel zipapp.")
    parser.add_argument("--target", default=str(DEFAULT_TARGET), help="Output .pyz path. Defaults to dist/sentinel.pyz.")
    args = parser.parse_args(argv)
    target = build_pyz(Path(args.target))
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
