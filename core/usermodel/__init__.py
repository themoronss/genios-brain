"""g-i-9 User Model — thin per-user persona (CONCLUSIONS, not raw history).

Per MD g-i-9 §0 (the law):
- Store distilled CONCLUSIONS, NOT raw history
  (history stays in g-i-1 source memory, referenced by pointer)
- Separate from Company Mind (g-i-3) — persona travels with user, not org
- "Persona" = the ONE user the system adopts, NOT multi-persona debate swarm
- redLines = HARD GATE (like g-i-2 hard constraints — force flag-to-human)
- Strongest encryption + per-user isolation
- User can view + edit + delete EVERYTHING (full transparency)
- NEVER cross-user, NEVER cross-company, NEVER shared/sold

Consumed by:
- g-i-2 decision pipeline   (routing + allowed actions + redline veto)
- g-i-4 prioritize          (priorities for relevance scoring)
- g-i-6 narrator            (voice for tone/length/lead-with)

Public API:
    from core.usermodel import (
        UserModel, Voice, DecisionPolicy, ProcessHabits, Priorities, RelationshipTag,
        seed_profile, SeedInput,
        record_edit, distill_field, DistillResult,
        propose_shift, confirm_proposal, reject_proposal, BigShiftProposal,
        apply_to_decision, apply_to_prioritizer, apply_to_narrator, AppliedPersona,
        view_profile, update_field, delete_profile,
    )
"""

from core.usermodel.apply import (
    AppliedPersona,
    apply_to_decision,
    apply_to_narrator,
    apply_to_prioritizer,
)
from core.usermodel.control import delete_profile, update_field, view_profile
from core.usermodel.distill import DistillResult, distill_field, record_edit
from core.usermodel.propose import (
    BigShiftProposal,
    confirm_proposal,
    propose_shift,
    reject_proposal,
)
from core.usermodel.schema import (
    DecisionPolicy,
    Priorities,
    ProcessHabits,
    RelationshipTag,
    UserModel,
    Voice,
)
from core.usermodel.seed import SeedInput, seed_profile

__all__ = [
    "AppliedPersona",
    "BigShiftProposal",
    "DecisionPolicy",
    "DistillResult",
    "Priorities",
    "ProcessHabits",
    "RelationshipTag",
    "SeedInput",
    "UserModel",
    "Voice",
    "apply_to_decision",
    "apply_to_narrator",
    "apply_to_prioritizer",
    "confirm_proposal",
    "delete_profile",
    "distill_field",
    "propose_shift",
    "record_edit",
    "reject_proposal",
    "seed_profile",
    "update_field",
    "view_profile",
]
