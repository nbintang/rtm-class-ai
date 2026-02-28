from __future__ import annotations

from fastapi import APIRouter

from src.ai.chains.lkpd_chain import LkpdChain
from src.ai.chains.quiz_chain import QuizChain
from src.ai.chains.remedial_chain import RemedialChain
from src.ai.chains.summary_chain import SummaryChain
from src.ai.rag.index import index_documents
from src.ai.rag.retriever import retrieve_context
from src.ai.validators.quiz_validator import validate_quiz_content
from src.ai.validators.summary_validator import validate_summary_content
from src.schemas.common import HealthResponse, SourceRef
from src.schemas.generate import (
    LkpdContent,
    LkpdGenerateRequest,
    LkpdGenerateResponse,
    QuizContent,
    QuizGenerateRequest,
    QuizGenerateResponse,
    RemedialContent,
    RemedialGenerateRequest,
    RemedialGenerateResponse,
    SummaryContent,
    SummaryGenerateRequest,
    SummaryGenerateResponse,
)
from src.schemas.rag import RagIndexRequest, RagIndexResponse
from src.utils.text import join_context

router = APIRouter()

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


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/rag/index", response_model=RagIndexResponse)
def rag_index(request: RagIndexRequest) -> RagIndexResponse:
    payload = index_documents(
        collection_name=request.collection_name,
        text=request.text,
        documents=[item.model_dump() for item in request.documents or []],
    )
    return RagIndexResponse.model_validate(payload)


@router.post("/generate/quiz", response_model=QuizGenerateResponse)
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


@router.post("/generate/summary", response_model=SummaryGenerateResponse)
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


@router.post("/generate/lkpd", response_model=LkpdGenerateResponse)
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


@router.post("/generate/remedial", response_model=RemedialGenerateResponse)
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
