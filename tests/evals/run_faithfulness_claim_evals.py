from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "evals" / "faithfulness_claims"
REPORTS = REPO_ROOT / "tests" / "evals" / "reports"

sys.path.insert(0, str(REPO_ROOT))
from sentinel.validation import artifact_faithfulness_report  # noqa: E402


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_fixture(fixture_dir: Path) -> dict[str, object]:
    evidence = load_json(fixture_dir / "evidence.json")["quotes"]
    answer_key = load_json(fixture_dir / "answer_key.json")
    artifact_reports = []
    unsupported_claims: list[str] = []

    for artifact_path in sorted((fixture_dir / "artifacts").glob("*.md")):
        relative_artifact = artifact_path.relative_to(fixture_dir).as_posix()
        report = artifact_faithfulness_report(
            artifact_path.read_text(encoding="utf-8"),
            evidence,
            artifact=relative_artifact,
        )
        artifact_reports.append(report)
        unsupported_claims.extend(
            str(claim["text"]) for claim in report["claims"] if not claim["supported"]
        )

    total_claims = sum(int(report["claim_count"]) for report in artifact_reports)
    supported_claims = sum(int(report["supported_claim_count"]) for report in artifact_reports)
    score = round(supported_claims / total_claims, 3) if total_claims else 1.0
    mismatches = fixture_mismatches(answer_key, score, unsupported_claims)

    return {
        "fixture": fixture_dir.name,
        "score": score,
        "claim_count": total_claims,
        "supported_claim_count": supported_claims,
        "unsupported_claim_count": total_claims - supported_claims,
        "unsupported_claims": unsupported_claims,
        "artifact_reports": artifact_reports,
        "ok": not mismatches,
        "mismatches": mismatches,
    }


def fixture_mismatches(answer_key: dict, score: float, unsupported_claims: list[str]) -> list[str]:
    mismatches: list[str] = []
    expected_score = answer_key.get("expected_score")
    if expected_score is not None and score != float(expected_score):
        mismatches.append(f"expected score {float(expected_score):.3f}, got {score:.3f}")

    expected_below = answer_key.get("expected_score_below")
    if expected_below is not None and not score < float(expected_below):
        mismatches.append(f"expected score below {float(expected_below):.3f}, got {score:.3f}")

    expected_unsupported = [str(item).lower() for item in answer_key.get("unsupported_contains", [])]
    unsupported_text = "\n".join(unsupported_claims).lower()
    for fragment in expected_unsupported:
        if fragment not in unsupported_text:
            mismatches.append(f"expected unsupported claim containing {fragment!r}")

    if answer_key.get("expect_no_unsupported") and unsupported_claims:
        mismatches.append(f"expected no unsupported claims, got {len(unsupported_claims)}")
    return mismatches


def main() -> int:
    fixtures = [path for path in sorted(FIXTURES.iterdir()) if path.is_dir()]
    results = [evaluate_fixture(fixture) for fixture in fixtures]
    faithful = next((result for result in results if result["fixture"] == "faithful"), None)
    trap = next((result for result in results if result["fixture"] == "silent_invention"), None)
    falsable_ok = bool(faithful and faithful["score"] == 1.0 and trap and trap["score"] < 1.0)
    report = {
        "date": date.today().isoformat(),
        "eval": "faithfulness_claims",
        "falsable_ok": falsable_ok,
        "fixtures": results,
        "summary": {
            "fixtures": len(results),
            "ok": all(result["ok"] for result in results) and falsable_ok,
            "avg_score": round(sum(float(result["score"]) for result in results) / len(results), 3)
            if results
            else 1.0,
            "total_unsupported_claims": sum(int(result["unsupported_claim_count"]) for result in results),
        },
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    output = REPORTS / f"faithfulness_claim_eval_{report['date']}.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Faithfulness claim evals - {report['date']}")
    for result in results:
        status = "OK " if result["ok"] else "FAIL"
        print(
            f"  [{status}] {result['fixture']:18s} score={float(result['score']):.3f} "
            f"claims={result['supported_claim_count']}/{result['claim_count']} "
            f"unsupported={result['unsupported_claim_count']}"
        )
        for mismatch in result["mismatches"]:
            print(f"         mismatch: {mismatch}")
    print(f"  falsable_ok={falsable_ok}")
    print(f"  report={output.relative_to(REPO_ROOT).as_posix()}")
    return 0 if report["summary"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
