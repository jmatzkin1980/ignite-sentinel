"""IMP-435 (H27 inc 9a, task 2): on the project path /next and the refusals name the real step, and /sync behaves (A-03, A-09,
A-11, A-13, A-33, A-36, A-10, A-01)."""
from __future__ import annotations

import contextlib
import io
import json
import re
import shlex
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
from sentinel.cli import build_parser, main  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.workspace import read_json, update_state, workspace_path  # noqa: E402

FX = Path(__file__).resolve().parent / "fixtures" / "inc9a"
NOTICE = "Prose is stored and indexed, not interpreted"


def run_all(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def next_step_line(err: str) -> str:
    found = re.search(r"^next step: (.*?)(?: \(skill: [^)]*\))?$", err, re.M)
    return found.group(1) if found else ""


def commands_in(step: str) -> list[str]:
    """The commands a next step names ("Run /a X, then /b Y."), each of which must parse with the real parser."""
    pieces = [piece.strip() for piece in re.split(r",? then |,? y después |; ", step.strip())]
    found = []
    for piece in pieces:
        piece = re.sub(r"^(?:Run|Corré) ", "", piece).rstrip(".")
        found.append(piece)
    return found


def assert_runnable(case: unittest.TestCase, step: str) -> None:
    case.assertTrue(step, "no next step")
    for command in commands_in(step):
        case.assertTrue(command.startswith("/"), step)
        case.assertNotIn("|", command, step)
        case.assertNotIn("PROJECT_ID", command, step)
        words = shlex.split(command[1:])
        if len(words) == 1:  # a bare command in a chain ("..., then /backlog") is the same project's
            words.append("ALTA")
        build_parser().parse_args(words)


def start(project: str, pedido: Path | str, *steps: list[str]) -> None:
    run_ok(["init", project])
    run_ok(["ingest", project, "--source", str(pedido)])
    for argv in steps:
        run_ok(argv)


ANSWERS = ["resolve-gaps", "ALTA", "--source", str(FX / "respuestas_alta.md")]


class Initialized(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        run_ok(["init", "ALTA"])

    def test_new_project_status(self):
        """A-36: a new project reports maturity 0.0 and the real project id in its next step."""
        status = json.loads(run_ok(["status", "ALTA"]))
        self.assertEqual(status["maturity_score"], 0.0)
        self.assertEqual(status["next_step"], "Run /ingest ALTA --source PATH.")
        assert_runnable(self, status["next_step"])


class Ingested(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        start("ALTA", FX / "pedido_alta.md")

    def test_specs_blocked_names_each_gap(self):
        """A-13.1: /specs on a blocked project says which gap needs which command."""
        code, _out, err = run_all(["specs", "ALTA"])
        self.assertEqual(code, 4, err)
        step = next_step_line(err)
        self.assertIn("/brief ALTA --profile", step)
        self.assertIn("/resolve-gaps", step)
        self.assertIn("GAP-BRIEF-PROFILE", err)
        self.assertIn("GAP-USERS", err)
        assert_runnable(self, step)

    def test_every_new_refusal_has_runnable_next(self):
        """RF 4: the next step of each refusal names commands the real parser accepts, with no `|` and no PROJECT_ID."""
        for command in (["specs", "ALTA"], ["backlog", "ALTA"]):
            code, _out, err = run_all(command)
            self.assertEqual(code, 4, err)
            assert_runnable(self, next_step_line(err))


class SpanishProject(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        run_ok(["init", "ALTA"])
        update_state("ALTA", project_language="es")
        run_ok(["ingest", "ALTA", "--source", str(FX / "pedido_alta.md")])

    def test_project_messages_follow_the_language(self):
        """M-2: the project-path refusals and warnings of a Spanish workspace are in Spanish."""
        forget_read_snapshots()
        code, _out, err = run_all(["validate", "ALTA", "--override", "nofile.json"])
        self.assertEqual(code, 3, err)
        self.assertIn("no se encontró el archivo de --override", err)
        code, _out, err = run_all(["specs", "ALTA"])
        self.assertEqual(code, 4, err)
        self.assertIn("No se puede generar specs", err)
        self.assertIn("Corré", err)
        self.assertNotIn("Cannot generate", err)
        code, _out, err = run_all(["brief", "ALTA", "--profile", "UI"])
        self.assertEqual(code, 0, err)
        self.assertIn("los ajustes del brief no están confirmados", err)


class Answered(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        start("ALTA", FX / "pedido_alta.md", ANSWERS)

    def test_backlog_gate_fixes(self):
        """A-13.2/3: only the brief settings block, and no specs exist: /resolve-gaps is not the fix, /specs comes before /backlog."""
        run_ok(["brief", "ALTA"])
        forget_read_snapshots()
        code, _out, err = run_all(["backlog", "ALTA"])
        self.assertEqual(code, 4, err)
        self.assertNotIn("resolve-gaps", err)
        self.assertIn("/brief ALTA --profile", err)
        step = next_step_line(err)
        self.assertIn("then /specs, then /backlog", step)
        assert_runnable(self, step)

    def test_brief_incomplete_settings_warn(self):
        """A-33: a profile without genesis, or a profile that contradicts it, is said on stderr."""
        code, _out, err = run_all(["brief", "ALTA", "--profile", "UI"])
        self.assertEqual(code, 0, err)
        self.assertTrue(err.startswith("sentinel warning:"), err)
        self.assertIn("genesis", err)

    def test_brief_contradictory_settings_warn(self):
        code, _out, err = run_all(["brief", "ALTA", "--profile", "MIG", "--genesis", "greenfield"])
        self.assertEqual(code, 0, err)
        self.assertTrue(err.startswith("sentinel warning:"), err)
        self.assertIn("MIG", err)
        self.assertIn("greenfield", err)


class BriefBeforeAnswers(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        start("ALTA", FX / "pedido_alta.md", ["brief", "ALTA"], ANSWERS)

    def test_backlog_before_any_specs(self):
        """A-13.3: /backlog before any specs exist asks for /specs, which compiles what it needs, not /brief."""
        code, _out, err = run_all(["backlog", "ALTA"])
        self.assertEqual(code, 4, err)
        self.assertIn("Run /specs, then /backlog", err)
        self.assertNotIn("Run /brief, then /backlog", err)
        self.assertNotIn("resolve-gaps", err)
        assert_runnable(self, next_step_line(err))


class ErpRequest(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        pedido = Path("pedido_erp.md")
        pedido.write_text((FX / "pedido_alta.md").read_text(encoding="utf-8")
                          + "\nLa integracion con el ERP queda fuera de esta primera version.\n", encoding="utf-8")
        start("ALTA", pedido, ANSWERS)

    def test_next_and_brief_same_proposal(self):
        """A-09: /next and /brief read the same input, and the gap question carries that proposal (not UI,REG)."""
        nxt = json.loads(run_ok(["next", "ALTA"]))
        self.assertEqual(nxt["key"], "brief_settings")
        proposed = re.search(r"--profile (\S+) --genesis (\S+)", nxt["command"])
        brief = json.loads(run_ok(["brief", "ALTA"]))
        proposal = brief["brief_settings"]["proposal"]
        self.assertEqual(proposed.group(1), ",".join(proposal["profiles"]))
        self.assertEqual(proposed.group(2), proposal["genesis"])
        question = brief["brief_settings"]["gap"]["question"]
        self.assertIn(f"/brief ALTA --profile {proposed.group(1)} --genesis {proposed.group(2)}", question)
        self.assertNotIn("UI,REG", question)
        gaps = (workspace_path("ALTA") / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        self.assertNotIn("PROJECT_ID --profile", gaps)


class Briefed(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        start("ALTA", FX / "pedido_alta.md", ANSWERS, ["brief", "ALTA", "--profile", "UI", "--genesis", "greenfield"])

    def setUp(self):
        super().setUp()
        forget_read_snapshots()
        self.base = workspace_path("ALTA")
        (self.temp / "input").mkdir(exist_ok=True)

    def note(self, name: str) -> str:
        target = self.temp / "input" / name
        shutil.copy(FX / name, target)
        return str(target)

    def health(self) -> dict:
        return json.loads(run_ok(["health", "ALTA"]))

    def test_next_names_specs_after_blocking(self):
        """A-03: no blocking gap, the brief exists and other gaps are open: the step is /specs, not /resolve-gaps and not /brief."""
        nxt = json.loads(run_ok(["next", "ALTA"]))
        self.assertEqual(nxt["key"], "specs")
        self.assertEqual(nxt["command"], "/specs ALTA")
        self.assertNotIn("run /brief", nxt["text"].lower())
        self.assertNotIn("PROJECT_ID", nxt["text"])
        self.assertIn("/resolve-gaps", nxt["text"])  # closing the rest stays the alternative

    def test_feeding_gaps_exist(self):
        """A-11: /brief and /specs only name gaps that are in gaps.md."""
        gaps = (self.base / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        known = set(re.findall(r"GAP-[A-Z0-9-]+", gaps))

        def named(node, found):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "feeding_gaps":
                        found.update(value)
                    elif "warning" in key:
                        found.update(re.findall(r"GAP-[A-Z0-9-]+", json.dumps(value)))
                    else:
                        named(value, found)
            elif isinstance(node, list):
                for item in node:
                    named(item, found)
            return found

        brief = json.loads(run_ok(["brief", "ALTA"]))
        specs = json.loads(run_ok(["specs", "ALTA"]))
        for result in (brief, specs):
            ids = named(result, set())
            self.assertTrue(ids <= known, sorted(ids - known))

    def test_same_file_sync_twice(self):
        """A-10: the same file twice is one change: the second answer says where it is already loaded."""
        source = self.note("minuta_comite.md")
        first = json.loads(run_ok(["sync", "ALTA", "--source", source]))
        copies = sorted(p.name for p in (self.base / "07_changes" / "01_meetings").glob("minuta_comite*.md"))
        last_change = read_json(self.base / "state.json", {}).get("last_change_id")
        forget_read_snapshots()
        second = json.loads(run_ok(["sync", "ALTA", "--source", source]))
        self.assertEqual(second["already_loaded"], {"source_id": first["source_id"], "change_id": first["change_id"]})
        self.assertNotIn("change_id", second)
        self.assertEqual(sorted(p.name for p in (self.base / "07_changes" / "01_meetings").glob("minuta_comite*.md")), copies)
        self.assertFalse((self.base / "07_changes" / "01_meetings" / "minuta_comite-2.md").exists())
        self.assertEqual(read_json(self.base / "state.json", {}).get("last_change_id"), last_change)

    def regenerate(self) -> None:
        for argv in (["brief", "ALTA"], ["specs", "ALTA"], ["backlog", "ALTA"]):
            forget_read_snapshots()
            run_ok(argv)
        forget_read_snapshots()

    def test_regeneration_without_applied_change_keeps_review(self):
        """A-01 (Q1): brief, specs and backlog regenerated from the same answers do not clear the semantic-change review."""
        first = json.loads(run_ok(["sync", "ALTA", "--source", self.note("minuta_comite.md")]))
        change = first["change_id"]
        self.assertEqual(self.health()["verdict"], "DIRTY")
        self.regenerate()
        health = self.health()
        self.assertEqual(health["verdict"], "DIRTY")
        self.assertIn(f"/trace ALTA --reviewed {change}", " ".join(health["findings"]))
        nxt = json.loads(run_ok(["next", "ALTA"]))
        self.assertIn(f"/trace ALTA --reviewed {change}", nxt["text"] + nxt["command"])
        run_ok(["trace", "ALTA", "--reviewed", change])
        self.assertEqual(self.health()["verdict"], "CLEAN")

    def test_regeneration_with_applied_answer_clears_review(self):
        """A-01 (Q1): an answer applied from that change (### GAP-...) and then regenerated leaves the project CLEAN."""
        first = json.loads(run_ok(["sync", "ALTA", "--source", self.note("minuta_con_respuesta.md")]))
        self.assertIn("GAP-BUSINESS-RULES", first["sync_closed_gaps"])
        self.assertEqual(self.health()["verdict"], "DIRTY")
        self.regenerate()
        self.assertEqual(self.health()["verdict"], "CLEAN")

    def test_same_second_regeneration_clears_review(self):
        """I-1: sync then brief, specs and backlog back to back (same wall-clock second) do not leave /backlog refused."""
        first = json.loads(run_ok(["sync", "ALTA", "--source", self.note("minuta_con_respuesta.md")]))
        self.assertIn("GAP-BUSINESS-RULES", first["sync_closed_gaps"])
        marker = read_json(self.base / "state.json", {})["suspicious_trace_links"]
        self.assertIsInstance(marker.get("recorded_at_ns"), int)
        self.regenerate()
        self.assertEqual(self.health()["verdict"], "CLEAN")

    def test_marker_nanosecond_stamp_and_old_markers(self):
        """I-1: the sub-second stamp decides when present; a marker without it keeps the one-second comparison."""
        from datetime import datetime, timezone
        from sentinel.health import _not_regenerated

        target = self.base / "02_requirements" / "project-brief.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x", encoding="utf-8")
        mtime_ns = target.stat().st_mtime_ns
        iso = datetime.fromtimestamp(target.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat()
        base = {"downstream_artifacts": [str(target)], "recorded_at": iso}
        self.assertEqual(_not_regenerated("ALTA", {**base, "recorded_at_ns": mtime_ns - 1}), [])
        self.assertEqual(len(_not_regenerated("ALTA", {**base, "recorded_at_ns": mtime_ns + 1})), 1)
        self.assertEqual(len(_not_regenerated("ALTA", base)), 1)  # old marker: same second counts as pending

    def test_prose_notice_on_stderr(self):
        """A-01: a note that changes nothing says so on stderr, and /next repeats it."""
        code, out, err = run_all(["sync", "ALTA", "--source", self.note("nota_sponsor.md")])
        self.assertEqual(code, 0, err)
        self.assertIn(f"sentinel warning: {NOTICE}", err)
        self.assertIn(NOTICE, json.loads(out)["prose_review"]["notice"])
        nxt = json.loads(run_ok(["next", "ALTA"]))
        self.assertIn(NOTICE, nxt["text"])


if __name__ == "__main__":
    unittest.main()
