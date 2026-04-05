from app.graph.embedder import embed_text


def embed_situation(text: str):
    """
    Convert a situation string into an embedding using Gemini.

    Args:
        text: The situation text to embed

    Returns:
        A vector embedding (list of floats) with dimension 768
        (gemini-embedding-001 with MRL output_dimensionality=768)
    """
    return embed_text(text)
