from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from src.ai.embeddings import get_embeddings
from src.config import settings


def build_retriever(collection_name: str, k: int | None = None):
    vectorstore = Chroma(
        collection_name=collection_name,
        persist_directory=settings.chroma_persist_dir,
        embedding_function=get_embeddings(),
    )
    return vectorstore.as_retriever(search_kwargs={"k": k or settings.top_k})


def retrieve_context(query: str, collection_name: str, k: int | None = None) -> list[Document]:
    retriever = build_retriever(collection_name=collection_name, k=k)
    return retriever.invoke(query)
