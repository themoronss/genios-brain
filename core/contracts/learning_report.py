"""
Learning Report — Full Layer 4 output contract.

Expanded from the original minimal contract to include:
- OutcomeRecord (execution result + feedback + errors + metrics)
- MemoryUpdate (with before/after, evidence, scope)
- PolicySuggestion (suggested governance changes)
- EvalMetrics (quality, drift, red flags)
- learning_version tag

All new fields are optional with defaults for backward compatibility.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


# --- L1: Outcome ---

class OutcomeRecord(BaseModel):
    execution_result: str = "pending"   # approved | rejected | auto_executed | failed | pending
    user_feedback: str = ""             # approve | edit | reject | ""
    user_comment: str = ""
    tool_errors: List[Dict[str, Any]] = []
    retries: int = 0
    side_effects: List[str] = []        # e.g. ["email_sent", "meeting_scheduled"]
    latency_ms: float = 0.0
    token_usage: int = 0
    tool_call_count: int = 0


# --- L2: Memory Writeback ---

class MemoryUpdate(BaseModel):
    field: str
    new_value: Any = ""
    confidence: float = 0.0
    # New fields
    operation: str = "upsert"           # upsert | append | delete
    previous_value: Any = None
    evidence_refs: List[str] = []
    scope: str = "workspace"            # workspace | actor | global
    auto_approved: bool = False
    review_required: bool = False
    reason: str = ""


# --- L3: Policy Suggestions ---

class PolicySuggestion(BaseModel):
    suggestion_type: str     # new_policy | threshold_change | guardrail
    description: str
    evidence: List[str] = []
    priority: str = "low"   # low | medium | high
    proposed_change: Dict[str, Any] = {}


# --- L4: Eval Metrics ---

class EvalMetrics(BaseModel):
    quality_score: float = 0.0
    drift_detected: bool = False
    drift_details: List[str] = []
    red_flag_count: int = 0
    red_flags: List[str] = []
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0


# --- Learning Metrics ---

class LearningMetrics(BaseModel):
    learning_time_ms: float = 0.0
    updates_proposed: int = 0
    updates_auto_approved: int = 0
    updates_queued_review: int = 0
    suggestions_generated: int = 0


# --- Final Report ---

class LearningReport(BaseModel):
    # Original fields (backward compat)
    outcome: str = "pending"
    memory_updates: List[MemoryUpdate] = []

    # New fields (all optional with defaults)
    outcome_record: OutcomeRecord = OutcomeRecord()
    policy_suggestions: List[PolicySuggestion] = []
    eval_metrics: EvalMetrics = EvalMetrics()
    learning_metrics: LearningMetrics = LearningMetrics()
    learning_version: str = "v1"