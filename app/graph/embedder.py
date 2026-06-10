"""Embedding helper. Routes through llm_client.embed — usage logged to llm_usage."""
from typing import Optional

from app.llm import llm_client


def embed_text(text: str, org_id: Optional[str] = None):
    """
    Embed text with gemini-embedding-001 (output_dimensionality=768).
    768 dims enables pgvector HNSW indexing (limit 2000), ~0.26% quality loss.
    Pass org_id when available so usage is attributed; None for system calls.
    """
    return llm_client.embed(org_id=org_id, text_in=text)
