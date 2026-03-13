import google.generativeai as genai
from app.config import GEMINI_API_KEY


genai.configure(api_key=GEMINI_API_KEY)


def embed_text(text: str):
    """
    Embed text using Google's Generative AI embedding model.
    Uses the gemini-embedding-001 model which is available in the current API.
    """
    result = genai.embed_content(model="models/gemini-embedding-001", content=text)

    return result["embedding"]
