from __future__ import annotations

import unittest
from unittest.mock import patch

from langchain_core.embeddings import DeterministicFakeEmbedding

from src.agent.rag import MaterialRAGStore
from src.config import settings


class MaterialRagStoreTests(unittest.TestCase):
    def test_index_sets_required_metadata(self) -> None:
        with patch(
            "src.agent.rag._build_embeddings",
            return_value=(DeterministicFakeEmbedding(size=64), None),
        ), patch(
            "langchain_chroma.Chroma",
            side_effect=RuntimeError("skip real chroma in unit test"),
        ), patch.object(
            settings, "rag_collection_name", "test_rag_meta"
        ), patch.object(
            settings, "rag_chunk_size", 50
        ), patch.object(
            settings, "rag_chunk_overlap", 10
        ):
            store = MaterialRAGStore()
            document_id = store.new_document_id()
            count, _ = store.index_material(
                user_id="user-1",
                document_id=document_id,
                filename="materi.txt",
                file_type="txt",
                text="Ini materi biologi tentang ekosistem dan rantai makanan." * 8,
            )

            self.assertGreater(count, 0)
            docs = [
                doc
                for doc in store._fallback_docs
                if (doc.metadata or {}).get("document_id") == document_id
            ]
            self.assertTrue(docs)
            metadata = docs[0].metadata or {}
            self.assertEqual(metadata.get("user_id"), "user-1")
            self.assertEqual(metadata.get("document_id"), document_id)
            self.assertEqual(metadata.get("filename"), "materi.txt")
            self.assertEqual(metadata.get("source"), "uploaded_material_chunk")

    def test_retrieval_isolation_by_document_id(self) -> None:
        with patch(
            "src.agent.rag._build_embeddings",
            return_value=(DeterministicFakeEmbedding(size=64), None),
        ), patch(
            "langchain_chroma.Chroma",
            side_effect=RuntimeError("skip real chroma in unit test"),
        ), patch.object(
            settings, "rag_collection_name", "test_rag_isolation"
        ), patch.object(
            settings, "rag_top_k", 8
        ):
            store = MaterialRAGStore()
            doc_a = store.new_document_id()
            doc_b = store.new_document_id()

            store.index_material(
                user_id="user-1",
                document_id=doc_a,
                filename="fisika.txt",
                file_type="txt",
                text="Materi tentang gaya, energi, dan percepatan.",
            )
            store.index_material(
                user_id="user-1",
                document_id=doc_b,
                filename="kimia.txt",
                file_type="txt",
                text="Materi tentang atom, molekul, dan ikatan kimia.",
            )

            docs, _ = store.retrieve_for_generation(
                user_id="user-1",
                document_id=doc_b,
                queries=["atom ikatan kimia"],
            )

            self.assertTrue(docs)
            self.assertTrue(
                all((doc.metadata or {}).get("document_id") == doc_b for doc in docs)
            )


if __name__ == "__main__":
    unittest.main()
