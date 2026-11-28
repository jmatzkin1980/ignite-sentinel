"""Shared test helpers (IMP-305).

- `run_cli` runs one command in-process and returns its exit code and output.
- `SnapshotWorkspaceCase` builds a workspace once per class and gives every test a
  fresh copy of it, at the same path, so a test can mutate it freely.
- `build_matured_workspace` is the chain most backlog tests start from:
  init, ingest, an answered GAP-ACCEPTANCE, brief, specs and backlog.
"""
from __future__ import annotations

import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from sentinel.cli import main


def run_cli(argv: list[str]) -> tuple[int, str]:
    """Run one command in-process; return (exit code, stdout). Stderr is discarded."""
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(io.StringIO()):
        code = main(list(argv))
    return code, out.getvalue()


def run_ok(argv: list[str]) -> str:
    """Run one command and fail the test if it does not exit 0."""
    code, out = run_cli(argv)
    if code != 0:
        raise AssertionError(f"{' '.join(argv)} exited {code}:\n{out[-2000:]}")
    return out


def place_harvest_docs(project_id: str, text: str) -> None:
    """IMP-435 (B-37): a harvest lists documents the workspace has; put the ones `text` names where it says they are."""
    from sentinel.harvest import harvest_doc_paths
    from sentinel.workspace import workspace_path

    for name, path in harvest_doc_paths(text).items():
        target = workspace_path(project_id) / path
        if path.startswith("00_raw/") and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"# {name}\n", encoding="utf-8")


IDS_SCOPE_ANSWER = "\n".join([
    "### GAP-SCOPE",
    "- Respuesta: El alta de proveedores con aprobación por monto.",
    "- Borde:",
    "  - nuevo | pantalla | Bandeja de aprobaciones",
    "  - nuevo | regla | Aprobación por monto",
    "  - adyacente | endpoint | Alta de proveedores",
    "  - adyacente | dato | Tabla de proveedores",
    "  - preservado | proceso | Alta de monto bajo",
    "  - preservado | regla | Validación de CUIT",
    "- Owner / fuente: Jefa de Compras",
    "- Estado de decisión: confirmado",
    "",
])


def gap_acceptance_answer(ears: str, evidence_label: str = "Evidence or reference") -> str:
    """A confirmed answer to GAP-ACCEPTANCE carrying the given EARS statement(s)."""
    return (
        "### GAP-ACCEPTANCE\n"
        f"- Answer: {ears}\n"
        "- Owner / source: Client workshop\n"
        f"- {evidence_label}: Synthetic EARS response\n"
        "- Decision status: confirmed\n"
    )


def build_matured_workspace(project_id: str, raw: str, answers: str, *, backlog: bool = True) -> Path:
    """Run the matured-backlog chain in the current folder; return the workspace path.

    `raw` is written to raw.md and ingested; `answers` (see `gap_acceptance_answer`)
    is written to answers.md and resolved. The chain stops after specs when
    `backlog` is False, for tests that add context before generating the backlog.
    """
    root = Path.cwd()
    (root / "raw.md").write_text(raw, encoding="utf-8")
    (root / "answers.md").write_text(answers, encoding="utf-8")
    run_ok(["init", project_id, "--brief-version", "1"])
    run_ok(["ingest", project_id, "--source", str(root / "raw.md")])
    run_ok(["resolve-gaps", project_id, "--source", str(root / "answers.md")])
    run_ok(["brief", project_id])
    run_ok(["specs", project_id])
    if backlog:
        run_ok(["backlog", project_id])
    return root / "workspaces" / project_id


class SnapshotWorkspaceCase(unittest.TestCase):
    """Build the workspace once per class; each test gets a fresh copy at the same path.

    Subclasses implement `build_workspace()`, which runs with the working folder set
    to the class's work folder. Before each test the work folder is restored from a
    snapshot taken right after the build, so tests stay independent. The copy keeps
    the build's path because generated artifacts quote absolute paths.

    In each test, `self.temp` is the work folder and the current directory.
    """

    _class_dir: Path
    _work: Path
    _snapshot: Path

    @classmethod
    def build_workspace(cls) -> None:
        raise NotImplementedError

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._class_dir = Path(tempfile.mkdtemp(prefix=f"sentinel_{cls.__name__}_"))
        cls._work = cls._class_dir / "work"
        cls._snapshot = cls._class_dir / "snapshot"
        cls._work.mkdir()
        old = Path.cwd()
        os.chdir(cls._work)
        try:
            cls.build_workspace()
        except BaseException:
            os.chdir(old)
            shutil.rmtree(cls._class_dir, ignore_errors=True)
            raise
        os.chdir(old)
        shutil.copytree(cls._work, cls._snapshot)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._class_dir, ignore_errors=True)
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        self.old_cwd = Path.cwd()
        if self._work.exists():
            shutil.rmtree(self._work)
        shutil.copytree(self._snapshot, self._work)
        os.chdir(self._work)
        self.temp = self._work

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        super().tearDown()


