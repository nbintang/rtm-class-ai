# rtm-class-ai

Standalone FastAPI service for asynchronous material generation (MCQ, essay, summary) from uploaded files.

## Functionality overview

This service receives uploaded learning material (`.pdf`, `.pptx`, `.txt`), processes it asynchronously, and returns generated output through callback webhooks.

Core capabilities:
- Material generation endpoints:
  - `POST /api/mcq`
  - `POST /api/essay`
  - `POST /api/summary`
  - `POST /api/material` (multi-type legacy endpoint)
- OAuth client-credentials token issuance:
  - `POST /api/oauth/token`
- Background processing with Redis queue + callback delivery retries.

## Processing flow

1. Client sends multipart form request with file upload.
2. API validates request and enqueues job in Redis.
3. Worker dequeues job and extracts text (`pdf` / `pptx` / `txt`).
4. Runtime builds RAG context for that upload only (`user_id + document_id` filter).
5. Model generates strict JSON output (with one repair retry if needed).
6. Worker sends callback payload (or skips callback if material job has no `callback_url`).

## API endpoints

### `GET /`
- Health check.
- Response message: `API is running.`

### `POST /api/oauth/token`
- Public endpoint.
- Enabled only when `OAUTH_ENABLED=true`.
- If OAuth is disabled, endpoint returns `404`.

`application/x-www-form-urlencoded` fields:
- `grant_type` (required): must be `client_credentials`
- `client_id` (required)
- `client_secret` (required)
- `scope` (optional): space-separated scopes, defaults to `OAUTH_DEFAULT_SCOPES`

Rate-limited by:
- IP (`OAUTH_TOKEN_RATE_LIMIT_PER_IP`)
- client ID (`OAUTH_TOKEN_RATE_LIMIT_PER_CLIENT`)
- window (`OAUTH_TOKEN_RATE_LIMIT_WINDOW_SECONDS`)

### Material generation endpoints

Applies to:
- `POST /api/material`
- `POST /api/mcq`
- `POST /api/essay`
- `POST /api/summary`

Common multipart fields:
- `user_id` (required, non-empty)
- `job_id` (required, non-empty)
- `material_id` (required, non-empty)
- `requested_by_id` (required, non-empty)
- `file` (required, one file: `.pdf`, `.pptx`, `.txt`)
- `callback_url` (optional, must be valid `http/https` if provided)
- `mcp_enabled` (optional, default `true`)

Important behavior:
- For material jobs, the returned/stored job ID is your submitted `job_id`.
- `job_id` should be unique per request to avoid overwriting previous Redis job records.
- If `callback_url` is omitted, processing still runs and callback delivery is skipped.

Additional per-endpoint fields:
- `POST /api/mcq`:
  - `mcq_count` (optional, default `DEFAULT_MCQ_COUNT`, range `1..20`)
- `POST /api/essay`:
  - `essay_count` (optional, default `DEFAULT_ESSAY_COUNT`, range `1..10`)
- `POST /api/summary`:
  - `summary_max_words` (optional, default `DEFAULT_SUMMARY_MAX_WORDS`, range `80..400`)
- `POST /api/material`:
  - `generate_types` (required, repeatable, unique values from `mcq|essay|summary`)
  - `mcq_count` (optional, range `1..20`)
  - `essay_count` (optional, range `1..10`)
  - `summary_max_words` (optional, range `80..400`)

All endpoints return `202 Accepted` on enqueue success.

## API response envelope

All documented JSON responses use:

Success:
```json
{
  "success": true,
  "data": {},
  "message": "Optional message",
  "meta": {
    "request_id": "req-..."
  }
}
```

Error:
```json
{
  "success": false,
  "error": {
    "code": "machine_readable_code",
    "message": "Human readable message",
    "details": null
  },
  "meta": {
    "request_id": "req-..."
  }
}
```

Common error codes:
- `invalid_request` (`400`)
- `unauthorized` (`401`)
- `forbidden` (`403`)
- `not_found` (`404`)
- `payload_too_large` (`413`)
- `too_many_requests` (`429`)
- `validation_error` (`422`)
- `internal_error` (`500`)
- `service_unavailable` (`503`)

## Callback contract

Event types:
- `material.generated`

Callback status values:
- `succeeded`
- `failed_processing`

Delivery behavior:
- Method: `POST` JSON to `callback_url`
- Total attempts: `1 + WEBHOOK_CALLBACK_MAX_RETRIES`
- Backoff: `WEBHOOK_CALLBACK_BACKOFF_SECONDS` (+ small jitter)
- Retryable: network/request errors and HTTP `408`, `425`, `429`, `5xx`
- Non-retryable: other HTTP statuses (for example `400`) stop immediately

If callback delivery ultimately fails:
- Internal job status becomes `failed_delivery`.

If material `callback_url` is empty:
- Callback is skipped intentionally.
- Worker still marks job processing outcome in Redis.

