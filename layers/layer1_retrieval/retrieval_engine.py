"""
Layer 1 — Retrieval Engine

The main orchestrator for the Retrieval Layer.
Coordinates all sub-modules (R0-R5) and the Bundle Assembler
to produce a complete ContextBundle.

Maintains backward compatibility: still accepts optional
memory_store/vector_store for legacy callers.
"""

import time

from core.contracts.context_bundle import (
    ContextBundle,
    ScopeContext,
    MemoryContext,
    PolicyContext,
    ToolContext,
    RelevantChunk,
    PrecedentContext,
)
from core.contracts.query_plan import QueryPlan

# R0 — Query Builder
from layers.layer1_retrieval.r0_query_builder.plan_composer import build_query_plan

# R1 — Scope Resolver
from layers.layer1_retrieval.r1_scope_resolver.scope_guard import resolve_scope

# R2 — Memory Retrieval
from layers.layer1_retrieval.r2_memory.memory_retriever import MemoryRetriever

# R3 — Tool State
from layers.layer1_retrieval.r3_tools.tool_orchestrator import ToolOrchestrator

# R4 — Policies
from layers.layer1_retrieval.r4_policies.policy_loader import PolicyLoader
from layers.layer1_retrieval.r4_policies.policy_matcher import PolicyMatcher

# R5 — Precedents
from layers.layer1_retrieval.r5_precedents.decision_log_retriever import DecisionLogRetriever
from layers.layer1_retrieval.r5_precedents.outcome_ranker import rank_precedents

# Bundle Assembler
from layers.layer1_retrieval.bundle_assembler.assembler import assemble_bundle


class RetrievalEngine:

    def __init__(self, memory_store=None, vector_store=None):
        """
        Args:
            memory_store: Optional MemoryStore instance.
                          If provided, memory is fetched from Supabase.
                          If None, mock data is used (for testing).
            vector_store: Optional VectorStore instance.
                          If provided, semantic search is performed.
                          If None, no relevant chunks are returned.
        """
        self.memory_retriever = MemoryRetriever(memory_store=memory_store)
        self.tool_orchestrator = ToolOrchestrator()
        self.policy_loader = PolicyLoader()
        self.policy_matcher = PolicyMatcher()
        self.precedent_retriever = DecisionLogRetriever()
        self.vector_store = vector_store

    def run(self, intent: str, workspace_id: str, actor_id: str) -> ContextBundle:
        """
        Layer 1 — Full Retrieval Pipeline.

        Steps:
            R0: Build query plan (normalize intent, determine requirements)
            R1: Resolve scope (workspace + actor + permissions)
            R2: Retrieve memory (preferences, entities, episodic)
            R3: Retrieve tool state (Gmail, Calendar via providers)
            R4: Retrieve policies (load + match)
            R5: Retrieve precedents (past decisions + ranking)
            Vector: Semantic search via vector store
            Assemble: Combine all into ContextBundle with citations + metrics

        Args:
            intent: Raw user intent text.
            workspace_id: Workspace identifier.
            actor_id: Actor identifier.

        Returns:
            Complete ContextBundle.
        """
        start_time = time.time()
        source_lists = []

        # --- R0: Query Builder ---
        query_plan = build_query_plan(intent)

        # --- R1: Scope Resolver ---
        scope = resolve_scope(workspace_id, actor_id)

        # --- R2: Memory Retrieval ---
        memory = MemoryContext()
        if "memory" in query_plan.required_contexts:
            memory, memory_sources = self.memory_retriever.retrieve(
                actor_id=actor_id,
                query_plan=query_plan,
            )
            source_lists.append(memory_sources)

        # --- R3: Tool State Retrieval ---
        tools = ToolContext()
        if "tools" in query_plan.required_contexts:
            tools, tool_sources = self.tool_orchestrator.retrieve(
                query_plan=query_plan,
                workspace_id=workspace_id,
            )
            source_lists.append(tool_sources)

        # --- R4: Policy Retrieval ---
        raw_policies = self.policy_loader.load(workspace_id, query_plan)
        policy, policy_sources = self.policy_matcher.match(
            policies=raw_policies,
            intent_type=query_plan.intent_type,
            entities=query_plan.entities,
            entity_data=memory.entity_data,
        )
        source_lists.append(policy_sources)

        # --- R5: Precedent Retrieval ---
        precedents = PrecedentContext()
        if "precedents" in query_plan.required_contexts:
            raw_precedents = self.precedent_retriever.retrieve(
                workspace_id=workspace_id,
                query_plan=query_plan,
            )
            precedents, precedent_sources = rank_precedents(raw_precedents)
            source_lists.append(precedent_sources)

        # --- Vector Search (semantic retrieval) ---
        relevant_chunks = self._retrieve_relevant_context(
            intent, workspace_id, query_plan
        )

        # --- Assemble ---
        elapsed_ms = (time.time() - start_time) * 1000

        bundle = assemble_bundle(
            scope=scope,
            memory=memory,
            policy=policy,
            tools=tools,
            precedents=precedents,
            relevant_chunks=relevant_chunks,
            source_lists=source_lists,
            retrieval_time_ms=elapsed_ms,
            query_plan_ref=query_plan.model_dump(),
        )

        return bundle

    def _retrieve_relevant_context(
        self, intent: str, workspace_id: str, query_plan: QueryPlan
    ) -> list[RelevantChunk]:
        """
        Perform semantic search using vector embeddings.
        Returns empty list if no vector_store is configured.
        """
        if not self.vector_store:
            return []

        results = self.vector_store.search(
            query=intent,
            workspace_id=workspace_id,
            top_k=5,
            threshold=0.3,
        )

        return [
            RelevantChunk(
                content=r["content"],
                similarity=r["similarity"],
                metadata=r.get("metadata", {}),
            )
            for r in results
        ]
