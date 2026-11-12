"""IMP-266: partition validation evals with seeded partitions.

Each fixture in tests/fixtures/evals/partition/ is a synthetic brief v2 (labelled as
such), its open gaps, the contracts frozen by a previous confirmation, a proposal and
the finding codes /split --confirm must refuse it with. Seeded: a cycle (a missing
contract), an asymmetric edge, coverage missing and duplicated, a second owner and an
extension without its cross note, a relaxed Must rule without restoration, edges
without their contract; held out: a frozen contract changed without and with its
audited delta, a conditional's gap with tentacles plus a hard edge inside its wave,
the integrator's premise, an enabler without demo plus a release without outcome
check, and a hard edge on a conditional release.

Scored per finding code: precision and recall per split. The run fails on a
mismatch, and on a drop below the floor in tests/evals/metric_baseline.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sentinel.release_split import validate_partition  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "evals" / "partition"
BASELINE = Path(__file__).resolve().parent / "metric_baseline.json"
TOLERANCE = 0.001


def _ratio(n: int, d: int) -> float:
    return round(n / d, 3) if d else 1.0


def run() -> dict:
    cases, tally = [], {}
    for path in sorted(FIXTURES.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        result = validate_partition(data["brief"], data["payload"], set(data.get("open_gaps", [])), data.get("frozen") or {})
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
        "partition_precision": result["overall"]["precision"],
        "partition_recall": result["overall"]["recall"],
        "partition_held_out_f1": result["metrics"].get("held_out", {}).get("f1", 1.0),
    }


def main() -> int:
    result = run()
    for case in result["cases"]:
        detail = "" if case["ok"] else f" got={case['got']} want={case['want']}"
        print(f"  [{'OK ' if case['ok'] else 'FAIL'}] {case['case']:32s} split={case['split']}{detail}")
    current = snapshot(result)
    print("Partition evals (IMP-266): " + " ".join(f"{k}={v:.3f}" for k, v in current.items()))
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
