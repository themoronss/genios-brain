import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.graph.embedding_jobs import embed_contacts

embed_contacts("87b0235e-e29d-468a-b841-522c13546515")