_HOME_SECTION = {2: "objetivo", 3: "alcance", 4: "proceso", 6: "preservado", 7: "reglas"}


def complete_extraction(project_id: str, change_id: str = "CHG-001", skip: tuple[str, ...] = ()) -> None:
    """IMP-402: inventory, propose every element as a section (or as UNCHANGED rows for the preserved surfaces) and confirm all.

    `skip`: elements a test already proposed and confirmed its own way (IMP-406)."""
    from sentinel.extraction.confirm import confirm_proposals
    from sentinel.extraction.inventory import build_inventory, element_lines, element_text, load_inventory
    from sentinel.extraction.coverage import preserved_coverage
    from sentinel.extraction.proposals import record_proposals
    from sentinel.workspace import workspace_path

    waive_crosses(project_id, change_id)
    build_inventory(project_id, change_id)
    base = workspace_path(project_id)
    elements = [e for e in (load_inventory(base, change_id) or {}).get("elements", []) if e["id"] not in skip]
    missing = preserved_coverage(project_id, change_id)["missing"]
    blocks: list[str] = []
    for index, element in enumerate(elements):
        flat = " ".join((element_text(base, element) or "").split())
        quote = flat[:60].strip()
        first, last = element_lines(element)
        span = f"- Líneas: {first}-{last}"
        if index == 0 and missing:
            lines = [f"### {element['id']}", "- Tratamiento: requisito", span, f'- Cita: "{quote}"']
            for surface in missing:
                lines += [f"- Enunciado: El sistema debe continuar funcionando como hoy en {surface}.",
                          "  - Delta: UNCHANGED", f"  - Superficie: {surface}"]
        else:
            section = _HOME_SECTION.get(element.get("home"), "reglas")
            lines = [f"### {element['id']}", "- Tratamiento: seccion", span, f"- Seccion: {section}", f'- Cita: "{quote}"']
        blocks.append("\n".join(lines) + "\n")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "proposals.md"
        path.write_text("\n".join(blocks), encoding="utf-8")
        result = record_proposals(project_id, change_id, path)
    if result.get("rejected"):
        raise AssertionError(f"complete_extraction: rejected {result['rejected']}")
    confirm_proposals(project_id, change_id, "all")


def waive_crosses(project_id: str, change_id: str = "CHG-001", reason: str = "fuera del alcance de esta prueba",
                  coherence: bool = True) -> None:
    """IMP-404: waive every cross-read of the change that is still missing, so a test of a later step gets past `crosses`
    (and, IMP-410, the lens coherence once it can be read, unless `coherence=False`)."""
    from sentinel.core.io import forget_read_snapshots
    from sentinel.crosses.record import skip_cross
    from sentinel.crosses.state import cross_status

    forget_read_snapshots()
    for kind in cross_status(project_id, change_id)["missing"]:
        skip_cross(project_id, change_id, kind, reason)
    if coherence:
        waive_coherence(project_id, change_id, reason)


def waive_coherence(project_id: str, change_id: str = "CHG-001", reason: str = "fuera del alcance de esta prueba") -> None:
    """IMP-410: waive the lens coherence of the change (when it is ready to be read), so a later step is reachable."""
    from sentinel.change_coherence import coherence_ready, skip_change_coherence
    from sentinel.core.io import forget_read_snapshots

    forget_read_snapshots()
    if coherence_ready(project_id, change_id):
        skip_change_coherence(project_id, change_id, reason)
    forget_read_snapshots()  # the lens view read files this test writes next


