from qdrant_client import QdrantClient
from supabase import create_client
from sentence_transformers import SentenceTransformer
import os


class ContextRetriever:
    def __init__(self):
        self.qdrant = QdrantClient(
            url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY")
        )

        self.supabase = create_client(
            os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
        )

        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")

    def get_context(self, intent: str, org_id: str, entity_name: str = None):
        """Retrieve structured context with metadata"""
        vector = self.encoder.encode(intent).tolist()

        from qdrant_client.models import Filter, FieldCondition, MatchValue

        results = self.qdrant.query_points(
            collection_name="genios_context",
            query=vector,
            limit=8,
            query_filter=Filter(
                must=[FieldCondition(key="org_id", match=MatchValue(value=org_id))]
            ),
        )

        # Structured context with metadata
        context = {
            "policies": [],
            "relationships": [],
            "profile": None,
            "entity_state": None,
        }

        for r in results.points:
            if r.score > 0.3:  # relevance threshold
                ctx_type = r.payload.get("context_type")

                if ctx_type == "policy":
                    context["policies"].append(
                        {
                            "content": r.payload["content"],
                            "confidence": round(r.score, 3),
                        }
                    )
                elif ctx_type == "relationship":
                    context["relationships"].append(
                        {
                            "content": r.payload["content"],
                            "entity_name": r.payload.get("entity_name"),
                            "confidence": round(r.score, 3),
                        }
                    )
                elif ctx_type == "profile":
                    context["profile"] = r.payload["content"]

        # Fetch entity state if entity mentioned
        if entity_name:
            result = (
                self.supabase.table("entity_state")
                .select("*")
                .eq("org_id", org_id)
                .ilike("entity_name", f"%{entity_name}%")
                .execute()
            )
            if result.data:
                context["entity_state"] = result.data[0]["current_state"]

        return context
