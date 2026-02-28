from core.stores.database import get_supabase_client
from core.stores.embedding_service import EmbeddingService


class VectorStore:
    """
    Store for semantic search over knowledge chunks using Supabase pgvector.
    Uses cosine similarity via the match_knowledge_chunks RPC function.
    """

    def __init__(self, embedding_service: EmbeddingService = None, client=None):
        """
        Args:
            embedding_service: EmbeddingService instance for generating vectors.
            client: Optional Supabase client (uses default if not provided).
        """
        self.embedding_service = embedding_service or EmbeddingService()
        self.client = client or get_supabase_client()

    def search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 5,
        threshold: float = 0.5
    ) -> list[dict]:
        """
        Semantic search: embed the query and find the most similar
        knowledge chunks in the given workspace.

        Returns list of dicts with: content, similarity, metadata
        """
        query_embedding = self.embedding_service.embed_query(query)

        result = self.client.rpc(
            "match_knowledge_chunks",
            {
                "query_embedding": query_embedding,
                "match_workspace_id": workspace_id,
                "match_count": top_k,
                "match_threshold": threshold,
            }
        ).execute()

        return result.data or []

    def insert(
        self,
        workspace_id: str,
        content: str,
        metadata: dict = None
    ) -> dict:
        """
        Embed content and insert as a knowledge chunk.
        """
        embedding = self.embedding_service.embed(content)

        row = {
            "workspace_id": workspace_id,
            "content": content,
            "metadata": metadata or {},
            "embedding": embedding,
        }

        result = self.client.table("knowledge_chunks").insert(row).execute()
        return result.data[0] if result.data else {}
