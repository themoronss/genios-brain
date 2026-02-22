from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from supabase import create_client
from sentence_transformers import SentenceTransformer
import uuid, os

encoder = SentenceTransformer('all-MiniLM-L6-v2')

def store_context(org_id: str, context_type: str, content: str, entity_name=None):

    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_KEY")
    )

    qdrant = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )

    # Store structured
    supabase.table("org_context").insert({
        "org_id": org_id,
        "context_type": context_type,
        "entity_name": entity_name,
        "content": content
    }).execute()

    # Store vector
    vector = encoder.encode(content).tolist()

    qdrant.upsert(
        collection_name="genios_context",
        points=[PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "org_id": org_id,
                "context_type": context_type,
                "entity_name": entity_name,
                "content": content
            }
        )]
    )