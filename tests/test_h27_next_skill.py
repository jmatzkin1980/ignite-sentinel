"""IMP-408 (H27 inc 2): every next step names the skill that carries it, from the command registry."""
from __future__ import annotations

import contextlib
import io
import json
import re
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, run_ok  # noqa: E402

from sentinel.cli import main  # noqa: E402
from sentinel.commands import BY_NAME, REGISTRY, skill_for_command, skill_for_next_text  # noqa: E402
from sentinel.mcp import run_cli  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / ".codex" / "skills"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROUTING_LINE = re.compile(r"^- ((?:`/[a-z-]+[^`]*`(?:, | and )?)+)[^:]*: use `(sentinel-[a-z-]+)`", re.M)


def check_skill(test: unittest.TestCase, value: str, owner: str) -> None:
    name, _, section = value.partition(" §")
    path = SKILLS / name / "SKILL.md"
    test.assertTrue(path.is_file(), f"{owner}: no skill {name}")
    if section:
        heading = re.compile(rf"^#{{2,3}} .*{re.escape(section)}", re.M)
        test.assertRegex(path.read_text(encoding="utf-8-sig"), heading, f"{owner}: {name} has no section {section}")


class RegistrySkills(unittest.TestCase):
    def test_every_command_names_an_existing_skill(self):
        for command in REGISTRY:
            self.assertTrue(command.skill, command.name)
            check_skill(self, command.skill, command.name)
            for _, variant in command.skill_variants:
                check_skill(self, variant, command.name)

    def test_router_routing_agrees_with_the_registry(self):
        text = (SKILLS / "sentinel-command-router" / "SKILL.md").read_text(encoding="utf-8-sig")
        routing = text.split("## Routing", 1)[1].split("\n## ", 1)[0]
        pairs: dict[str, set[str]] = {}
        for found in ROUTING_LINE.finditer(routing):
            for verb in re.findall(r"`/([a-z-]+)", found.group(1)):
                pairs.setdefault(verb, set()).add(found.group(2))
        self.assertTrue(pairs)
        for verb, routed in pairs.items():
            command = BY_NAME[verb]
            ours = {command.skill.split(" §")[0], *(v.split(" §")[0] for _, v in command.skill_variants)}
            self.assertTrue(ours & routed, f"/{verb}: registry {sorted(ours)} vs router {sorted(routed)}")

    def test_skill_for_command(self):
        self.assertEqual(skill_for_command("/export P --artifact brief --change CHG-001 --final"), "sentinel-project-brief")
        self.assertEqual(skill_for_command("/export P --artifact gaps --format interview"), "sentinel-discovery")
        self.assertEqual(skill_for_command("/prototype P --manual --source M.json"), "sentinel-prototype-manual")
        self.assertEqual(skill_for_command("/cross P --change CHG-001 --kind diseno --claims PATH"),
                         "sentinel-discovery §Cross-reads of a change")
        self.assertEqual(skill_for_command(""), "")
        self.assertEqual(skill_for_next_text("Wait for /ingest to finish"), "")
        self.assertEqual(skill_for_next_text("Run /init NOPE first."), "sentinel-discovery")


class NextSkill(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_extraction" / "pedido_ids.md", root / "pedido_ids.md")
        shutil.copy(FIXTURES / "incomplete_requirement.md", root / "incomplete_requirement.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", "PRJ"])
        run_ok(["init", "CHGP"])

    def test_project_next_names_the_skill(self):
        first = json.loads(run_ok(["next", "PRJ"]))
        self.assertEqual(first["key"], "ingest")
        self.assertEqual(first["skill"], "sentinel-discovery")
        run_ok(["ingest", "PRJ", "--source", "incomplete_requirement.md"])
        step = json.loads(run_ok(["next", "PRJ"]))
        self.assertTrue(step["skill"])
        self.assertEqual(step["skill"], skill_for_command(step["command"]))
        status = json.loads(run_ok(["status", "PRJ"]))
        self.assertEqual(status["next_action"]["skill"], step["skill"])

    def test_change_next_names_the_skill(self):
        ingested = json.loads(run_ok(["ingest", "CHGP", "--source", "pedido_ids.md", "--change"]))
        self.assertEqual(ingested["next_step"]["skill"], "sentinel-gap-response")
        change = ingested["change_id"]
        resolved = json.loads(run_ok(["resolve-gaps", "CHGP", "--source", "scope.md", "--change", change]))
        self.assertEqual(resolved["next_step"]["key"], "baseline")
        self.assertEqual(resolved["next_step"]["skill"], "sentinel-sync")
        again = json.loads(run_ok(["next", "CHGP", "--change", change]))
        self.assertEqual((again["key"], again["skill"]), ("baseline", "sentinel-sync"))

    def test_error_line_names_the_skill(self):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            main(["status", "NOPE"])
        self.assertIn("next step: Run /init NOPE first. (skill: sentinel-discovery)", err.getvalue())
        result = run_cli(["status", "NOPE"])
        self.assertEqual(result["next_step"], "Run /init NOPE first.")
        self.assertEqual(result["skill"], "sentinel-discovery")


if __name__ == "__main__":
    unittest.main()
