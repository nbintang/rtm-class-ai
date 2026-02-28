# rtm-class-ai

Standalone Python 3.11 AI microservice for LangChain + RAG + prompt-based generation. This service is designed to be called by a separate NestJS backend.

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

## Endpoints

- `GET /health`
- `POST /rag/index`
- `POST /generate/quiz`
- `POST /generate/summary`
- `POST /generate/lkpd`
- `POST /generate/remedial`

## Example curl

### Health

```bash
curl -X GET http://localhost:8000/health
```

### RAG Index

```bash
curl -X POST http://localhost:8000/rag/index \
  -H "Content-Type: application/json" \
  -d '{
    "collection_name": "biology",
    "text": "Fotosintesis adalah proses tumbuhan membuat makanan..."
  }'
```

### Generate Quiz

```bash
curl -X POST http://localhost:8000/generate/quiz \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Fotosintesis",
    "grade_level": "SMP",
    "num_questions": 5,
    "collection_name": "biology",
    "use_rag": true
  }'
```

### Generate Summary

```bash
curl -X POST http://localhost:8000/generate/summary \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Fotosintesis",
    "max_words": 150,
    "collection_name": "biology",
    "use_rag": true
  }'
```

### Generate LKPD

```bash
curl -X POST http://localhost:8000/generate/lkpd \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Fotosintesis",
    "learning_objective": "Siswa memahami faktor yang mempengaruhi fotosintesis",
    "activity_count": 3,
    "collection_name": "biology",
    "use_rag": true
  }'
```

### Generate Remedial

```bash
curl -X POST http://localhost:8000/generate/remedial \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Fotosintesis",
    "weaknesses": ["Belum memahami reaksi terang", "Sulit membedakan kloroplas"],
    "session_count": 3,
    "collection_name": "biology",
    "use_rag": true
  }'
```

## NestJS Integration

Set the AI base URL in NestJS to:

- `http://localhost:8000`

Then call these paths directly:

- `/health`
- `/rag/index`
- `/generate/quiz`
- `/generate/summary`
- `/generate/lkpd`
- `/generate/remedial`
