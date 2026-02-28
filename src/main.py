from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.ai.chains.lkpd_chain import LkpdChain
from src.ai.chains.quiz_chain import QuizChain
from src.ai.chains.remedial_chain import RemedialChain
from src.ai.chains.summary_chain import SummaryChain
from src.ai.rag.index import index_documents
from src.ai.rag.retriever import retrieve_context
from src.ai.validators.quiz_validator import validate_quiz_content
from src.ai.validators.summary_validator import validate_summary_content
from src.core.constants import APP_NAME, APP_VERSION, DEFAULT_COLLECTION
from src.core.exceptions import ServiceError, register_exception_handlers
from src.core.logging import configure_logging
from src.utils.text import join_context


class HealthResponse(BaseModel):
    status: str


class RagDocumentInput(BaseModel):
    id: str | None = None
    text: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagIndexRequest(BaseModel):
    collection_name: str = DEFAULT_COLLECTION
    text: str | None = None
    documents: list[RagDocumentInput] | None = None

    @model_validator(mode="after")
    def validate_content(self) -> "RagIndexRequest":
        has_text = bool(self.text and self.text.strip())
        has_docs = bool(self.documents)
        if not has_text and not has_docs:
            raise ValueError("Provide either 'text' or 'documents'.")
        return self


class RagIndexResponse(BaseModel):
    collection_name: str
    indexed_chunks: int
    document_count: int
    chunk_ids: list[str]


class SourceRef(BaseModel):
    chunk_id: str | None = None
    source_id: str | None = None
    excerpt: str


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct_answer: str
    explanation: str
    difficulty: str | None = None


class QuizContent(BaseModel):
    title: str
    questions: list[QuizQuestion]


class SummaryContent(BaseModel):
    title: str
    overview: str
    key_points: list[str]
    action_items: list[str] = Field(default_factory=list)


class LkpdActivity(BaseModel):
    title: str
    instruction: str
    expected_output: str


class LkpdContent(BaseModel):
    title: str
    objective: str
    activities: list[LkpdActivity]


class RemedialSession(BaseModel):
    session_title: str
    focus: str
    task: str
    success_criteria: str


class RemedialContent(BaseModel):
    title: str
    diagnosis: str
    sessions: list[RemedialSession]


class BaseGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    collection_name: str = DEFAULT_COLLECTION
    use_rag: bool = True
    additional_context: str | None = None


class QuizGenerateRequest(BaseGenerateRequest):
    grade_level: str = "SMP"
    num_questions: int = Field(default=5, ge=1, le=20)


class SummaryGenerateRequest(BaseGenerateRequest):
    max_words: int = Field(default=180, ge=50, le=500)


class LkpdGenerateRequest(BaseGenerateRequest):
    learning_objective: str = "Understand core concept"
    activity_count: int = Field(default=3, ge=1, le=10)


class RemedialGenerateRequest(BaseGenerateRequest):
    weaknesses: list[str] = Field(default_factory=list)
    session_count: int = Field(default=3, ge=1, le=10)


class QuizGenerateResponse(BaseModel):
    content: QuizContent
    sources: list[SourceRef]
    warnings: list[str]


class SummaryGenerateResponse(BaseModel):
    content: SummaryContent
    sources: list[SourceRef]
    warnings: list[str]


class LkpdGenerateResponse(BaseModel):
    content: LkpdContent
    sources: list[SourceRef]
    warnings: list[str]


class RemedialGenerateResponse(BaseModel):
    content: RemedialContent
    sources: list[SourceRef]
    warnings: list[str]


configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=APP_NAME, version=APP_VERSION)
register_exception_handlers(app)

quiz_chain = QuizChain()
summary_chain = SummaryChain()
lkpd_chain = LkpdChain()
remedial_chain = RemedialChain()


