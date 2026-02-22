from qdrant_client import QdrantClient
from qdrant_client.models import PayloadSchemaType
import os
from dotenv import load_dotenv

load_dotenv()

client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

client.create_payload_index(
    collection_name="genios_context",
    field_name="org_id",
    field_schema=PayloadSchemaType.KEYWORD
)

print("Index created for org_id")