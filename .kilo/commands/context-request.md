---
description: Generate a domain-specific context request, or move a CTX-NNN along its lifecycle.
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

Each request is a `CTX-NNN` with a lifecycle: `active` -> `answered` -> `closed`, or `obsolete`. `/sync` marks an active request `answered` when the synced change cites its id. Move it yourself with:

```powershell
python -m sentinel /context-request PROJECT_ID --id CTX-001 --status closed --reason TEXT
```

`closed` and `obsolete` need `--reason` and are final; an answered request can go back to `active` when the answer falls short. Regenerating a request for the same domain reopens it.
