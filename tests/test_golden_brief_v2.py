"""H16a close (26z): golden snapshots of the brief v2 in English and Spanish.

The same populated lifecycle as `test_golden_artifacts` (EARS answers that close
the acceptance gap), then `/brief --profile UI --genesis greenfield` on the default
flow (IMP-26w: a new project compiles the brief v2). The brief and its compile report are pinned. The v1 goldens stay
untouched in `fixtures/golden/<lang>/`.

Regenerate intentionally with `SENTINEL_UPDATE_GOLDEN=1` and review the git diff.
"""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel.memory import ContextBroker

sys.path.insert(0, str(Path(__file__).resolve().parent))
from golden_normalize import normalize  # noqa: E402
from test_golden_artifacts import SCENARIOS  # noqa: E402

GOLDEN_DIR = Path(__file__).resolve().parent / "fixtures" / "golden" / "brief_v2"
UPDATE = os.environ.get("SENTINEL_UPDATE_GOLDEN") == "1"


def _generate(language: str) -> dict[str, str]:
    from sentinel.cli import main

    scenario = SCENARIOS[language]
    pid = scenario["project_id"]
    old_cwd = Path.cwd()
    tmp = Path(tempfile.mkdtemp())
    os.chdir(tmp)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            raw = tmp / "raw.md"
            raw.write_text(scenario["raw"], encoding="utf-8")
            assert main(["init", pid]) == 0
            assert main(["ingest", pid, "--source", str(raw)]) == 0
            for index, statement in enumerate(scenario["ears"], start=1):
                answer = tmp / f"answer-{index}.md"
                answer.write_text(scenario["answer"].format(s=statement, i=index), encoding="utf-8")
                assert main(["resolve-gaps", pid, "--source", str(answer)]) == 0
            assert main(["brief", pid, "--profile", "UI", "--genesis", "greenfield"]) == 0  # IMP-26w: v2 is the default
        base = tmp / "workspaces" / pid / "02_requirements"
        report = json.loads((base / "brief_compile_report.json").read_text(encoding="utf-8"))
        return {
            "project-brief.md": normalize((base / "project-brief.md").read_text(encoding="utf-8"), pid),
            "brief_compile_report.json": normalize(json.dumps(report, ensure_ascii=False, indent=2) + "\n", pid),
        }
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmp, ignore_errors=True)


class GoldenBriefV2Tests(unittest.TestCase):
    def _check(self, language: str) -> None:
        with patch.object(ContextBroker, "_connect_lancedb", lambda self: None):
            produced = _generate(language)
        for name, text in produced.items():
            golden = GOLDEN_DIR / language / name
            if UPDATE:
                golden.parent.mkdir(parents=True, exist_ok=True)
                golden.write_text(text, encoding="utf-8", newline="\n")
                continue
            self.assertTrue(golden.exists(), f"missing golden {golden}; create it with SENTINEL_UPDATE_GOLDEN=1")
            self.assertEqual(text, golden.read_text(encoding="utf-8"),
                             f"brief_v2/{language}/{name} drifted from its golden; regenerate with "
                             "SENTINEL_UPDATE_GOLDEN=1 and review the git diff.")

    def test_english(self):
        self._check("en")

    def test_spanish(self):
        self._check("es")


if __name__ == "__main__":
    unittest.main()
