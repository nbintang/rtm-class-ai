# rtm-class-ai

Standalone Python 3.11 AI microservice untuk generate materi dan LKPD via upload file, diproses async, lalu hasil dikirim ke callback URL.

## Current flow
- `POST /api/material` menerima upload (`pdf`, `pptx`, `txt`)
- `POST /api/lkpd` menerima upload (`pdf`, `pptx`, `txt`)
- API langsung balas `202 Accepted` + `job_id`
- Worker background memproses extraction -> RAG -> generation
- Hasil akhir dikirim ke `callback_url` (HTTP POST JSON)
- Jika callback gagal, retry `3` kali dengan backoff default `5,15,45` detik
- Khusus LKPD: server juga generate PDF, disimpan lokal 24 jam, dan callback mengirim `pdf_url`

## Install

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -e .
cp .env.example .env
```

## Run

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

## Run With Docker Compose

1. Isi `.env` (minimal `GROQ_API_KEY` harus terisi).
2. Jalankan:

```bash
docker compose up --build
```

Service yang jalan:
- API di `http://localhost:8000`
- Redis di `localhost:6379`

Stop:

```bash
docker compose down
```

Shortcut npm-style commands (via `taskipy`):

```bash
uv run task up    # docker compose up --build
uv run task upd   # docker compose up -d --build
uv run task down  # docker compose down
uv run task logs  # docker compose logs -f
uv run task ps    # docker compose ps
```

## Endpoint

- `POST /api/material`
- `POST /api/lkpd`
- `GET /api/lkpd/files/{file_id}`

## Request Form Fields

- `user_id` (required)
- `file` (required, single file: `.pdf`, `.pptx`, `.txt`)
- `callback_url` (required, valid `http/https` URL)
- `generate_types` (required, repeatable: `mcq`, `essay`, `summary`; minimal 1 tipe)
- `mcq_count` (optional, default `10`, min `1`, max `20`; dipakai jika `mcq` dipilih)
- `essay_count` (optional, default `3`, min `1`, max `10`; dipakai jika `essay` dipilih)
- `summary_max_words` (optional, default `200`, min `80`, max `400`; dipakai jika `summary` dipilih)
- `mcp_enabled` (optional, default `true`)

## Submit Response (`202`)

```json
{
  "job_id": "job-...",
  "status": "accepted",
  "message": "Material queued for async processing."
}
```

## Callback Payload

Event callback: `material.generated`

### Success

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
  "finished_at": "2026-03-01T00:00:00Z"
}
```

### Failed Processing

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
  "finished_at": "2026-03-01T00:00:00Z"
}
```

## LKPD Request Form Fields

- `user_id` (required)
- `file` (required, single file: `.pdf`, `.pptx`, `.txt`)
- `callback_url` (required, valid `http/https` URL)
- `activity_count` (optional, default `5`, min `1`, max `15`)

## LKPD Submit Response (`202`)

```json
{
  "job_id": "job-...",
  "status": "accepted",
  "message": "LKPD queued for async processing."
}
```

## LKPD Callback Payload

Event callback: `lkpd.generated`

### Success

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
    "pdf_expires_at": "2026-03-02T00:00:00Z",
    "sources": [],
    "warnings": []
  },
  "attempt": 1,
  "finished_at": "2026-03-01T00:00:00Z"
}
```

### Failed Processing

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
  "finished_at": "2026-03-01T00:00:00Z"
}
```

## Example curl (submit async)

```bash
curl -X POST http://localhost:8000/api/material \
  -F "user_id=user-1" \
  -F "callback_url=https://example.com/hooks/material" \
  -F "generate_types=mcq" \
  -F "generate_types=summary" \
  -F "mcq_count=10" \
  -F "summary_max_words=200" \
  -F "mcp_enabled=true" \
  -F "file=@./materi.pdf"
```

## Example curl (submit LKPD async)

```bash
curl -X POST http://localhost:8000/api/lkpd \
  -F "user_id=user-1" \
  -F "callback_url=https://example.com/hooks/lkpd" \
  -F "activity_count=5" \
  -F "file=@./materi.pdf"
```

## Example curl (download LKPD PDF)

```bash
curl -L "http://localhost:8000/api/lkpd/files/lkpd-xxxxxxxx" -o lkpd.pdf
```

## RAG Isolation

Default retrieval bersifat **per-file ketat**:
- Setiap upload punya `document_id` baru.
- Retrieval dibatasi `user_id + document_id` upload saat ini.
- Upload baru tidak tercampur otomatis dengan file upload sebelumnya.

## Environment Variables

- `GROQ_API_KEY` (required)
- `GROQ_MODEL` (default: `llama-3.1-8b-instant`)
- `GROQ_TEMPERATURE` (default: `0.2`)
- `GROQ_TIMEOUT_SECONDS` (default: `30`)
- `MCP_SERVERS_JSON` (JSON object, HTTP MCP transport only)
- `AGENT_MAX_ITERATIONS` (default: `5`)
- `AGENT_MEMORY_COLLECTION` (default: `agent_memory`)
- `CHROMA_PERSIST_DIR` (default: `.chroma`)
- `RAG_COLLECTION_NAME` (default: `material_chunks`)
- `RAG_CHUNK_SIZE` (default: `1000`)
- `RAG_CHUNK_OVERLAP` (default: `150`)
- `RAG_TOP_K` (default: `8`)
- `RAG_FETCH_K` (default: `24`)
- `RAG_MMR_LAMBDA` (default: `0.5`)
- `MATERIAL_MAX_FILE_MB` (default: `15`)
- `DEFAULT_MCQ_COUNT` (default: `10`)
- `DEFAULT_ESSAY_COUNT` (default: `3`)
- `DEFAULT_SUMMARY_MAX_WORDS` (default: `200`)
- `REDIS_URL` (default: `redis://localhost:6379/0`)
- `WEBHOOK_CALLBACK_TIMEOUT_SECONDS` (default: `10`)
- `WEBHOOK_CALLBACK_MAX_RETRIES` (default: `3`)
- `WEBHOOK_CALLBACK_BACKOFF_SECONDS` (default: `5,15,45`)
- `JOB_TTL_SECONDS` (default: `86400`)
- `JOB_QUEUE_KEY` (default: `material_jobs:queue`)
- `LKPD_DEFAULT_ACTIVITY_COUNT` (default: `5`)
- `LKPD_MIN_ACTIVITY_COUNT` (default: `1`)
- `LKPD_MAX_ACTIVITY_COUNT` (default: `15`)
- `LKPD_JOB_QUEUE_KEY` (default: `lkpd_jobs:queue`)
- `LKPD_PDF_DIR` (default: `.generated/lkpd`)
- `LKPD_PDF_TTL_SECONDS` (default: `86400`)
- `APP_PUBLIC_BASE_URL` (default: `http://localhost:8000`)

## Catatan

- Tidak ada endpoint polling status publik.
- Hasil akhir dikirim via callback URL.
- Auth/signature callback belum diaktifkan pada fase ini.
- `GET /api/lkpd/files/{file_id}` hanya valid selama masa retensi file (default 24 jam).