def _build_context(
    *,
    query: str,
    collection_name: str,
    use_rag: bool,
    additional_context: str | None,
) -> tuple[str, list[SourceRef], list[str]]:
    warnings: list[str] = []
    sources: list[SourceRef] = []
    context_parts: list[str] = []

    if use_rag:
        try:
            docs = retrieve_context(query=query, collection_name=collection_name)
            if not docs:
                warnings.append("No RAG context found for this query.")
            else:
                context_parts.append(join_context(docs))
                for doc in docs:
                    metadata = doc.metadata or {}
                    sources.append(
                        SourceRef(
                            chunk_id=metadata.get("chunk_id"),
                            source_id=metadata.get("source_id"),
                            excerpt=doc.page_content[:200],
                        )
                    )
        except Exception as exc:
            warnings.append(f"RAG retrieval failed: {exc}")

    if additional_context:
        context_parts.append(additional_context)

    context = "\n\n".join(part for part in context_parts if part.strip())
    if not context.strip():
        warnings.append("Context is limited; output may be generic.")

    return context, sources, warnings


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/rag/index", response_model=RagIndexResponse)
def rag_index(request: RagIndexRequest) -> RagIndexResponse:
    payload = index_documents(
        collection_name=request.collection_name,
        text=request.text,
        documents=[item.model_dump() for item in request.documents or []],
    )
    return RagIndexResponse.model_validate(payload)


@app.post("/generate/quiz", response_model=QuizGenerateResponse)
def generate_quiz(request: QuizGenerateRequest) -> QuizGenerateResponse:
    context, sources, warnings = _build_context(
        query=request.topic,
        collection_name=request.collection_name,
        use_rag=request.use_rag,
        additional_context=request.additional_context,
    )

    raw_content = quiz_chain.invoke(
        {
            "topic": request.topic,
            "grade_level": request.grade_level,
            "num_questions": request.num_questions,
            "context": context,
        }
    )
    warnings.extend(validate_quiz_content(raw_content, request.num_questions))

    return QuizGenerateResponse(
        content=QuizContent.model_validate(raw_content),
        sources=sources,
        warnings=warnings,
    )


@app.post("/generate/summary", response_model=SummaryGenerateResponse)
def generate_summary(request: SummaryGenerateRequest) -> SummaryGenerateResponse:
    context, sources, warnings = _build_context(
        query=request.topic,
        collection_name=request.collection_name,
        use_rag=request.use_rag,
        additional_context=request.additional_context,
    )

    raw_content = summary_chain.invoke(
        {
            "topic": request.topic,
            "max_words": request.max_words,
            "context": context,
        }
    )
    warnings.extend(validate_summary_content(raw_content, request.max_words))

    return SummaryGenerateResponse(
        content=SummaryContent.model_validate(raw_content),
        sources=sources,
        warnings=warnings,
    )


@app.post("/generate/lkpd", response_model=LkpdGenerateResponse)
def generate_lkpd(request: LkpdGenerateRequest) -> LkpdGenerateResponse:
    context, sources, warnings = _build_context(
        query=request.topic,
        collection_name=request.collection_name,
        use_rag=request.use_rag,
        additional_context=request.additional_context,
    )

    raw_content = lkpd_chain.invoke(
        {
            "topic": request.topic,
            "learning_objective": request.learning_objective,
            "activity_count": request.activity_count,
            "context": context,
        }
    )

    return LkpdGenerateResponse(
        content=LkpdContent.model_validate(raw_content),
        sources=sources,
        warnings=warnings,
    )


@app.post("/generate/remedial", response_model=RemedialGenerateResponse)
def generate_remedial(request: RemedialGenerateRequest) -> RemedialGenerateResponse:
    context, sources, warnings = _build_context(
        query=request.topic,
        collection_name=request.collection_name,
        use_rag=request.use_rag,
        additional_context=request.additional_context,
    )

    raw_content = remedial_chain.invoke(
        {
            "topic": request.topic,
            "weaknesses": ", ".join(request.weaknesses) if request.weaknesses else "Not provided",
            "session_count": request.session_count,
            "context": context,
        }
    )

    return RemedialGenerateResponse(
        content=RemedialContent.model_validate(raw_content),
        sources=sources,
        warnings=warnings,
    )
