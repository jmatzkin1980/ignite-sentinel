"""IMP-258b: anchor-review evals with seeded defects.

Each fixture in tests/fixtures/evals/anchor_review/ is a synthetic brief v2, the
text of its sources, an agent review payload and the expected verdict per review
(accept, reject, holds). Seeded: anchors that say less or the opposite, an
adversarial refutation of a "holds", quotes that are not verbatim at either end,
incomplete findings, unknown sources or places, and a held-out split.

Precision and recall of "accept" are scored per split; the run fails on a
mismatch and on a drop below the floor in tests/evals/metric_baseline.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sentinel.anchor_review import validate_reviews  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "evals" / "anchor_review"
BASELINE = Path(__file__).resolve().parent / "metric_baseline.json"
TOLERANCE = 0.001


def _verdicts(result: dict, reviews: list[dict]) -> list[str]:
    rejected = {int(r["index"]) for r in result["rejected"]}
    accepted = len(result["accepted"])
    out, seen_accept = [], 0
    for index, item in enumerate(reviews, start=1):
        if index in rejected:
            out.append("reject")
            continue
        refuted = isinstance(item.get("adversarial"), dict) and item["adversarial"].get("refuted")
        if str(item.get("verdict", "")).lower() == "holds" and not refuted:
            out.append("holds")
        else:
            out.append("accept")
            seen_accept += 1
    assert seen_accept == accepted, "accepted count drifted from the per-review verdicts"
    return out


def _ratio(n: int, d: int) -> float:
    return round(n / d, 3) if d else 1.0


def run() -> dict:
    cases, tally = [], {}
    for path in sorted(FIXTURES.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        reviews = data["payload"]["anchors"]
        got = _verdicts(validate_reviews(data["brief"], data["sources"], data["payload"]), reviews)
        want = data["expected"]
        t = tally.setdefault(data["split"], {"tp": 0, "fp": 0, "fn": 0})
        for g, w in zip(got, want):
            t["tp"] += g == "accept" and w == "accept"
            t["fp"] += g == "accept" and w != "accept"
            t["fn"] += g != "accept" and w == "accept"
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
        "anchor_review_precision": result["overall"]["precision"],
        "anchor_review_recall": result["overall"]["recall"],
        "anchor_review_held_out_f1": result["metrics"].get("held_out", {}).get("f1", 1.0),
    }


def main() -> int:
    result = run()
    for case in result["cases"]:
        detail = "" if case["ok"] else f" got={case['got']} want={case['want']}"
        print(f"  [{'OK ' if case['ok'] else 'FAIL'}] {case['case']:30s} split={case['split']}{detail}")
    current = snapshot(result)
    print("Anchor review evals (IMP-258b): " + " ".join(f"{k}={v:.3f}" for k, v in current.items()))
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
