"""IMP-258: anchor evals with seeded defects.

Each fixture in tests/fixtures/evals/anchors/ is a synthetic brief v2 with its
source registry and the anchor findings it must produce (code, place). Fixtures
mix seeded defects, correct symmetries that must not be flagged (two facts each
with its own anchor), distractors (exempt places and line kinds) and a held-out
split never used to tune the rules.

Precision, recall and F1 are computed over (code, place) pairs, per split. The run
fails on a missed or extra finding, and when a metric drops below the floor in
tests/evals/metric_baseline.json (doc 53 gate: no regression).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sentinel.anchors import anchor_report  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "evals" / "anchors"
BASELINE = Path(__file__).resolve().parent / "metric_baseline.json"
TOLERANCE = 0.001


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 3) if denominator else 1.0


def run() -> dict:
    per_split: dict[str, Counter] = {}
    cases = []
    for path in sorted(FIXTURES.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        got = Counter((f["code"], f["place"]) for f in anchor_report(data["brief"], data["registry"])["findings"])
        want = Counter(tuple(item) for item in data["expected"])
        tp, fp, fn = sum((got & want).values()), sum((got - want).values()), sum((want - got).values())
        counts = per_split.setdefault(data["split"], Counter())
        counts.update(tp=tp, fp=fp, fn=fn)
        cases.append({"case": data["case"], "split": data["split"], "ok": fp == 0 and fn == 0,
                      "extra": sorted(got - want), "missed": sorted(want - got)})
    metrics = {}
    for split, c in per_split.items():
        precision = _ratio(c["tp"], c["tp"] + c["fp"])
        recall = _ratio(c["tp"], c["tp"] + c["fn"])
        f1 = round(2 * precision * recall / (precision + recall), 3) if precision + recall else 0.0
        metrics[split] = {"precision": precision, "recall": recall, "f1": f1}
    total = sum(per_split.values(), Counter())
    overall = {"precision": _ratio(total["tp"], total["tp"] + total["fp"]), "recall": _ratio(total["tp"], total["tp"] + total["fn"])}
    return {"cases": cases, "metrics": metrics, "overall": overall}


def snapshot(result: dict) -> dict[str, float]:
    return {
        "anchor_precision": result["overall"]["precision"],
        "anchor_recall": result["overall"]["recall"],
        "anchor_held_out_f1": result["metrics"].get("held_out", {}).get("f1", 1.0),
    }


def main() -> int:
    result = run()
    for case in result["cases"]:
        print(f"  [{'OK ' if case['ok'] else 'FAIL'}] {case['case']:28s} split={case['split']}"
              + (f" extra={case['extra']}" if case["extra"] else "") + (f" missed={case['missed']}" if case["missed"] else ""))
    current = snapshot(result)
    print("Anchor evals (IMP-258): " + " ".join(f"{k}={v:.3f}" for k, v in current.items()))
    data = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {"floor": {}}
    if "--update-metric-baseline" in sys.argv:
        data.setdefault("floor", {}).update(current)
        BASELINE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    floor = data.get("floor", {})
    regressions = [f"{k} {current[k]:.3f} < floor {float(v):.3f}" for k, v in sorted(floor.items())
                   if k in current and current[k] + TOLERANCE < float(v)]
    for line in regressions:
        print(f"  [FAIL] metric regression: {line}")
    return 0 if all(case["ok"] for case in result["cases"]) and not regressions else 1


if __name__ == "__main__":
    sys.exit(main())
