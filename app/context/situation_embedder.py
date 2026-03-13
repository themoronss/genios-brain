from app.graph.embedder import embed_text


def embed_situation(text: str):
    """
    Convert a situation string into an embedding using Gemini.

    Args:
        text: The situation text to embed

    Returns:
        A vector embedding (list of floats) with dimension 1536
        matching pgvector dimension requirements
    """
    return embed_text(text)
