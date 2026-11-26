"""IMP-433: the project's refine / compose / implementation-feedback outputs, hashed independently of the checkout path.

`build_project_outputs(work)` runs the three commands on a plain project; `project_output_hashes(work)` returns the
normalized sha256 of their outputs. The baseline in fixtures/change_inc8 was taken with the code before IMP-433.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import build_matured_workspace, gap_acceptance_answer, run_ok  # noqa: E402
from release_project_flow import ROOT, normalized_sha256  # noqa: E402

PID = "BASE"
BASELINE = Path(__file__).resolve().parent / "fixtures" / "change_inc8" / "after_backlog_project_sha256.json"
RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads.

In scope: read-only risk dashboard for open queues. Out of scope: editing cases.

Metric: reduce manual preparation by 30 percent in the first release month.
"""
EARS = "When queue metrics are available, the system shall display open risk queues."
OBJECTIVE = "Objective: let operations leads review risk queues before the daily meeting."
GLOBS = ("03_specs/prd.md", "03_specs/compositions/*", "04_backlog/EPIC-001.md", "04_backlog/US-*.md",
         "04_backlog/refinements/*", "07_changes/05_implementation_feedback/*")


def build_project_outputs(work: Path) -> None:
    """Run in the current folder (`work`): matured project, then refine, compose and implementation-feedback."""
    ws = build_matured_workspace(PID, RAW, gap_acceptance_answer(EARS), backlog=False)
    (ws / "00_raw" / "02_technology_context" / "tech.md").write_text(
        "Execution commands: run pytest. Critical surfaces: risk dashboard module and queue metrics API. "
        "Engineering practices: preserve trace IDs and validate queue failures.", encoding="utf-8")
    (ws / "00_raw" / "04_quality_context" / "quality.md").write_text(
        "Quality evidence: fail-to-pass, pass-to-pass and acceptance evidence must cover queue metrics.", encoding="utf-8")
    run_ok(["reindex", PID])
    run_ok(["backlog", PID])
    drafts = {
        "refine": {"proposals": [{
            "id": "BREF-001", "kind": "reslice", "target_stories": ["US-001"], "source_units": ["SPEC-U-001"],
            "slicing_pattern": "Data / External Dependency",
            "recommendation": "Keep this story focused on the confirmed queue metrics dependency.",
            "rationale": "The Spec Unit names queue metrics as the observable trigger and response.",
            "citations": [EARS]}]},
        "compose": {"blocks": [{"section": "1", "paragraphs": [{
            "text": "The PRD narrative can say the dashboard is meant to help operations leads review risk queues.",
            "citations": [OBJECTIVE]}]}]},
        "feedback": {"findings": [{
            "id": "IFB-001", "type": "gap", "gap_id": "GAP-FEEDBACK-QUEUE-DETAIL", "story": "US-001",
            "acceptance_criteria": "AC-001-01", "source_units": ["SPEC-U-001"],
            "summary": "Implementation found that the queue detail dependency is not covered by the story contract.",
            "evidence": "Queue detail test fails because the risk indicator source is not in the handoff contract.",
            "source": "implementation test run", "mark_stale": True}]},
    }
    for name, command in (("refine", "refine-backlog"), ("compose", "compose"), ("feedback", "implementation-feedback")):
        path = work / f"{name}.json"
        path.write_text(json.dumps(drafts[name]), encoding="utf-8")
        run_ok([command, PID, "--source", str(path)])


def project_output_hashes(work: Path, only: tuple[str, ...] = GLOBS) -> dict[str, str]:
    base = work / "workspaces" / PID
    tokens = []
    for root, token in ((ROOT.parent, "<REPO>"), (work, "<WORK>"), (base, "<WORK>")):
        for value in {str(root), root.as_posix(), str(root.resolve()), root.resolve().as_posix()}:
            tokens.append((value, token))
    tokens.sort(key=lambda item: -len(item[0]))
    found = {}
    for pattern in only:
        for path in sorted(base.glob(pattern)):
            if path.is_file():
                found[path.relative_to(base).as_posix()] = normalized_sha256(path.read_bytes(), tokens)
    return dict(sorted(found.items()))


if __name__ == "__main__":
    import os
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        old = os.getcwd()
        os.chdir(tmp)
        try:
            build_project_outputs(Path(tmp))
            print(json.dumps(project_output_hashes(Path(tmp)), indent=2))
        finally:
            os.chdir(old)
