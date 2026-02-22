# setup_qdrant.py

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import os
from dotenv import load_dotenv

load_dotenv()

client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))

client.create_collection(
    collection_name="genios_context",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
)

print("Collection created")
