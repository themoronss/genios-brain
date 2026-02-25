from pydantic import BaseModel
from typing import List


class ActionStep(BaseModel):
    description: str


class ActionPlan(BaseModel):
    steps: List[ActionStep]


class DecisionPacket(BaseModel):
    intent_type: str
    execution_mode: str  # auto_execute | needs_approval | propose_only
    action_plan: ActionPlan
    reasons: List[str]