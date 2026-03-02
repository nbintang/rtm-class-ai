# rtm-class-ai

Standalone FastAPI microservice for async material generation and LKPD generation from uploaded files.

## What this service does
- Accepts file uploads for:
  - `POST /api/material` (generate `mcq`, `essay`, `summary`)
  - `POST /api/lkpd` (generate LKPD + downloadable PDF)
- Immediately returns `202 Accepted` with `job_id`
- Processes jobs in background worker (Redis queue)
- Delivers final result to `callback_url` via HTTP POST

## Current architecture flow
1. Client submits multipart form request.
2. API validates request and stores job in Redis.
3. Worker pulls queue, extracts text (`.pdf`, `.pptx`, `.txt`), indexes RAG, calls model.
4. Worker sends callback payload (retry with backoff if callback fails).
5. LKPD flow also renders a PDF and exposes a temporary download URL.

## Tech stack
- Python 3.11
- FastAPI + Uvicorn
- Redis (async queue + job metadata)
- LangChain + LangGraph
- Groq (`langchain-groq`)
- Chroma (`langchain-chroma`)
- ReportLab (LKPD PDF rendering)

## Requirements
- Python `>=3.11`
- Redis server
- `GROQ_API_KEY` set in `.env`

## Local setup
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -e .
cp .env.example .env
```

## Run locally
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Alternative launcher:
```bash
python cmd/run.py
```

## Run with Docker Compose
1. Fill `.env` (minimum: `GROQ_API_KEY`).
2. Start services:
```bash
docker compose up --build
```

Service endpoints:
- API: `http://localhost:8000`
- Redis: `localhost:6379`

Stop:
```bash
docker compose down
```

Task shortcuts (taskipy):
```bash
uv run task up
uv run task upd
uv run task down
uv run task logs
uv run task ps
```

## HTTP API

### `POST /api/material`
Multipart form fields:
- `user_id` (required, non-empty)
- `file` (required, one file: `.pdf`, `.pptx`, `.txt`)
- `callback_url` (required, valid `http/https`)
- `generate_types` (required, repeatable: `mcq`, `essay`, `summary`; unique; min 1)
- `mcq_count` (optional, default `10`, range `1..20`)
- `essay_count` (optional, default `3`, range `1..10`)
- `summary_max_words` (optional, default `200`, range `80..400`)
- `mcp_enabled` (optional, default `true`)

Response (`202`):
```json
{
  "job_id": "job-...",
  "status": "accepted",
  "message": "Material queued for async processing."
}
```

### `POST /api/lkpd`
Multipart form fields:
- `user_id` (required, non-empty)
- `file` (required, one file: `.pdf`, `.pptx`, `.txt`)
- `callback_url` (required, valid `http/https`)
- `activity_count` (optional, default `5`, constrained by env min/max)

Response (`202`):
```json
{
  "job_id": "job-...",
  "status": "accepted",
  "message": "LKPD queued for async processing."
}
```

### `GET /api/lkpd/files/{file_id}`
- Returns generated LKPD PDF (`application/pdf`)
- Returns `404` if file is missing or expired

## Callback contract

### Delivery behavior
- Callback target: your submitted `callback_url`
- Method: `POST` JSON
- Attempts: `1 + WEBHOOK_CALLBACK_MAX_RETRIES`
  - Default = `4` total attempts (`1 initial + 3 retries`)
- Backoff: `WEBHOOK_CALLBACK_BACKOFF_SECONDS` (default `5,15,45`) with small jitter

### Material event: `material.generated`
`status` values in callback payload:
- `succeeded`
- `failed_processing`

Success example:
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

Failed processing example:
```json
{
  "event": "material.generated",
  "job_id": "job-...",
  "status": "failed_processing",
  "user_id": "user-1",
  "error": {
    "code": "material_validation_error",
    "message": "Unsupported file type. Allowed extensions: .pdf, .pptx, .txt"
  },
  "attempt": 1,
  "finished_at": "2026-03-02T00:00:00Z"
}
```

### LKPD event: `lkpd.generated`
`status` values in callback payload:
- `succeeded`
- `failed_processing`

Success example:
```json
{
  "event": "lkpd.generated",
  "job_id": "job-...",
  "status": "succeeded",
  "user_id": "user-1",
  "result": {
    "document_id": "doc-...",
    "material": {
      "filename": "materi.pdf",
      "file_type": "pdf",
      "extracted_chars": 12345
    },
    "lkpd": {
      "title": "...",
      "learning_objectives": ["..."],
      "instructions": ["..."],
      "activities": [
        {
          "activity_no": 1,
          "task": "...",
          "expected_output": "...",
          "assessment_hint": "..."
        }
      ],
      "worksheet_template": "...",
      "assessment_rubric": [
        {
          "aspect": "...",
          "criteria": "...",
          "score_range": "1-4"
        }
      ]
    },
    "pdf_url": "http://localhost:8000/api/lkpd/files/lkpd-...",
    "pdf_expires_at": "2026-03-03T00:00:00Z",
    "sources": [],
    "warnings": []
  },
  "attempt": 1,
  "finished_at": "2026-03-02T00:00:00Z"
}
```

