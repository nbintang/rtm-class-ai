from __future__ import annotations

from src.agent.rag import MaterialRAGStore
from src.agent.types import GenerateType, SourceRef


def build_rag_context(
    *,
    rag_store: MaterialRAGStore,
    user_id: str,
    document_id: str,
    filename: str,
    file_type: str,
    extracted_text: str,
    generate_types: list[GenerateType],
) -> tuple[str, list[SourceRef], list[str]]:
    warnings: list[str] = []

    try:
        chunk_count, index_warnings = rag_store.index_material(
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            file_type=file_type,
            text=extracted_text,
        )
        warnings.extend(index_warnings)
        if chunk_count <= 0:
            warnings.append(
                "RAG indexing produced no chunks; using extracted text fallback."
            )
            return extracted_text, [], warnings
    except Exception as exc:
        warnings.append(f"RAG indexing failed; using extracted text fallback: {exc}")
        return extracted_text, [], warnings

    queries = build_rag_queries(
        extracted_text,
        generate_types=generate_types,
    )
    docs, retrieval_warnings = rag_store.retrieve_for_generation(
        user_id=user_id,
        document_id=document_id,
        queries=queries,
    )
    warnings.extend(retrieval_warnings)

    if not docs:
        warnings.append("RAG retrieval returned no chunks; using extracted text fallback.")
        return extracted_text, [], warnings

    context = "\n\n".join(doc.page_content for doc in docs)
    sources: list[SourceRef] = []
    for doc in docs:
        metadata = doc.metadata or {}
        sources.append(
            SourceRef(
                chunk_id=metadata.get("chunk_id"),
                source_id=metadata.get("document_id"),
                excerpt=doc.page_content[:200],
            )
        )

    return context, sources, warnings


def build_lkpd_rag_context(
    *,
    rag_store: MaterialRAGStore,
    user_id: str,
    document_id: str,
    filename: str,
    file_type: str,
    extracted_text: str,
) -> tuple[str, list[SourceRef], list[str]]:
    warnings: list[str] = []

    try:
        chunk_count, index_warnings = rag_store.index_material(
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            file_type=file_type,
            text=extracted_text,
        )
        warnings.extend(index_warnings)
        if chunk_count <= 0:
            warnings.append(
                "RAG indexing produced no chunks; using extracted text fallback."
            )
            return extracted_text, [], warnings
    except Exception as exc:
        warnings.append(f"RAG indexing failed; using extracted text fallback: {exc}")
        return extracted_text, [], warnings

    queries = build_lkpd_rag_queries(extracted_text)
    docs, retrieval_warnings = rag_store.retrieve_for_generation(
        user_id=user_id,
        document_id=document_id,
        queries=queries,
    )
    warnings.extend(retrieval_warnings)

    if not docs:
        warnings.append("RAG retrieval returned no chunks; using extracted text fallback.")
        return extracted_text, [], warnings

    context = "\n\n".join(doc.page_content for doc in docs)
    sources: list[SourceRef] = []
    for doc in docs:
        metadata = doc.metadata or {}
        sources.append(
            SourceRef(
                chunk_id=metadata.get("chunk_id"),
                source_id=metadata.get("document_id"),
                excerpt=doc.page_content[:200],
            )
        )

    return context, sources, warnings


def build_rag_queries(
    extracted_text: str,
    *,
    generate_types: list[GenerateType],
) -> list[str]:
    topic_hint = " ".join(extracted_text.split()[:40])
    queries = [f"konsep utama materi {topic_hint}"]
    if "summary" in generate_types:
        queries.append(f"ringkasan konsep utama materi {topic_hint}")
    if "mcq" in generate_types:
        queries.append(
            f"fakta penting dan konsep untuk kuis pilihan ganda {topic_hint}"
        )
    if "essay" in generate_types:
        queries.append(f"pemahaman mendalam untuk soal essay {topic_hint}")
    return queries


def build_lkpd_rag_queries(extracted_text: str) -> list[str]:
    topic_hint = " ".join(extracted_text.split()[:40])
    return [
        f"konsep utama dan tujuan pembelajaran materi {topic_hint}",
        f"langkah kegiatan praktikum atau aktivitas pembelajaran {topic_hint}",
        f"indikator penilaian dan rubrik tugas untuk materi {topic_hint}",
    ]

