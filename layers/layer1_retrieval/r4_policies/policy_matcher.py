"""
R4.2 — Policy Matcher

Filters policies to only those applicable to the current intent.
Handles conflict resolution (stricter rule wins).
Produces PolicyContext with trace.
"""

from core.contracts.context_bundle import PolicyContext, SourceRef


class PolicyMatcher:
    """Match and filter policies based on intent, entities, and context."""

    def match(
        self,
        policies: list[dict],
        intent_type: str,
        entities: list[str],
        entity_data: dict,
    ) -> tuple[PolicyContext, list[SourceRef]]:
        """
        Filter policies to applicable ones and produce trace.

        Args:
            policies: All policies loaded for the workspace.
            intent_type: Canonical intent type.
            entities: Entity names from intent.
            entity_data: Entity memory data (for checking tiers etc).

        Returns:
            Tuple of (PolicyContext with rules + trace, list of SourceRefs).
        """
        matched_rules = []
        trace = []
        sources = []

        for policy in policies:
            is_match, reason = self._check_policy(
                policy, intent_type, entities, entity_data
            )

            trace_entry = {
                "policy_id": policy.get("id", "unknown"),
                "policy_type": policy.get("policy_type", "unknown"),
                "matched": is_match,
                "reason": reason,
            }
            trace.append(trace_entry)

            if is_match:
                matched_rules.append(policy)
                sources.append(SourceRef(
                    source_type="policy",
                    source_id=str(policy.get("id", "unknown")),
                    confidence=1.0,
                ))

        # Conflict resolution: sort by priority (higher = stricter)
        matched_rules.sort(key=lambda p: p.get("priority", 0), reverse=True)

        return PolicyContext(
            rules=matched_rules,
            trace=trace,
        ), sources

    def _check_policy(
        self,
        policy: dict,
        intent_type: str,
        entities: list[str],
        entity_data: dict,
    ) -> tuple[bool, str]:
        """
        Check if a single policy applies to the current context.

        Returns:
            Tuple of (is_match, reason_string).
        """
        condition = policy.get("condition", {})

        # Check intent_type condition
        if "intent_type" in condition:
            if condition["intent_type"] != intent_type:
                return False, f"intent_type mismatch: need {condition['intent_type']}"

        # Check recipient_tier condition
        if "recipient_tier" in condition:
            required_tier = condition["recipient_tier"]
            tier_found = False
            for entity_name in entities:
                edata = entity_data.get(entity_name, {})
                if isinstance(edata, dict) and edata.get("tier") == required_tier:
                    tier_found = True
                    break

            # Also check top-level entity_data for legacy format
            if not tier_found:
                for key, val in entity_data.items():
                    if isinstance(val, dict) and val.get("tier") == required_tier:
                        tier_found = True
                        break

            if not tier_found:
                return False, f"no entity with tier={required_tier}"

        # If we passed all condition checks, it's a match
        return True, "all conditions met"
