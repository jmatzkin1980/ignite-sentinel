---
description: Generate or refresh the mature Ignite Sentinel project brief.
argument-hint: PROJECT_ID [--profile UI,API,BAT,INT,MIG,REG,MT] [--genesis greenfield|brownfield-integration|brownfield-extension|brownfield-replacement] [--validation-direction to-build|built] [--brief-version 1|2]
---

# Ignite Brief

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` from:

```text
/brief PROJECT_ID
```

Run from the repository root:

```powershell
python -m sentinel /brief PROJECT_ID
```

Return the `02_requirements/project-brief.md` path.

The output carries `brief_settings`: the project profile(s), genesis and validation direction the brief v2 is built for. While they are unconfirmed it shows a `proposal` from the raw input; never apply it silently. Ask the BA and record the answer:

```powershell
python -m sentinel /brief PROJECT_ID --profile UI,REG --genesis brownfield-extension
```

`MIG` implies `brownfield-replacement`; declaring it with another genesis is reported as a contradiction. With a mixed genesis, pass both and the most demanding one is declared.

`--brief-version 2` opts the project into the brief v2 (§0–§9, every fact cited, every gap a `⏳` mark, N/A with its counterfactual). It compiles only with a confirmed profile and genesis; until then `GAP-BRIEF-PROFILE` opens and the v1 brief stays. Report `02_requirements/brief_compile_report.json`: its `fill_sites` are what is left to fill and `unused_sources` what the brief never cites. `--brief-version 1` goes back. In a v2 project `/resolve-gaps` rewrites the answered places in place (`brief_v2.rewritten_places`); report them, never hand-edit the v2 body.
