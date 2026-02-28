"""
Judgement Plan — Controls which checks J1-J5 must run and their thresholds.
Produced by J0 Judgement Planner.
"""

from pydantic import BaseModel
from typing import List, Dict


class JudgementPlan(BaseModel):
    intent_type: str
    required_checks: List[str]  # e.g. ["sufficiency", "policy", "risk", "priority", "multifactor"]
    thresholds: Dict[str, float] = {}  # e.g. {"risk_auto_execute": 0.4, "priority_min": 0.3}
    org_mode: str = "default"  # fundraising | hiring | default
    metadata: Dict[str, str] = {}
