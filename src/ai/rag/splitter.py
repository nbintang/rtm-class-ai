from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import settings


def get_text_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.max_chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
