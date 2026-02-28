# RTM Class AI

Backend template for an AI-powered class platform:
- User/auth flows
- Material ingestion and processing
- AI generation (summary, quiz, LKPD, remedial)
- Quiz creation and scoring
- RAG building blocks

## Structure

The project follows this module layout:
- `src/main.py` - FastAPI app bootstrap
- `src/config.py` - environment config
- `src/core/` - logging/security/exceptions/constants
- `src/db/` - SQLAlchemy base/session/models
- `src/modules/` - domain routes/schemas/services
- `src/ai/` - provider gateway, RAG, prompts, generators, validators
- `src/storage/` - local + S3 storage adapters
- `src/jobs/` - async queue/task stubs
- `src/utils/` - shared utility helpers
- `tests/` - starter tests

## Quick Start

1. Install dependencies:

```bash
pip install -e ".[dev]"
```

2. Copy environment file:

```bash
cp .env.example .env
```

3. Run API:

```bash
uvicorn src.main:app --reload
```

4. Open docs:
- `http://127.0.0.1:8000/api/v1/docs`

## Notes

- The current service layer uses in-memory stores for quick scaffolding.
- DB models and SQLAlchemy setup are prepared for migration to persistent repositories.
- AI gateway falls back to an echo provider when `OPENAI_API_KEY` is not configured.
