"""IMP-265: release-split proposal evals with seeded proposals.

Each fixture in tests/fixtures/evals/split_proposal/ is a synthetic brief v2 (rotulated
as such), its open gaps, an agent proposal and the finding codes the runtime must
raise. Seeded: a criterion without source, an empty release, a layer cut (by name
and by lens), a misplaced inheritance, spike and conditional contracts, an integrator
without its consumption table, and clean proposals that must pass; plus a held-out
split.

Scored per finding code: precision and recall per split. The run fails on a
mismatch, and on a drop below the floor in tests/evals/metric_baseline.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sentinel.split_proposal import validate_proposal  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "evals" / "split_proposal"
BASELINE = Path(__file__).resolve().parent / "metric_baseline.json"
TOLERANCE = 0.001


def _ratio(n: int, d: int) -> float:
    return round(n / d, 3) if d else 1.0


def run() -> dict:
    cases, tally = [], {}
    for path in sorted(FIXTURES.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        result = validate_proposal(data["brief"], data["payload"], set(data.get("open_gaps", [])))
        got = sorted({f["code"] for f in result["findings"]})
        want = sorted(set(data["expected"]))
        t = tally.setdefault(data["split"], {"tp": 0, "fp": 0, "fn": 0})
        t["tp"] += len(set(got) & set(want))
        t["fp"] += len(set(got) - set(want))
        t["fn"] += len(set(want) - set(got))
        cases.append({"case": data["case"], "split": data["split"], "ok": got == want, "got": got, "want": want})
    metrics = {}
    for split, t in tally.items():
        p, r = _ratio(t["tp"], t["tp"] + t["fp"]), _ratio(t["tp"], t["tp"] + t["fn"])
        metrics[split] = {"precision": p, "recall": r, "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}
    total = {k: sum(t[k] for t in tally.values()) for k in ("tp", "fp", "fn")}
    overall = {"precision": _ratio(total["tp"], total["tp"] + total["fp"]), "recall": _ratio(total["tp"], total["tp"] + total["fn"])}
    return {"cases": cases, "metrics": metrics, "overall": overall}


def snapshot(result: dict) -> dict[str, float]:
    return {
        "split_proposal_precision": result["overall"]["precision"],
        "split_proposal_recall": result["overall"]["recall"],
        "split_proposal_held_out_f1": result["metrics"].get("held_out", {}).get("f1", 1.0),
    }


def main() -> int:
    result = run()
    for case in result["cases"]:
        detail = "" if case["ok"] else f" got={case['got']} want={case['want']}"
        print(f"  [{'OK ' if case['ok'] else 'FAIL'}] {case['case']:32s} split={case['split']}{detail}")
    current = snapshot(result)
    print("Split proposal evals (IMP-265): " + " ".join(f"{k}={v:.3f}" for k, v in current.items()))
    data = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {"floor": {}}
    if "--update-metric-baseline" in sys.argv:
        data.setdefault("floor", {}).update(current)
        BASELINE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    regressions = [f"{k} {current[k]:.3f} < floor {float(v):.3f}" for k, v in sorted(data.get("floor", {}).items())
                   if k in current and current[k] + TOLERANCE < float(v)]
    for line in regressions:
        print(f"  [FAIL] metric regression: {line}")
    return 0 if all(c["ok"] for c in result["cases"]) and not regressions else 1


if __name__ == "__main__":
    sys.exit(main())
