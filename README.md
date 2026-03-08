# RTM Class AI

Standalone FastAPI service for asynchronous material generation (MCQ, essay, summary) from uploaded files.

## Overview

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

## Stack

- Python 3.11+
- FastAPI + Uvicorn
- Pydantic v2
- LangChain + LangGraph
- Groq (`langchain-groq`)
- MCP adapters (`langchain-mcp-adapters`)
- ChromaDB (`chromadb`, `langchain-chroma`)
- Redis queue + retry-based callback delivery
- JWT + OAuth client credentials flow
- ReportLab (LKPD PDF generation)

## Prerequisites

- Python 3.11+
- Redis server
- Groq API key (`GROQ_API_KEY`)
- `.env` configuration based on `.env.example`

Optional:
- Docker + Docker Compose

## Quick Start

1. Create and activate virtual environment.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```

2. Install dependencies.

```bash
pip install -e .
```

3. Create environment file.

```bash
cp .env.example .env
```

PowerShell:

```powershell
Copy-Item .env.example .env
```

4. Ensure Redis is running and update `.env` values.

5. Start API.

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Alternative launcher:

```bash
python cmd/run.py
```

Server listens on `http://localhost:8000` by default.

## Run Commands

```bash
# local API (reload)
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# helper launcher
python cmd/run.py

# docker compose via taskipy
python -m taskipy up
python -m taskipy upd
python -m taskipy down
python -m taskipy logs
python -m taskipy ps
```

## Processing Flow

1. Client sends multipart form request with file upload.
2. API validates request and enqueues job in Redis.
3. Worker dequeues job and extracts text (`pdf` / `pptx` / `txt`).
4. Runtime builds RAG context for that upload only (`user_id + document_id` filter).
5. Model generates strict JSON output (with one repair retry if needed).
6. Worker sends callback payload (or skips callback if material job has no `callback_url`).

## API Endpoints

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

## API Response Envelope

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

## Callback Contract

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

## Authentication and Authorization

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

## Generation Behavior Details

- Output language target: Bahasa Indonesia (prompts enforce this).
- Material extraction supports `.pdf`, `.pptx`, `.txt`.
- Maximum upload size controlled by `MATERIAL_MAX_FILE_MB`.
- RAG indexes each upload into chunks and retrieves with strict `user_id + document_id` filter.
- If vector store/indexing fails, runtime falls back to extracted text and returns warnings.
- Model output parsing is lenient for common malformed JSON (smart quotes, trailing commas, quoted code fences).
- If first parse fails, runtime performs one repair retry; if still invalid, job fails processing.
- Contract enforcement trims extra questions/activities and records warnings when output diverges from requested counts.

## MCP Behavior

- Controlled by request field `mcp_enabled` (material endpoints only).
- Server config from `MCP_SERVERS_JSON`.
- Only MCP server entries with `transport="streamable_http"` are accepted.
- Insert calls are planned per requested type (`insert_mcq`, `insert_essay`, `insert_summary`).
- Each MCP insert payload includes `job_id`, `material_id`, and `requested_by_id`.

