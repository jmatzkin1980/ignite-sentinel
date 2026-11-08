# Context Broker

Ignite Sentinel uses retrieval to reduce prompt context, not to replace source artifacts.

## Retrieval Contract

- Query by workflow intent and project ID.
- Filter by artifact type, domain, and trace IDs when possible.
- Return a small context pack containing source path, artifact ID, score, summary, and chunk text.
- If memory and source files disagree, source files win.

## CLI

```bash
python "${CLAUDE_PLUGIN_ROOT}/launcher.py" /retrieve PROJECT_ID --query "scope and acceptance criteria" --workflow maturity
```
