# Synthetic diagram sections (IMP-273)

**Synthetic fixture: invented for the tests, it describes no real client or system.**

`sections.json` replaces the pending bodies of §3.3, §3.4, §5.1 and §5.6 of the v2 brief golden
(`tests/fixtures/golden/brief_v2/en/project-brief.md`) with structured lines. `tests/test_diagrams.py`
compiles them into Mermaid and compares against `tests/fixtures/golden/diagrams/*.mmd`.
