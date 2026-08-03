"""Token budget pruning for context bundles.

Section B's reasoner runs on Haiku (8K context). At 25+ contacts a bundle
can exceed that and silently truncate inside the LLM call → garbage output.
This module prunes oldest/cheapest items until the JSON fits the budget.

Design decisions:
  - No tiktoken dep: chars/4 estimate is good enough at this stage. A later
    upgrade can swap _estimate_tokens() for tiktoken.cl100k_base.
  - Never prunes: entity basics, open_commitments (overdue is critical),
    narrative, confidence/scores. These are load-bearing for the prompt.
  - Pruning order is "least useful first": old interactions → company
    stakeholders → precedents → situational context.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Haiku is 8192 tokens; leave ~1200 headroom for system prompt + output.
DEFAULT_MAX_TOKENS = 7000

# Order matters — earlier entries get pruned first when over budget.
_PRUNABLE_LIST_KEYS = (
    "recent_interactions",   # trim oldest
    "company_contacts",      # full drop if needed
    "precedents",
    "situation_signals",
    "warm_intro_paths",
    "situational_context",
)


def _estimate_tokens(obj: Any) -> int:
    """Cheap token estimate. ~4 chars per token for English."""
    try:
        return max(1, len(json.dumps(obj, default=str)) // 4)
    except Exception:
        return 0


def prune_bundle_to_budget(
    bundle: Dict, max_tokens: int = DEFAULT_MAX_TOKENS,
) -> Dict:
    """Mutate `bundle` until it fits `max_tokens`. Returns the same dict.

    Records what was dropped under bundle['_pruned'] so the LLM prompt and
    observability can flag pruned bundles (lower confidence weighting upstream).
    """
    if not isinstance(bundle, dict):
        return bundle

    before = _estimate_tokens(bundle)
    if before <= max_tokens:
        return bundle  # fast path, no work

    items_dropped = 0
    for key in _PRUNABLE_LIST_KEYS:
        if _estimate_tokens(bundle) <= max_tokens:
            break
        items = bundle.get(key)
        if not isinstance(items, list) or not items:
            continue
        # Trim half the items at a time from the oldest end (start of list).
        # Most builders sort newest-first, so head = oldest.
        while items and _estimate_tokens(bundle) > max_tokens:
            items.pop()  # drop the last (oldest) item
            items_dropped += 1
        if not items:
            bundle.pop(key, None)

    after = _estimate_tokens(bundle)
    bundle["_pruned"] = {
        "items_dropped": items_dropped,
        "estimate_tokens_before": before,
        "estimate_tokens_after": after,
        "max_tokens": max_tokens,
    }
    if items_dropped:
        logger.info(
            f"bundle pruned: dropped={items_dropped} "
            f"tokens {before}→{after} (max={max_tokens})"
        )
    return bundle
