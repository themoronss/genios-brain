from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from supabase import create_client
from google import genai
from google.genai import types
import uuid, os

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def store_context(org_id: str, context_type: str, content: str, entity_name=None):

    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

    qdrant = QdrantClient(
        url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY")
    )

    # Store structured
    supabase.table("org_context").insert(
        {
            "org_id": org_id,
            "context_type": context_type,
            "entity_name": entity_name,
            "content": content,
        }
    ).execute()

    # Store vector using Gemini embeddings
    result = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=content,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=384,
        ),
    )
    vector = result.embeddings[0].values

    qdrant.upsert(
        collection_name="genios_context",
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "org_id": org_id,
                    "context_type": context_type,
                    "entity_name": entity_name,
                    "content": content,
                },
            )
        ],
    )