### Material callback success shape
```json
{
  "event": "material.generated",
  "job_id": "job-...",
  "status": "succeeded",
  "user_id": "user-1",
  "result": {
    "user_id": "user-1",
    "document_id": "doc-...",
    "material": {
      "filename": "materi.pdf",
      "file_type": "pdf",
      "extracted_chars": 12345
    },
    "mcq_quiz": {"questions": []},
    "essay_quiz": {"questions": []},
    "summary": {
      "title": "...",
      "overview": "...",
      "key_points": []
    },
    "sources": [],
    "tool_calls": [],
    "warnings": []
  },
  "attempt": 1,
  "finished_at": "2026-03-02T00:00:00Z"
}
```

Internal Redis job statuses:
- `accepted`
- `processing`
- `succeeded`
- `failed_processing`
- `failed_delivery`

## Authentication and authorization

JWT behavior:
- `JWT_ENABLED=true`: `/api/*` routes require `Authorization: Bearer <token>`.
- `JWT_ENABLED=false`: JWT checks are bypassed.

OAuth behavior:
- `OAUTH_ENABLED=true`: token issuance via `POST /api/oauth/token`.
- `OAUTH_ENABLED=false`: token endpoint returns `404`.

Token requirements (when JWT enabled):
- Signed with `HS256` using `JWT_SECRET`
- Claims required: `iss`, `aud`, `sub`, `iat`, `exp`
- `sub` must start with `client:`
- Optional denylist revocation check via Redis (`JWT_DENYLIST_ENABLED=true`)

Default scopes:
- `/api/material`, `/api/mcq`, `/api/essay`, `/api/summary` -> `material:write`

## Generation behavior details

- Output language target: Bahasa Indonesia (prompts enforce this).
- Material extraction supports `.pdf`, `.pptx`, `.txt`.
- Maximum upload size controlled by `MATERIAL_MAX_FILE_MB`.
- RAG indexes each upload into chunks and retrieves with strict `user_id + document_id` filter.
- If vector store/indexing fails, runtime falls back to extracted text and returns warnings.
- Model output parsing is lenient for common malformed JSON (smart quotes, trailing commas, quoted code fences).
- If first parse fails, runtime performs one repair retry; if still invalid, job fails processing.
- Contract enforcement trims extra questions/activities and records warnings when output diverges from requested counts.

MCP behavior:
- Controlled by request field `mcp_enabled` (material endpoints only).
- Server config from `MCP_SERVERS_JSON`.
- Only MCP server entries with `transport="streamable_http"` are accepted.
- Insert calls are planned per requested type (`insert_mcq`, `insert_essay`, `insert_summary`).
- Each MCP insert payload includes `job_id`, `material_id`, and `requested_by_id`.

## Environment variables

See `.env.example` for full list. Key groups:

Runtime/model:
- `GROQ_API_KEY`
- `GROQ_MODEL`
- `GROQ_TEMPERATURE`
- `GROQ_TIMEOUT_SECONDS`
- `AGENT_MAX_ITERATIONS`

Storage/queue:
- `REDIS_URL`
- `JOB_QUEUE_KEY`
- `JOB_TTL_SECONDS`
- `CHROMA_PERSIST_DIR`

RAG:
- `RAG_COLLECTION_NAME`
- `RAG_CHUNK_SIZE`
- `RAG_CHUNK_OVERLAP`
- `RAG_TOP_K`
- `RAG_FETCH_K`
- `RAG_MMR_LAMBDA`

Webhook callback:
- `WEBHOOK_CALLBACK_TIMEOUT_SECONDS`
- `WEBHOOK_CALLBACK_MAX_RETRIES`
- `WEBHOOK_CALLBACK_BACKOFF_SECONDS`

Auth:
- `JWT_ENABLED`
- `JWT_SECRET`
- `JWT_ISSUER`
- `JWT_AUDIENCE`
- `JWT_REQUIRED_SCOPES`
- `OAUTH_ENABLED`
- `OAUTH_CLIENT_ID`
- `OAUTH_CLIENT_SECRET`
- `OAUTH_ALLOWED_SCOPES`
- `OAUTH_DEFAULT_SCOPES`

CORS:
- `CORS_ENABLED`
- `CORS_ALLOW_ORIGINS`
- `CORS_ALLOW_METHODS`
- `CORS_ALLOW_HEADERS`
- `CORS_ALLOW_CREDENTIALS`

## Local run (minimal)

Requirements:
- Python 3.11+
- Redis server
- `.env` configured

Install:
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -e .
cp .env.example .env
```

Run API:
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Or use helper launcher (`127.0.0.1:7860`):
```bash
python cmd/run.py
```

## Current limitations

- No public endpoint for polling job status.
- Final client delivery is callback-based.
- Callback signature/authentication is not implemented.
