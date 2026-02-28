from src.ai.rag.retriever import Retriever


def test_rag_retriever_returns_results() -> None:
    retriever = Retriever()
    retriever.add_document("doc-1", "Python is a programming language used in AI systems.")
    retriever.add_document("doc-2", "Biology studies living organisms.")

    results = retriever.retrieve("programming language", top_k=1)
    assert len(results) == 1
    assert results[0].id.startswith("doc-")

