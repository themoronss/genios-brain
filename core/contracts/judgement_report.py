from pydantic import BaseModel
from typing import List


class RiskReport(BaseModel):
    score: float
    level: str
    reasons: List[str]


class PolicyVerdict(BaseModel):
    status: str  # allow | deny | needs_approval
    reasons: List[str]


class JudgementReport(BaseModel):
    risk: RiskReport
    policy: PolicyVerdict
    ok_to_act: bool
    needs_approval: bool