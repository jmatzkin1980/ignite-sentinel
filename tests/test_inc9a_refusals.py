"""IMP-435 (H27 inc 9a) task 3: export, view and input refusals get the right exit code and a runnable next step.

Each test repeats the command sequence of the reviewer (docs/evolution/inc9-review): C-02 (+B-17), A-05, A-23, C-13,
C-20, A-32, A-34, B-37, B-38, B-29, B-30.
"""
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

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
from test_h26_extract_proposals import CID as EXP_CID, PID as EXP_PID, ProposalsCase, block  # noqa: E402
from test_h27_change_release import CID, PID as REL_PID, ChangeReleaseCase  # noqa: E402
from test_h27_export_v2 import CID as EXPORT_CID, PID as EXPORT_PID, ExportCase  # noqa: E402

from sentinel.cli import build_parser, main  # noqa: E402
from sentinel.commands import EXPORT_ARTIFACTS  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FX = ROOT / "fixtures"
INC9A = FX / "inc9a"


def run_all(argv: list[str]) -> tuple[int, str, str]:
    """(exit code, stdout, stderr) of one command."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def next_step_of(err: str) -> str:
    """The `next step:` line of an error, without the `(skill: ..)` the CLI appends."""
    found = re.search(r"^next step: (.*?)(?: \(skill: [^)]*\))?$", err, re.M)
    return found.group(1) if found else ""


def parse_command(command: str):
    """A next step that is a command parses with the real parser (PATH, TEXTO and IMPACT stand for a value)."""
    assert command.startswith("/"), command
    return build_parser().parse_args(shlex.split(command[1:].replace("--impact IMPACT", "--impact operativo")))


class ProjectNotStarted(SnapshotWorkspaceCase):
    """A project that only has `/init`: nothing was ingested, no request was made."""

    @classmethod
    def build_workspace(cls):
        run_ok(["init", "ALTA"])

    def test_export_missing_context_request(self):
        """A-05: `/export --artifact context-request --domain design` before `/context-request` is a missing prerequisite."""
        code, _, err = run_all(["export", "ALTA", "--artifact", "context-request", "--domain", "design"])
        self.assertEqual(code, 4, err)
        self.assertIn("next step: /context-request ALTA --domain design", err)

    def test_export_interview_before_ingest(self):
        """A-23: the interview of gaps that do not exist yet."""
        code, _, err = run_all(["export", "ALTA", "--artifact", "gaps", "--format", "interview"])
        self.assertEqual(code, 4, err)
        self.assertIn("next step: /ingest ALTA --source PATH", err)

    def test_override_missing_file(self):
        """C-20: `--override` with a file that does not exist says so (and does not ask for a decision)."""
        for argv in (["validate", "ALTA", "--override", "nofile.json"], ["quality", "ALTA", "--override", "nofile.json"],
                     ["backlog-status", "ALTA", "--override", "nofile.json"]):
            code, _, err = run_all(argv)
            self.assertEqual(code, 3, (argv, err))
            self.assertIn("not found", err)
            self.assertNotIn("at least one decision", err)

    def test_fake_pdf_refused(self):
        """A-32: a `.pdf` whose bytes happen to be UTF-8 text is refused like a binary one."""
        Path("fake.pdf").write_bytes(b"%PDF-1.4 fake pedido de compras\n")
        Path("real.pdf").write_bytes(b"%PDF-1.7\n\xff\xfe\x00binary")
        code, _, binary = run_all(["ingest", "ALTA", "--source", "real.pdf"])
        self.assertEqual(code, 3, binary)
        code, _, fake = run_all(["ingest", "ALTA", "--source", "fake.pdf"])
        self.assertEqual(code, 3, fake)
        self.assertEqual(fake.replace("fake.pdf", "x.pdf"), binary.replace("real.pdf", "x.pdf"))
        self.assertFalse(list((workspace_path("ALTA") / "00_raw").rglob("fake.*")))


class StoryCase(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        for argv in (["init", "ALTA"], ["ingest", "ALTA", "--source", str(INC9A / "pedido_alta.md")],
                     ["resolve-gaps", "ALTA", "--source", str(INC9A / "respuestas_alta.md")],
                     ["brief", "ALTA", "--profile", "UI", "--genesis", "greenfield"],
                     ["specs", "ALTA"], ["backlog", "ALTA"]):
            run_ok(argv)

    def test_story_status_unknown_id(self):
        """A-34: the backlog exists; it is the id that is wrong."""
        code, _, err = run_all(["story-status", "ALTA", "--story", "US-099", "--set", "Ready"])
        self.assertEqual(code, 3, err)
        self.assertIn("Story does not exist: US-099", err)
        self.assertIn("Known stories: US-001", err)
        self.assertNotIn("Run /backlog", err)
        parse_command(next_step_of(err))

    def test_story_status_done_to_done(self):
        """A-34: the table allows only `Stale` after `Done`."""
        for status in ("Ready", "In Progress", "In Review", "Done"):
            run_ok(["story-status", "ALTA", "--story", "US-001", "--set", status])
        code, _, err = run_all(["story-status", "ALTA", "--story", "US-001", "--set", "Done"])
        self.assertEqual(code, 3, err)
        self.assertIn("Done -> Done", err)


class ChangeOnlyCase(SnapshotWorkspaceCase):
    """BORR: a workspace that only holds a change (no project requirements)."""

    @classmethod
    def build_workspace(cls):
        shutil.copy(FX / "change_borrador.md", Path.cwd() / "pedido.md")
        run_ok(["init", "BORR"])
        run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"])

    def test_view_diagrams_change_only(self):
        """C-13: `/view --artifact diagrams` in a change-only workspace points to the view of the change."""
        code, _, err = run_all(["view", "BORR", "--artifact", "diagrams"])
        self.assertEqual(code, 4, err)
        self.assertEqual(next_step_of(err), "/view BORR --artifact diagrams --change CHG-001")

    def test_harvest_doc_not_in_workspace(self):
        """B-37: the harvest lists a document that the workspace does not have (only the SAD was loaded)."""
        run_ok(["sources", "BORR", "--load", str(FX / "change_baseline" / "sad-compras.md"), "--role", "linea_de_base",
                "--change", "CHG-001"])
        code, _, err = run_all(["harvest", "BORR", "--source", str(FX / "change_inc7" / "harvest_parcial.md"),
                                "--change", "CHG-001"])
        self.assertEqual(code, 3, err)
        self.assertIn("manual-compras", err)
        self.assertIn("00_raw/06_baseline/manual-compras.md", err)
        self.assertFalse((workspace_path("BORR") / "01_discovery" / "harvest.json").exists())
        parsed = parse_command(next_step_of(err))
        self.assertEqual((parsed.command, parsed.role), ("sources", "linea_de_base"))


class ExtractRejected(ProposalsCase):
    def test_extract_all_rejected(self):
        """B-38: a proposals file with nothing recorded says so on stderr, with the reason and the valid names."""
        quote = '- Cita: "la jefatura aprueba las altas de monto alto"'
        Path("p.md").write_text(block("SEC-objetivo", "- Treatment: section", "- Section: glosario", quote),
                                encoding="utf-8")
        code, out, err = run_all(["extract", EXP_PID, "--change", EXP_CID, "--proposals", "p.md"])
        self.assertEqual(code, 0, err)
        self.assertEqual(len(json.loads(out)["rejected"]), 1)
        self.assertIn("sentinel warning:", err)
        self.assertIn("SEC-objetivo", err)
        for name in ("objetivo", "usuarios", "proceso", "alcance", "preservado", "reglas", "aceptacion"):  # the change speaks Spanish
            self.assertIn(name, err)

    def test_extract_some_recorded_is_quiet(self):
        code, _, err = run_all(["extract", EXP_PID, "--change", EXP_CID, "--proposals",
                                str(FX / "change_extraction" / "propuestas_ejemplo.md")])
        self.assertEqual(code, 0, err)
        self.assertNotIn("sentinel warning:", err)


class ImpactPlaceholder(ExportCase):
    def test_impact_placeholder(self):
        """B-29: nothing a BA is told to paste carries `construccion|operativo` (in a shell the bar is a pipe)."""
        step = json.loads(run_ok(["next", EXPORT_PID, "--change", EXPORT_CID]))
        self.assertEqual(step["key"], "export_final", step)
        code, _, final_err = run_all(["export", EXPORT_PID, "--artifact", "brief", "--change", EXPORT_CID, "--final"])
        self.assertEqual(code, 4, final_err)
        code, _, misuse_err = run_all(["gaps", EXPORT_PID, "--change", EXPORT_CID, "--id", "GAP-X"])
        self.assertEqual(code, 3, misuse_err)
        for command in (step["command"], next_step_of(final_err), next_step_of(misuse_err)):
            self.assertNotIn("construccion|operativo", command)
            self.assertIn("--impact IMPACT", command)
            parse_command(command)
        for text in (step["text"], final_err, misuse_err):
            self.assertIn("IMPACT = construccion u operativo", text)
            self.assertNotIn("construccion|operativo", text)


class ReleaseCase(ChangeReleaseCase):
    def test_export_release_guide_change(self):
        """C-02: the guide of the series of a change is exported like the other deliverables of a change."""
        code, out, err = run_all(["export", REL_PID, "--artifact", "release-guide", "--change", CID])
        self.assertEqual(code, 0, err)
        target = workspace_path(REL_PID) / "08_context_packs" / "exports" / f"{CID}-release-guide.md"
        self.assertTrue(target.is_file())
        self.assertEqual(json.loads(out)["path"], target.as_posix())

    def test_export_change_refusal_lists_only_what_it_exports(self):
        """B-17: every artifact the refusal of `/export --artifact prd --change` lists is one `/export` takes."""
        code, _, err = run_all(["export", REL_PID, "--artifact", "prd", "--change", CID])
        self.assertEqual(code, 3, err)
        listed = re.search(r"admite (.+?), no prd", err).group(1).split(" o ")
        self.assertIn("release-guide", listed)
        for artifact in listed:
            self.assertIn(artifact, EXPORT_ARTIFACTS)
        self.assertNotIn("|", next_step_of(err))
        parse_command(next_step_of(err))

    def test_specs_release_next(self):
        """B-30: the next step of `/specs --change --release r1` is about the release, not the change as a whole."""
        result = json.loads(run_ok(["specs", REL_PID, "--change", CID, "--release", "r1"]))
        self.assertIn(f"03_specs/{CID}/r1/", result["next_step"])
        self.assertIn(f"/backlog {REL_PID} --change {CID} --release r1", result["next_step"])
        whole = json.loads(run_ok(["specs", REL_PID, "--change", CID]))
        self.assertIn(f"/backlog {REL_PID} --change {CID}", whole["next_step"])


if __name__ == "__main__":
    unittest.main()
