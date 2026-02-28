from pydantic import BaseModel
from typing import Dict, Any, List, Optional


class ScopeContext(BaseModel):
    workspace_id: str
    actor_id: str
    role: str
    permissions: List[str] = []


class MemoryContext(BaseModel):
    preferences: Dict[str, Any] = {}
    entity_data: Dict[str, Any] = {}
    episodic: List[Dict[str, Any]] = []
    outcomes: List[Dict[str, Any]] = []


class PolicyContext(BaseModel):
    rules: List[Dict[str, Any]] = []
    trace: List[Dict[str, Any]] = []


class ToolContext(BaseModel):
    snapshots: Dict[str, Any] = {}
    stale_flags: Dict[str, bool] = {}


class RelevantChunk(BaseModel):
    content: str
    similarity: float
    metadata: Dict[str, Any] = {}


class SourceRef(BaseModel):
    source_type: str  # memory | policy | tool | precedent | vector
    source_id: str
    confidence: float = 1.0


class PrecedentContext(BaseModel):
    past_decisions: List[Dict[str, Any]] = []
    templates: List[Dict[str, Any]] = []


class RetrievalMetrics(BaseModel):
    total_memory_items: int = 0
    total_tool_calls: int = 0
    total_precedents: int = 0
    total_policies_matched: int = 0
    retrieval_time_ms: float = 0.0
    estimated_tokens: int = 0


class ContextBundle(BaseModel):
    scope: ScopeContext
    memory: MemoryContext
    policy: PolicyContext
    tools: ToolContext
    relevant_chunks: List[RelevantChunk] = []
    precedents: PrecedentContext = PrecedentContext()
    source_map: List[SourceRef] = []
    metrics: RetrievalMetrics = RetrievalMetrics()
    query_plan_ref: Dict[str, Any] = {}
    context_bundle_version: str = "v1"
