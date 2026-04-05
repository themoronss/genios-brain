import google.generativeai as genai
from app.config import GEMINI_API_KEY


genai.configure(api_key=GEMINI_API_KEY)


def embed_text(text: str):
    """
    Embed text using Google's Generative AI embedding model.
    Uses gemini-embedding-001 with output_dimensionality=768 (MRL truncation).
    768 dims enables pgvector HNSW indexing (limit: 2000) with only 0.26% quality loss.
    """
    result = genai.embed_content(
        model="models/gemini-embedding-001",
        content=text,
        output_dimensionality=768,
    )

    return result["embedding"]