Failed processing example:
```json
{
  "event": "lkpd.generated",
  "job_id": "job-...",
  "status": "failed_processing",
  "user_id": "user-1",
  "error": {
    "code": "lkpd_validation_error",
    "message": "Model failed to produce valid LKPD JSON output after one retry."
  },
  "attempt": 1,
  "finished_at": "2026-03-02T00:00:00Z"
}
```

### Internal job statuses (Redis record)
- `accepted`
- `processing`
- `succeeded`
- `failed_processing`
- `failed_delivery`

## Example curl

Submit material job:
```bash
curl -X POST http://localhost:8000/api/material \
  -F "user_id=user-1" \
  -F "callback_url=https://example.com/hooks/material" \
  -F "generate_types=mcq" \
  -F "generate_types=essay" \
  -F "generate_types=summary" \
  -F "mcq_count=10" \
  -F "essay_count=3" \
  -F "summary_max_words=200" \
  -F "mcp_enabled=true" \
  -F "file=@./materi.pdf"
```

Submit LKPD job:
```bash
curl -X POST http://localhost:8000/api/lkpd \
  -F "user_id=user-1" \
  -F "callback_url=https://example.com/hooks/lkpd" \
  -F "activity_count=5" \
  -F "file=@./materi.pdf"
```

Download LKPD PDF:
```bash
curl -L "http://localhost:8000/api/lkpd/files/lkpd-xxxxxxxx" -o lkpd.pdf
```

## LKPD PDF output behavior
- PDF generated with branded header on every page
- Optional logo from `LKPD_HEADER_LOGO_PATH`
- Header title lines configurable (`LINE1`, `LINE2`, `LINE3`)
- First page includes:
  - `Document ID`
  - Source file info
  - Student identity block (`Nama`, `NIS`, `Kelas`, `Tanggal`)
- Stored in `LKPD_PDF_DIR` and expired using `LKPD_PDF_TTL_SECONDS`

## RAG isolation behavior
- Each upload gets a new `document_id`
- Retrieval filter is strict by `user_id + document_id`
- New uploads are not mixed with previous upload contexts by default

## MCP behavior
- Controlled by request field `mcp_enabled`
- Server config from `MCP_SERVERS_JSON`
- Only `transport="streamable_http"` configs are accepted
- If configured but tools unavailable, processing still continues with warnings

## Environment variables
- `CHROMA_PERSIST_DIR=.chroma`
- `GROQ_API_KEY=`
- `GROQ_MODEL=llama-3.1-8b-instant`
- `GROQ_TEMPERATURE=0.2`
- `GROQ_TIMEOUT_SECONDS=30`
- `MCP_SERVERS_JSON={}`
- `AGENT_MAX_ITERATIONS=5`
- `AGENT_MEMORY_COLLECTION=agent_memory`
- `RAG_COLLECTION_NAME=material_chunks`
- `RAG_CHUNK_SIZE=1000`
- `RAG_CHUNK_OVERLAP=150`
- `RAG_TOP_K=8`
- `RAG_FETCH_K=24`
- `RAG_MMR_LAMBDA=0.5`
- `MATERIAL_MAX_FILE_MB=15`
- `DEFAULT_MCQ_COUNT=10`
- `DEFAULT_ESSAY_COUNT=3`
- `DEFAULT_SUMMARY_MAX_WORDS=200`
- `REDIS_URL=redis://localhost:6379/0`
- `WEBHOOK_CALLBACK_TIMEOUT_SECONDS=10`
- `WEBHOOK_CALLBACK_MAX_RETRIES=3`
- `WEBHOOK_CALLBACK_BACKOFF_SECONDS=5,15,45`
- `JOB_TTL_SECONDS=86400`
- `JOB_QUEUE_KEY=material_jobs:queue`
- `LKPD_DEFAULT_ACTIVITY_COUNT=5`
- `LKPD_MIN_ACTIVITY_COUNT=1`
- `LKPD_MAX_ACTIVITY_COUNT=15`
- `LKPD_JOB_QUEUE_KEY=lkpd_jobs:queue`
- `LKPD_PDF_DIR=.generated/lkpd`
- `LKPD_PDF_TTL_SECONDS=86400`
- `LKPD_HEADER_LOGO_PATH=.assets/lkpd/logo.png`
- `LKPD_HEADER_ACCENT_HEX=#1F4E79`
- `LKPD_HEADER_TITLE_LINE1=LEMBAR KERJA PESERTA DIDIK (LKPD)`
- `LKPD_HEADER_TITLE_LINE2=SMARTER AI`
- `LKPD_HEADER_TITLE_LINE3=`
- `APP_PUBLIC_BASE_URL=http://localhost:8000`

## Notes
- No public endpoint for polling job status yet
- Final output delivery is callback-only
- Callback signature/auth is not implemented yet
- API error shape uses:
```json
{ "detail": "..." }
```
