import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


class EmbeddingService:
    """
    Generates text embeddings using Google Gemini's gemini-embedding-001 model.
    Produces 3072-dimensional vectors.
    """

    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY must be set. "
                "Add it to your .env file."
            )
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = "models/gemini-embedding-001"

    def embed(self, text: str) -> list[float]:
        """
        Generate an embedding vector for the given text.
        Returns a 3072-dimensional float vector.
        """
        result = genai.embed_content(
            model=self.model,
            content=text,
            task_type="retrieval_document"
        )
        return result["embedding"]

    def embed_query(self, text: str) -> list[float]:
        """
        Generate an embedding vector optimized for search queries.
        """
        result = genai.embed_content(
            model=self.model,
            content=text,
            task_type="retrieval_query"
        )
        return result["embedding"]
