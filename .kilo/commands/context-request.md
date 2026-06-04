---
description: Generate a domain-specific context request.
agent: sentinel-discovery
---

# Ignite Context Request

Parse `PROJECT_ID` and `--domain` from:

```text
/context-request PROJECT_ID --domain technology
```

Allowed domains: `technology`, `design`, `quality`, `frontend`, `backend`.

Run from the repository root:

```powershell
python -m sentinel /context-request PROJECT_ID --domain DOMAIN
```

Return the generated file under `08_context_packs/requests/`.
