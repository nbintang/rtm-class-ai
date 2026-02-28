from langchain_openai import OpenAIEmbeddings

from src.config import settings


def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        model=settings.openai_embed_model,
    )
