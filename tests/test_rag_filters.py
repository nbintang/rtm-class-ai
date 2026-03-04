from __future__ import annotations

from src.agent.rag import MaterialRAGStore


def test_build_retrieval_filter_uses_single_top_level_operator() -> None:
    where = MaterialRAGStore._build_retrieval_filter(
        user_id="material:user-1",
        document_id="doc-abc",
    )

    assert list(where.keys()) == ["$and"]
    assert where["$and"] == [
        {"user_id": "material:user-1"},
        {"document_id": "doc-abc"},
    ]
