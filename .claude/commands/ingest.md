---
description: Ingest raw client, domain, or interaction evidence into an Ignite workspace.
argument-hint: PROJECT_ID --source PATH [--replace] [--change]
---

# Ignite Ingest

Arguments received from the user invocation: `$ARGUMENTS`

Parse the project ID and source path from the invocation:

```text
/ingest PROJECT_ID --source PATH
/ingest PROJECT_ID --source PATH --change
```

Run from the repository root:

```powershell
python -m sentinel /ingest PROJECT_ID --source PATH
```

This also indexes generated artifacts plus workspace context folders into local LanceDB memory.

Then summarize generated `RAW`, `REQ`, `GAP`, `DEC`, `SEED`, `DISC`, and lens review IDs. Mention that `01_discovery/lens_review.md` contains the Product, Technology, Design, and Quality scrutiny, and that focused context can be retrieved with:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "topic" --workflow discovery --write-pack
```

With `--change` (IMP-382) the source is a change or new feature on an existing system. Sentinel opens a CHG-nnn with only the scope round (GAP-OBJECTIVE, GAP-USERS, GAP-SCOPE, GAP-PRODUCT-ASIS-TOBE) in `01_discovery/CHG-nnn/gaps.md`; the project's requirement and gaps are not touched. The change's brief, specs and backlog are not generated yet.