## Environment Variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `CHROMA_PERSIST_DIR` | No | `.chroma` | Local persistence directory for Chroma vector store. |
| `GROQ_API_KEY` | Yes | - | API key for Groq model access. |
| `GROQ_MODEL` | No | `llama-3.1-8b-instant` | Model name used for generation. |
| `GROQ_TEMPERATURE` | No | `0.2` | Sampling temperature for generation. |
| `GROQ_TIMEOUT_SECONDS` | No | `30` | Timeout for Groq API calls. |
| `MCP_SERVERS_JSON` | No | `{}` | JSON object of configured MCP servers. |
| `AGENT_MAX_ITERATIONS` | No | `5` | Max internal agent/tool loop iterations. |
| `AGENT_MEMORY_COLLECTION` | No | `agent_memory` | Memory collection name for agent memory storage. |
| `RAG_COLLECTION_NAME` | No | `material_chunks` | Chroma collection name for material chunks. |
| `RAG_CHUNK_SIZE` | No | `1000` | Chunk size for document splitting. |
| `RAG_CHUNK_OVERLAP` | No | `150` | Chunk overlap for document splitting. |
| `RAG_TOP_K` | No | `8` | Number of retrieved chunks returned to prompt context. |
| `RAG_FETCH_K` | No | `24` | Candidate chunks fetched before MMR selection. |
| `RAG_MMR_LAMBDA` | No | `0.5` | MMR diversity/relevance balancing factor. |
| `MATERIAL_MAX_FILE_MB` | No | `15` | Maximum accepted upload size in MB. |
| `DEFAULT_MCQ_COUNT` | No | `10` | Default MCQ question count. |
| `DEFAULT_ESSAY_COUNT` | No | `3` | Default essay question count. |
| `DEFAULT_SUMMARY_MAX_WORDS` | No | `200` | Default max words for summary output. |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Redis connection URL for queue and shared state. |
| `WEBHOOK_CALLBACK_TIMEOUT_SECONDS` | No | `10` | Callback request timeout per attempt. |
| `WEBHOOK_CALLBACK_MAX_RETRIES` | No | `3` | Max callback retries after first attempt. |
| `WEBHOOK_CALLBACK_BACKOFF_SECONDS` | No | `5,15,45` | Backoff schedule between callback retries (seconds). |
| `JOB_TTL_SECONDS` | No | `86400` | TTL for stored job state in Redis. |
| `JOB_QUEUE_KEY` | No | `material_jobs:queue` | Redis list key used for material job queue. |
| `LKPD_DEFAULT_ACTIVITY_COUNT` | No | `5` | Default LKPD activity count. |
| `LKPD_MIN_ACTIVITY_COUNT` | No | `1` | Minimum LKPD activity count. |
| `LKPD_MAX_ACTIVITY_COUNT` | No | `15` | Maximum LKPD activity count. |
| `LKPD_JOB_QUEUE_KEY` | No | `lkpd_jobs:queue` | Redis list key used for LKPD job queue. |
| `LKPD_PDF_DIR` | No | `.generated/lkpd` | Output directory for generated LKPD PDFs. |
| `LKPD_PDF_TTL_SECONDS` | No | `86400` | TTL for generated LKPD PDF artifacts. |
| `LKPD_HEADER_LOGO_PATH` | No | `.assets/lkpd/logo.png` | Logo file path used in LKPD PDF header. |
| `LKPD_HEADER_ACCENT_HEX` | No | `#1F4E79` | Accent color used in LKPD PDF header. |
| `LKPD_HEADER_TITLE_LINE1` | No | `LEMBAR KERJA PESERTA DIDIK (LKPD)` | LKPD PDF header title line 1. |
| `LKPD_HEADER_TITLE_LINE2` | No | `SMARTER AI` | LKPD PDF header title line 2. |
| `LKPD_HEADER_TITLE_LINE3` | No | empty | LKPD PDF header title line 3. |
| `APP_PUBLIC_BASE_URL` | No | `http://localhost:8000` | Public base URL for generated file links. |
| `JWT_ENABLED` | No | `true` | Enables JWT protection on `/api/*` routes. |
| `JWT_SECRET` | Yes when `JWT_ENABLED=true` | `replace-with-at-least-32-characters` | Shared secret for HS256 token verification/signing. |
| `JWT_ISSUER` | No | `my-backend` | Expected JWT issuer (`iss`). |
| `JWT_AUDIENCE` | No | `rtm-class-ai` | Expected JWT audience (`aud`). |
| `JWT_CLOCK_SKEW_SECONDS` | No | `30` | Allowed JWT clock skew in seconds. |
| `JWT_REQUIRED_SCOPES` | No | JSON mapping in `.env.example` | Route-to-scope mapping used for authorization checks. |
| `JWT_DENYLIST_ENABLED` | No | `true` | Enables denylist check for revoked JWT `jti`. |
| `JWT_DENYLIST_PREFIX` | No | `auth:denylist:jti:` | Redis key prefix for JWT denylist entries. |
| `OAUTH_ENABLED` | No | `true` | Enables `POST /api/oauth/token` endpoint. |
| `OAUTH_CLIENT_ID` | Yes when `OAUTH_ENABLED=true` | `rtm-client` | Client ID for OAuth client-credentials flow. |
| `OAUTH_CLIENT_SECRET` | Yes when `OAUTH_ENABLED=true` | `replace-with-strong-client-secret` | Client secret for OAuth client-credentials flow. |
| `OAUTH_ALLOWED_SCOPES` | No | `material:write lkpd:write lkpd:read` | Space-separated scopes clients can request. |
| `OAUTH_DEFAULT_SCOPES` | No | `material:write lkpd:write lkpd:read` | Scopes used when no `scope` is requested. |
| `OAUTH_TOKEN_TTL_SECONDS` | No | `300` | Access-token lifetime in seconds. |
| `OAUTH_TOKEN_RATE_LIMIT_WINDOW_SECONDS` | No | `60` | Rate-limit window for token endpoint. |
| `OAUTH_TOKEN_RATE_LIMIT_PER_IP` | No | `30` | Max token requests per IP per window. |
| `OAUTH_TOKEN_RATE_LIMIT_PER_CLIENT` | No | `30` | Max token requests per client per window. |
| `CORS_ENABLED` | No | `true` | Enables/disables CORS middleware. |
| `CORS_ALLOW_ORIGINS` | No | `*` | Allowed CORS origins. |
| `CORS_ALLOW_METHODS` | No | `*` | Allowed CORS methods. |
| `CORS_ALLOW_HEADERS` | No | `*` | Allowed CORS headers. |
| `CORS_ALLOW_CREDENTIALS` | No | `false` | Whether credentials are allowed in CORS. |

## Current Limitations

- No public endpoint for polling job status.
- Final client delivery is callback-based.
- Callback signature/authentication is not implemented.
