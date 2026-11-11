"""IMP-260: deterministic cross-consistency of the brief v2 (the contract's exit checks).

The rules live in `templates/cross_checks.json`. Each rule reads ids or fact lines
from some places of the brief and checks them against others: a role of 2.1 named
in 4.1/5.11, each error code shown in 4.2 present in 5.15, each business rule with
a step in 3.2, each flag of 6.1 declared in 5.3, build items within scope (9.1 ⊆
6.1, 6.2 ∩ 9.1 = ∅, every 6.1 item built), exclusions with a destination, priority
only in 2.3, assumptions with a use, technical pieces with a build item.

A rule whose source places carry nothing (or are N/A) is SKIP, not PASS: there is
nothing to cross yet. Every result is a non-blocking WARN in `/validate`'s
cross-consistency report, like the other cross-artifact checks.
"""
from __future__ import annotations

import re
from typing import Any

from .brief_model import parse_brief
from .resources import read_package_json

C_ITEM_RE = re.compile(r"^- `(?P<id>C-[0-9]{2,})` (?:(?:Debt|Deuda|Defect|Defecto): )?(?P<text>.+?) \[\[")
FACT_TEXT_RE = re.compile(r"^- (?P<text>.+?)(?: \(`GAP-[A-Z0-9-]+`\))? \[\[")


def rules() -> list[dict[str, Any]]:
    return read_package_json("templates/cross_checks.json")["checks"]


class _Brief:
    def __init__(self, text: str):
        self.model = parse_brief(text)
        self.lines = text.splitlines()

    def body(self, sid: str) -> str:
        """The text of a place and everything nested in it ("5" = the whole section)."""
        spans = [s for key, s in self.model.sections.items() if key == sid or key.startswith(sid + ".")]
        if not spans:
            return ""
        start, end = min(s.start for s in spans), max(s.end for s in spans)
        return "\n".join(self.lines[start:end])

    def is_na(self, sid: str) -> bool:
        body = self.body(sid)
        return bool(body) and "N/A —" in body and "[[" not in body

    def facts(self, sid: str) -> list[str]:
        return [line for line in self.body(sid).splitlines() if line.startswith("- ") and "[[" in line]

    def fact_texts(self, sid: str) -> list[str]:
        found = []
        for line in self.facts(sid):
            match = FACT_TEXT_RE.match(line)
            if match:
                found.append(match.group("text"))
        return found

    def build_items(self) -> list[tuple[str, str]]:
        return [(m.group("id"), m.group("text")) for line in self.body("9.1").splitlines() if (m := C_ITEM_RE.match(line))]


def _ids(pattern: str, text: str) -> list[str]:
    return sorted(set(re.findall(pattern, text)))


def run_cross_checks(text: str) -> list[dict[str, Any]]:
    """One result per rule: {id, status PASS|WARN|SKIP, issues[]}. Empty for a v1 brief."""
    brief = _Brief(text)
    if brief.model.version != 2:
        return []
    results = []
    for rule in rules():
        issues, applicable = _evaluate(brief, rule)
        status = "SKIP" if not applicable else ("WARN" if issues else "PASS")
        results.append({"id": rule["id"], "status": status, "issues": issues})
    return results


def _evaluate(brief: _Brief, rule: dict[str, Any]) -> tuple[list[str], bool]:
    kind, message = rule["kind"], rule["message"]
    if kind == "ids_subset":
        found = _ids(rule["pattern"], "\n".join(brief.body(s) for s in rule["from"]))
        targets = [s for s in rule["to"] if not brief.is_na(s)]
        if not found or not targets:
            return [], False
        target_text = "\n".join(brief.body(s) for s in targets)
        return [message.format(id=i) for i in found if i not in target_text], True
    if kind == "presence_implies_ids":
        found = _ids(rule["pattern"], "\n".join(brief.body(s) for s in rule["from"]))
        if not found:
            return [], False
        ok = re.search(rule["requires"], "\n".join(brief.body(s) for s in rule["in"]))
        return ([] if ok else [message]), True
    if kind == "build_within_scope":
        items, scope = brief.build_items(), brief.fact_texts("6.1")
        if not items:
            return [], False
        return [message.format(id=i) for i, t in items if not any(t in s or s in t for s in scope)], True
    if kind == "scope_has_build_item":
        items, scope = brief.build_items(), brief.fact_texts("6.1")
        if not scope:
            return [], False
        return [message.format(text=s[:80]) for s in scope if not any(t in s or s in t for _, t in items)], True
    if kind == "excluded_not_built":
        items, excluded = brief.build_items(), brief.fact_texts("6.2")
        if not items or not excluded:
            return [], False
        return [message.format(id=i) for i, t in items if any(t in e or e in t for e in excluded)], True
    if kind == "lines_contain_any":
        lines = [line for s in rule["in"] for line in brief.facts(s)]
        if not lines:
            return [], False
        def marked(line: str) -> bool:  # an uppercase marker is the brief's own vocabulary: match it exactly
            return any((m in line) if m != m.lower() else (m in line.lower()) for m in rule["markers"])

        return [message.format(text=FACT_TEXT_RE.match(line).group("text")[:80] if FACT_TEXT_RE.match(line) else line[:80])
                for line in lines if not marked(line)], True
    if kind == "words_outside":
        hits = []
        for sid in sorted({k for k in brief.model.sections if "." in k and not k.startswith("0.")}):
            if any(sid == a or sid.startswith(a + ".") for a in rule["allowed"]):
                continue
            section = brief.model.sections[sid]
            own = "\n".join(line for line in brief.lines[section.start + 1:section.end] if line.startswith("- "))
            if re.search(rule["pattern"], own, re.I):
                hits.append(message.format(place=sid))
        return hits, True
    if kind == "ids_used":
        found = _ids(rule["pattern"], "\n".join(brief.body(s) for s in rule["from"]))
        if not found:
            return [], False
        def related(sid: str) -> bool:  # the source place, its parents and its children
            return any(sid == f or f.startswith(sid + ".") or sid.startswith(f + ".") for f in rule["from"])

        leaves = [sid for sid in brief.model.sections if ("." in sid or sid.startswith("A.")) and not related(sid)
                  and sid != "A.provenance"]
        elsewhere = "\n".join(brief.body(sid) for sid in leaves)
        return [message.format(id=i) for i in found if i not in elsewhere], True
    if kind == "facts_imply_items":
        if not any(brief.facts(s) for s in rule["from"]):
            return [], False
        return ([] if brief.build_items() else [message]), True
    if kind == "facts_imply_words":
        if not any(brief.facts(s) for s in rule["from"]):
            return [], False
        build = brief.body("9.1").lower()
        return ([] if any(w in build for w in rule["words"]) else [message]), True
    raise ValueError(f"unknown cross-check kind {kind!r}")
