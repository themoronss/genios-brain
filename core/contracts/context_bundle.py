from pydantic import BaseModel
from typing import Dict, Any, List


class ScopeContext(BaseModel):
    workspace_id: str
    actor_id: str
    role: str


class MemoryContext(BaseModel):
    preferences: Dict[str, Any] = {}
    entity_data: Dict[str, Any] = {}


class PolicyContext(BaseModel):
    rules: List[Dict[str, Any]] = []


class ToolContext(BaseModel):
    snapshots: Dict[str, Any] = {}


class RelevantChunk(BaseModel):
    content: str
    similarity: float
    metadata: Dict[str, Any] = {}


class ContextBundle(BaseModel):
    scope: ScopeContext
    memory: MemoryContext
    policy: PolicyContext
    tools: ToolContext
    relevant_chunks: List[RelevantChunk] = []
