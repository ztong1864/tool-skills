---
name: labkag-skill
description: "API wrapper skill for LabKAG. Use when an agent needs to call the LabKAG HTTP API through the bundled CLI script for health checks, upload, extraction, ingestion, literature query, evidence search, or knowledge inspection."
---

# LabKAG API Wrapper

Use this skill when you need to call LabKAG as an external service.
Do not modify the LabKAG repository.

## Call Pattern

Prefer the bundled script:

```text
py -3.10 labkag-skill/scripts/labkag_api.py <command> [args]
```

Default base URL:

```text
http://127.0.0.1:8001
```

Override with `--base-url` or `LABKAG_BASE_URL`.

## Commands

- `health`
- `upload --file <pdf>`
- `extract --file-id <id> [--project-id <id>] [--extract-level basic|detailed] [--return-chunks]`
- `ingest --paper-extraction <json-file> [--project-id <id>] [--confirm]`
- `query --question <text> [--project-id <id>] [--paper-id <id>] [--top-k N]`
- `search --query <text> [--project-id <id>] [--paper-id <id>] [--top-k N]`
- `knowledge --paper-id <id> [--project-id <id>] [--include-evidence / --no-include-evidence]`

## Minimal Rules

- Call `health` before other actions when the service state is unknown.
- Use `upload -> extract -> ingest -> query/search/knowledge` for the literature pipeline.
- Treat non-2xx responses as service failures and inspect the returned JSON body.
- `extract` requires the configured LLM provider.
- `ingest` writes to Neo4j only when `--confirm` is set.
- `search` and `query` should prefer embedding when the service is configured for it.

## Output Handling

- Print or return the raw JSON response when possible.
- If the API returns a structured error body, surface the `status`, first error `code`, and message.
- Do not infer success from HTTP status alone; inspect the JSON payload.
