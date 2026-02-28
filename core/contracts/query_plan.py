from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class RetrievalBudget(BaseModel):
    max_tool_calls: int = 4
    max_memory_items: int = 20
    max_tokens: int = 4000
    max_precedents: int = 5


class QueryPlan(BaseModel):
    """
    Structured retrieval plan produced by R0 Query Builder.
    Controls what to fetch, from where, and how deep.
    """
    intent_type: str  # normalized intent category
    raw_intent: str  # original user text
    required_contexts: List[str]  # e.g. ["scope", "memory", "tools", "policies", "precedents"]
    entities: List[str] = []  # extracted entity names
    budget: RetrievalBudget = RetrievalBudget()
    ttl_overrides: Dict[str, int] = {}  # tool_name -> ttl_seconds override
    metadata: Dict[str, Any] = {}