def lines_field(element_id: str, source: str = "pedido_ids.md") -> str:
    """IMP-406: the `- Líneas: A-B` line (the whole element) of an element of a change_extraction fixture."""
    from sentinel.extraction.inventory import element_lines, parse_request_elements

    path = Path(__file__).resolve().parent / "fixtures" / "change_extraction" / source
    for element in parse_request_elements(path.read_text(encoding="utf-8"), "F-01", "pedido.md"):
        if element["id"] == element_id:
            first, last = element_lines(element)
            return f"- Líneas: {first}-{last}"
    return ""


def class_deferred(project_id: str, change_id: str = "CHG-001", impact: str = "operativo") -> list[str]:
    """IMP-406: class the open non-blocking questions nobody classed yet (they default to `construccion` and hold the
    verdict at NOT_READY, so `/export --final` refuses); the ids that were classed."""
    from sentinel.changes import deferred_gaps
    from sentinel.core.io import forget_read_snapshots

    forget_read_snapshots()
    found = [d["id"] for d in deferred_gaps(project_id, change_id) if not d["classed"]]
    for gap in found:
        run_ok(["gaps", project_id, "--change", change_id, "--id", gap, "--impact", impact,
                "--reason", "lo resuelve otra área (prueba)"])
    forget_read_snapshots()
    return found


def export_final_brief(project_id: str, change_id: str = "CHG-001") -> str:
    """IMP-406: the `export_final` milestone, so a test of a later step (specs, backlog, validate) gets past it."""
    class_deferred(project_id, change_id)
    return run_ok(["export", project_id, "--artifact", "brief", "--change", change_id, "--final"])


def reproposal_block(project_id: str, change_id: str, element_id: str, corrected: bool = True) -> str:
    """IMP-406 I4: the stored proposal of an element as a worksheet block, corrected (a note, a reason or a statement
    says one thing more), so it is a proposal that differs from the one a verification reopened.
    `corrected=False` gives the same proposal again, as it was."""
    from sentinel.core.io import forget_read_snapshots
    from sentinel.extraction.lines import format_ranges
    from sentinel.extraction.proposals import load_proposals
    from sentinel.workspace import workspace_path

    forget_read_snapshots()
    item = load_proposals(workspace_path(project_id), change_id)["items"][element_id]
    lines = [f"### {element_id}", f"- Tratamiento: {item['treatment']}", f"- Líneas: {format_ranges(item['lines'])}",
             f'- Cita: "{item["quote"]}"']
    if item["treatment"] == "seccion":
        lines += [f"- Seccion: {item['section']}"]
        if corrected or item.get("summary"):
            lines += [f"- Resumen: {'corregido tras la verificación' if corrected else item['summary']}"]
    elif item["treatment"] == "descarte":
        lines += [f"- Motivo: {item['reason']}{' (corregido tras la verificación)' if corrected else ''}"]
    else:
        for statement in item["statements"]:
            text = statement["text"].rstrip(".") + (" en todos los casos." if corrected else ".")
            lines += [f"- Enunciado: {text}", f"  - Delta: {statement['delta']}",
                      f"  - Superficie: {'; '.join(statement['surfaces'])}"]
    return "\n".join(lines) + "\n"


