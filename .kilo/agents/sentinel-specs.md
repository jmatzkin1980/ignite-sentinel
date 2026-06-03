---
name: sentinel-specs
description: Generate AI-friendly PRD/specification artifacts from mature requirements.
mode: primary
---

# Sentinel Specs

Run:

```powershell
python -m sentinel /maturity PROJECT_ID
python -m sentinel /specs PROJECT_ID
python -m sentinel /trace PROJECT_ID
```

Rules:

- Do not generate specs while maturity is `BLOCKED`.
- Keep specs implementation-agnostic and useful for Product, Technology, Design, Quality, and Delivery.
- Preserve `REQ -> SPEC` traceability.
