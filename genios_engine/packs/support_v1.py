"""customer_support pack v1.0.0 — DATA, not code. The authority lane for the Customer Support
domain.

Same reason as `admin_v1.py`: `persist_complete` requires the config snapshot's `pack_id` to equal
the capability's `domain`, and no `customer_support` pack existed — so all 49 authored Customer
Support capabilities died under `no_tenant_pack` and emitted nothing.

The pack id is `customer_support`, NOT `support`. Those are two different names for two different
things and both are correct where they are used:

  * `support` is the DOMAIN HINT Layer 1 attaches and Layer 2 correlates under
    (`capture/domain/hints.py`, `context/domain_spec.py`).
  * `customer_support` is the CORPUS DOMAIN ID (`Customer Support Expertise/domain.yaml`), which
    is what `expertise_capability_manifest` puts in `manifest.domain`, which is what
    `persist_complete` compares against `config_snapshots.pack_id`.

`capability_resolver.DOMAIN_ALIASES` already bridges the first to the second. This pack has to
match the SECOND, because the pack lookup happens after the alias, keyed on `manifest.domain`.
Naming it `support` would resolve nothing and reproduce exactly the bug it exists to fix.

`rules: []` IS THE DESIGN — see `admin_v1.py` for the full argument. It is even starker here:
`_schema/vocabulary.yaml` records that of the shipped Layer 2 situation types exactly five are
domain-neutral and ZERO observation kinds are support-native. No ticket, no SLA clock, no CSAT,
no incident, no reopen. A support pack whose rules were restricted to what exists today would be
a sales pack wearing a support hat — which is the failure `planned_substrate` was written to
prevent, and it is worse than a gap because it looks like coverage.
"""

SUPPORT_V1 = {
    "id": "customer_support",        # the CORPUS domain id — see the module docstring
    "version": "1.0.1",             # 1.0.1: 1.0.0 was registered into a pack_registry from a
                                    #   PRE-REVIEW draft whose schema.fields still named
                                    #   `commitment.text`, `commitment.status` and `party.role` —
                                    #   three facts the L2 PIPELINE writes and the extractor must
                                    #   not be asked for. Published bytes are immutable by design
                                    #   (registry.py refuses a changed manifest under a used
                                    #   version), so the correction is a VERSION, not an edit;
                                    #   1.0.0 holds no tenant, no snapshot and no signal. Same
                                    #   convention as general_v1 1.3.0 -> 1.3.1.
    "requires": {"engine": ">=0.1.0"},

    # Identical to general_v1 / sales_v1 / admin_v1 on purpose: one shared org-wide daily budget
    # ranks every pack's cards against each other, so a divergent gate or band would decide ties
    # by scale instead of by merit.
    "scoring_defaults": {
        "weights": {"u": 45, "i": 35, "r": 20},
        "c_weights": {"conf": 50, "fresh": 30, "corr": 20},
        "corroboration": {"one": 60, "two": 85, "three_plus": 100, "rank3_full": True},
        "gate": {"s_min": 42, "c_min": 50},
        "budget_per_user_day": 15,
        "impact": {"i_floor": 55, "i_floor_scope": "deal_linked", "p90_default": 50000},
        "r_half_life": {"countdown_h": 24, "elapsed_h": 72},
        "bands": {"high": 52, "critical": 60},
    },

    "rules": [],
    "plays": {},
    "templates": {"_version": "cards.v2"},

    "schema": {
        # ONLY fields Layer 2 actually writes — cross-checked against
        # `_schema/vocabulary.yaml::substrate.fact_paths` and against `select distinct field from
        # graph_facts` on the live org. Nothing from `planned_substrate` appears here: `ticket.*`,
        # `sla.*`, `entitlement.*`, `csat.*` and `incident.*` have no writer, and
        # `field_vocabulary` would put every one of them in the extraction prompt, inviting the
        # model to invent an SLA target nobody agreed to. That is a Layer 2 build, named as one.
        #
        # The consequence is worth stating rather than hiding: on a correspondence-only tenant a
        # support case is read through the same substrate a relationship is — who wrote last,
        # whose turn it is, what was promised, how the exchange is trending. That is a real and
        # useful read, and it is a fraction of what a connected helpdesk would give.
        "fields": [
            # whose turn it is — for support this is the first-response question in the only
            # form the substrate can express it
            "thread.last_inbound", "thread.last_outbound", "thread.ball_in_court",
            # what was promised to the customer, and whether it has come due
            "commitment.due_at", "commitment.action",
            # a call or review that ended with something unresolved
            "meeting.status", "meeting.start_at", "meeting.end_at", "meeting.occurred",
            "meeting.attended", "meeting.external_counterparty", "meeting.open_loop",
            # who this person is to us, and in which direction the relationship runs — a
            # customer, a prospect and an investor asking the same question are three different
            # support cases
            "relationship.nature", "relationship.direction",
            "role", "company",
            # engine-computed, never extracted; `derived.sentiment` is the closest thing the
            # substrate has to a satisfaction signal and is deliberately not called one
            "derived.momentum", "derived.engagement", "derived.sentiment",
        ],
            # NOT declared, on purpose: `commitment.text`, `commitment.status` and `party.role`
            # are written by the L2 PIPELINE itself, not by the extractor. They are real facts and
            # a capability may read them off the node; naming them here would put them in the
            # extraction prompt and ask the model to invent a value the pipeline already owns —
            # and a model-written `commitment.status` would then race the pipeline's own write.

        # L2 situation types, for the same reason as admin_v1: the compiled lane's signal rule_id
        # is the capability id's last segment.
        "signal_vocab": ["support_case", "support_contact"],
    },

    "capture": {"classifier_hints": "customer support: a customer blocked or waiting — a reported "
                                    "problem, a promised fix, an unanswered question, an "
                                    "escalation"},
}