class SyncCase(SnapshotWorkspaceCase):
    """H27 inc 6a: a change with its baseline harvested, a design loaded and both cross-reads recorded.

    Copied from the `NextCase` of `test_h26_cross_next.py`. Subclasses set `PID` (one per module).
    The contradiction question is answered, so the change has no open question left.
    """

    PID = "SYNC"
    CID = "CHG-001"
    FIXTURES = Path(__file__).resolve().parent / "fixtures"

    @classmethod
    def build_workspace(cls) -> None:
        from sentinel.crosses.record import record_cross

        crosses = cls.FIXTURES / "change_crosses"
        pid, cid = cls.PID, cls.CID
        root = Path.cwd()
        shutil.copy(crosses / "pedido_contradiccion.md", root / "pedido.md")
        shutil.copy(crosses / "harvest_compras.md", root / "harvest_compras.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", pid])
        run_ok(["ingest", pid, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", pid, "--source", "scope.md", "--change", cid])
        run_ok(["sources", pid, "--load", str(cls.FIXTURES / "change_baseline" / "sad-compras.md"),
                "--role", "linea_de_base", "--change", cid])
        run_ok(["harvest", pid, "--source", "harvest_compras.md", "--change", cid])
        run_ok(["sources", pid, "--load", str(crosses / "prototipo-aprobaciones.html"),
                "--role", "diseno_nuevo", "--change", cid])
        found = cls._ids()
        record_cross(pid, cid, "diseno", cls._claims("cruce_diseno.md", found))
        record_cross(pid, cid, "contradicciones", cls._claims("cruce_contradicciones.md", found))
        # the divergence and the contradiction each open a question: answer both
        blocks = []
        for gap in cls._open_gaps():
            if gap.startswith(("GAP-DIS-", "GAP-CON-")):
                chosen = "(A) rige el diseño." if gap.startswith("GAP-DIS-") else "(A) rige la primera."
                blocks += [f"### {gap}", f"- Respuesta: {chosen}", "- Owner / fuente: Jefa de Compras",
                           "- Estado de decisión: confirmado", ""]
        answer = root / "answer.md"
        answer.write_text("\n".join(blocks), encoding="utf-8")
        run_ok(["resolve-gaps", pid, "--source", str(answer), "--change", cid])

    @classmethod
    def _ids(cls) -> dict[str, str]:
        from sentinel.status import change_sources

        found = change_sources(cls.PID, cls.CID)["by_role"]
        return {"pedido": found["pedido"][0], "diseno": found["diseno_nuevo"][0]}

    @classmethod
    def _claims(cls, name: str, ids: dict[str, str]) -> Path:
        text = (cls.FIXTURES / "change_crosses" / name).read_text(encoding="utf-8")
        text = text.replace("F-PED", ids["pedido"]).replace("F-DIS", ids["diseno"])
        path = Path.cwd() / f"sub-{name}"
        path.write_text(text, encoding="utf-8")
        return path

    @classmethod
    def _gap_rows(cls) -> list[dict]:
        from sentinel.changes import change_gaps_path
        from sentinel.gaps import parse_gap_rows
        from sentinel.workspace import workspace_path

        path = change_gaps_path(workspace_path(cls.PID), cls.CID)
        return [g for g in parse_gap_rows(path.read_text(encoding="utf-8")) if g.get("id") != "NONE"]

    @classmethod
    def _open_gaps(cls) -> list[str]:
        return [g["id"] for g in cls._gap_rows() if str(g.get("status", "OPEN")).strip("`").upper() != "CLOSED"]

    def setUp(self) -> None:
        super().setUp()
        from sentinel.core.io import forget_read_snapshots

        forget_read_snapshots()

    def step(self) -> dict:
        from sentinel.core.io import forget_read_snapshots
        from sentinel.readiness_verdict import change_next_step

        forget_read_snapshots()
        return change_next_step(self.PID, self.CID)

    def ids(self) -> dict[str, str]:
        return self._ids()

    def claims(self, name: str, ids: dict[str, str]) -> Path:
        return self._claims(name, ids)

    def open_gaps(self) -> list[str]:
        return self._open_gaps()

    def gap_answer(self, gap_id: str) -> str:
        """The answer stored for a question in the change's gaps.md ('' when it has none)."""
        for row in self._gap_rows():
            if row.get("id") == gap_id:
                return str(row.get("resolution_note") or row.get("answer") or "")
        return ""

    def write_v2(self, name: str = "pedido.md", old: str = "mayor a 5.000.000", new: str = "mayor a 3.000.000") -> Path:
        """The request with one replacement, written to `name` in the current folder."""
        text = (self.FIXTURES / "change_crosses" / "pedido_contradiccion.md").read_text(encoding="utf-8")
        if old not in text:
            raise AssertionError(f"{old!r} is not in the request fixture")
        path = Path.cwd() / name
        path.write_text(text.replace(old, new), encoding="utf-8")
        return path


class ProjectExtractionCase(SnapshotWorkspaceCase):
    """IMP-420 (H27 inc 6b): a project whose request carries element ids (RN-, CA-, HU-, PD-), loaded without a change."""

    PID = "PEX"
    FIXTURES = Path(__file__).resolve().parent / "fixtures" / "project_extraction"
    SOURCE = "brief_alta_proveedores.md"

    @classmethod
    def build_workspace(cls) -> None:
        shutil.copy(cls.FIXTURES / cls.SOURCE, Path.cwd() / cls.SOURCE)
        run_ok(["init", cls.PID])
        run_ok(["ingest", cls.PID, "--source", cls.SOURCE])
