"""
Judgement Report — Full Layer 2 output contract.

Expanded from the original minimal contract to include:
- NeedMoreInfo (sufficiency check)
- PriorityReport (urgency/importance)
- MultiFactorReport (ranked factors + constraints)
- JudgementMetrics (timing)
- judgement_version tag

All new fields are optional with defaults for backward compatibility.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


# --- J1: Sufficiency ---

class ClarifyingQuestion(BaseModel):
    question: str
    options: List[str] = []
    reason: str = ""
    blocking_field: str = ""


class NeedMoreInfo(BaseModel):
    value: bool = False
    questions: List[ClarifyingQuestion] = []


# --- J2: Policy ---

class PolicyVerdict(BaseModel):
    status: str = "allow"  # allow | deny | needs_approval
    reasons: List[str] = []
    violations: List[str] = []
    approvals_required: List[str] = []
    constraints: List[str] = []


# --- J3: Risk ---

class RiskReport(BaseModel):
    score: float = 0.0
    level: str = "low"  # low | medium | high
    reasons: List[str] = []
    sensitive_entities: List[str] = []
    reversibility: str = "reversible"  # reversible | partial | irreversible


# --- J4: Priority ---

class PriorityReport(BaseModel):
    score: float = 0.5
    reasons: List[str] = []
    org_mode: str = "default"
    distraction_flag: bool = False


# --- J5: Multi-Factor ---

class RankedFactor(BaseModel):
    name: str
    category: str  # actor | org | situation | agent | tool
    weight: float = 0.0
    value: Any = None
    source_ref: str = ""


class MultiFactorReport(BaseModel):
    ranked_factors: List[RankedFactor] = []
    constraints: List[str] = []
    confidence: float = 0.0


# --- Metrics ---

class JudgementMetrics(BaseModel):
    judging_time_ms: float = 0.0
    checks_run: int = 0
    policies_evaluated: int = 0
    factors_extracted: int = 0


# --- Final Report ---

class JudgementReport(BaseModel):
    # Original fields (backward compat)
    risk: RiskReport = RiskReport()
    policy: PolicyVerdict = PolicyVerdict()
    ok_to_act: bool = False
    needs_approval: bool = False

    # New fields (all optional with defaults)
    need_more_info: NeedMoreInfo = NeedMoreInfo()
    priority: PriorityReport = PriorityReport()
    multi_factor: MultiFactorReport = MultiFactorReport()
    metrics: JudgementMetrics = JudgementMetrics()
    judgement_version: str = "v1"