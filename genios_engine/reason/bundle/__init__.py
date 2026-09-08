"""Group L4.5 — **the voice**. The reasoning bundle, its gauntlet, its fallback, and the gate every
model consult in Layer 4 passes through.

    the founder's instruction, which is why this group exists at all:
    "reasoning wala part — content achha rahe, context achha rahe. Otherwise, without reasoning,
     cheezein polish nahi hongi, aur user ke saamne detail jaana chahiye."

**What this package is allowed to do:** interpret evidence and narrate reasoning.
**What nothing in it can do:** choose, score, or permit. Score, rank, priority, permission, policy,
elimination and confidence composition are deterministic, live elsewhere, and are already finished
before a single word here exists.

Read in this order:

| module | what it owns |
|---|---|
| `sites` | MAP A's R-series as a closed vocabulary: which sites exist, at which tier |
| `budget` | doc 11's guards — per-decision and per-tenant spend, in integer micro-dollars |
| `gate` | **C5** — the one door. Activation, precondition, cache, budget, call, validate, fallback |
| `numbers` | the catalogue: every number the deterministic half computed, and nothing else |
| `grounding` | the material one decision may rest on, quote, or name |
| `prompt` | what R-2 shows a model — a decision already made, never a choice |
| `gauntlet` | **V-1 … V-7**, in order, every outcome recorded |
| `template` | the deterministic fallback: plainer, never less true, and labelled |
| `narrator` | **R-2** — the five sections for one fixed decision |
| `store` | where a narrative lives and every consult is receipted (migration 0120) |
| `sweep` | the real path: `runner.run_all` -> narrate what was just published |

The doctrine property, and the test that holds it:
`tests/reason/test_bundle_doctrine.py` — with every R-site force-failed, a full replay produces
BYTE-IDENTICAL DecisionObjects. If that ever fails, the model has acquired decision authority and
the wave is reverted.
"""

from __future__ import annotations

from .budget import NarrativeBudget, cost_micro_usd, estimate_micro_usd
from .gate import ConsultResult, RSiteGate, force_fail_r_sites, force_failed
from .gauntlet import CheckResult, GauntletReport, run_gauntlet
from .grounding import Grounding, build_grounding
from .narrator import Narration, narrate
from .numbers import Catalogue, Number, build_catalogue
from .prompt import build_prompt
from .sites import R_SITES, SITE_NARRATE, require_site, tier_for
from .store import BundleStore, StoredBundle, bundles_for_cards
from .sweep import narrate_published, sweep_orgs
from .template import build_template, template_bundle

__all__ = ["BundleStore", "Catalogue", "CheckResult", "ConsultResult", "GauntletReport",
           "Grounding", "NarrativeBudget", "Narration", "Number", "RSiteGate", "R_SITES",
           "SITE_NARRATE", "StoredBundle", "build_catalogue", "build_grounding", "build_prompt",
           "build_template", "bundles_for_cards", "cost_micro_usd", "estimate_micro_usd",
           "force_fail_r_sites", "force_failed", "narrate", "narrate_published", "require_site",
           "run_gauntlet", "sweep_orgs", "template_bundle", "tier_for"]
