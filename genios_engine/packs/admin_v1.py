"""admin pack v1.0.0 — DATA, not code. The authority lane for the Admin domain.

WHY THIS FILE EXISTS, and why it carries no rules.

`ReasoningStore.persist_complete` (reason/store.py:928) refuses a write unless the config
snapshot's `pack_id` equals the capability's `domain`. `_tenant_pack` resolves that snapshot from
`tenant_packs`, and only two pack modules existed — `general_v1` and `sales_v1`. So every one of
the 57 authored Admin capabilities died at `domain_shadow.py:387` under `no_tenant_pack` and
emitted nothing, however well written. The corpus was not being judged and rejected; it was never
looked at. This module is the missing lane.

`rules: []` IS THE DESIGN, not an unfinished edge.

  1. The Admin lane's rules are its CAPABILITIES. The compiled Layer 3 brain reads the corpus,
     reasons over it and emits a signal whose `rule_id` is the situation type. A pack rule here
     would be a second, dumber brain competing for the same cards.
  2. The org-wide daily signal budget is SHARED (`runner._budget_used` counts every signal
     regardless of pack). `general_v1` already owns relationship hygiene for ANY contact —
     overdue promises, unanswered mail, quiet contacts, meetings with no follow-up. Restating any
     of those here would emit a duplicate card under a second `pack_id` for the same node, and
     spend the shared budget twice to say one thing.
  3. Everything that is genuinely ADMIN-native — an approval sitting past its threshold, a
     statutory filing due, an invoice that does not match its PO, an unreturned laptop — rests on
     facts Layer 2 does not write. `_schema/vocabulary.yaml::planned_substrate` lists 25 such
     situation types and 38 such fact paths, every one of them emitted by nothing. A rule written
     against them would be unfireable by construction, which is the exact dishonesty
     `planned_substrate` exists to prevent. It is a Layer 2 gap, and it is named as one.

So this pack grants authority and declares vocabulary. It does not pretend to reason.
"""

ADMIN_V1 = {
    "id": "admin",                   # MUST equal the corpus domain id ("Admin Expertise"/
                                    # domain.yaml identity.id) — persist_complete compares the
                                    # config snapshot's pack_id against the capability's domain.
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

    # Deliberately IDENTICAL to general_v1 / sales_v1. Cards from every pack are ranked against
    # each other inside one shared 7/day budget, so a different gate or a different band here
    # would silently make Admin cards win (or lose) every tie on scale alone rather than on
    # merit. Divergence has to be earned by evidence from a live distribution; there is none yet.
    "scoring_defaults": {
        "weights": {"u": 45, "i": 35, "r": 20},
        "c_weights": {"conf": 50, "fresh": 30, "corr": 20},
        "corroboration": {"one": 60, "two": 85, "three_plus": 100, "rank3_full": True},
        "gate": {"s_min": 42, "c_min": 50},
        "budget_per_user_day": 15,
        # `i_floor_scope: deal_linked` is kept even though nothing here is deal-linked: the floor
        # then applies to nothing and an Admin signal's impact is whatever the reasoner measured.
        # An unconditional floor would give every administrative obligation the same impact as a
        # stalled deal of unknown value, which is the one thing that would make the shared queue
        # dishonest.
        "impact": {"i_floor": 55, "i_floor_scope": "deal_linked", "p90_default": 50000},
        "r_half_life": {"countdown_h": 24, "elapsed_h": 72},
        "bands": {"high": 52, "critical": 60},
    },

    # See the module docstring. An empty list is a statement, and it is checked by a named test
    # (tests/test_admin_support_packs.py) so it cannot be quietly filled with a duplicate of
    # general_v1's relationship hygiene.
    "rules": [],
    "plays": {},

    # The compiled lane carries its OWN copy: `capability_resolver` collects the situation's
    # `render` block into the plan, `card_builder` (line 349) reads `signal["capability_render"]`
    # FIRST and only falls through to `effective["templates"]` for a legacy signal. With no legacy
    # rules there is nothing to template. `_version` stays because card_builder stamps
    # `cards.template_version` from it regardless of which copy won.
    "templates": {"_version": "cards.v2"},

    "schema": {
        # ONLY fields Layer 2 actually writes. Cross-checked twice: against
        # `_schema/vocabulary.yaml::substrate.fact_paths` (whose provenance is the three real
        # producers — ENGINE_FIELDS, the shipped packs, and the L2 pipeline's direct writes), and
        # against `select distinct field from graph_facts` on the design partner's live org.
        #
        # This list is not decoration. `context/extract/vocab.py::field_vocabulary` unions every
        # pack's `schema.fields` into the L2 EXTRACTION PROMPT, so a field named here is a field
        # the model is told to go and find. Naming `approval.state` or `filing.due_at` — both of
        # which the Admin corpus would dearly like — would invite the model to invent a plausible
        # value for a fact nobody stated. Every one of the entries below already has a writer, so
        # this pack adds zero new extraction surface: the union is unchanged the day it ships.
        "fields": [
            # the administrative atom: an obligation with an owner and a date
            "commitment.due_at", "commitment.action",
            # whose turn it is, and when either side last moved — the only reliable read of an
            # open administrative loop on a correspondence-only tenant
            "thread.last_inbound", "thread.last_outbound", "thread.ball_in_court",
            # meetings, including the five fields `meeting.status` may no longer stand in for
            "meeting.status", "meeting.start_at", "meeting.end_at", "meeting.scheduled",
            "meeting.occurred", "meeting.attended", "meeting.external_counterparty",
            "meeting.open_loop",
            # what the counterparty IS to us — an administrative counterparty is not a buyer
            "relationship.nature", "relationship.direction",
            # legacy flat names, still written by the pipeline and still read
            "role", "company",
            # engine-computed, never extracted (field_vocabulary strips `derived.*` from the
            # prompt); declared so a capability may cite them as evidence
            "derived.momentum", "derived.engagement", "derived.sentiment",
        ],
            # NOT declared, on purpose: `commitment.text`, `commitment.status` and `party.role`
            # are written by the L2 PIPELINE itself, not by the extractor. They are real facts and
            # a capability may read them off the node; naming them here would put them in the
            # extraction prompt and ask the model to invent a value the pipeline already owns —
            # and a model-written `commitment.status` would then race the pipeline's own write.

        # The reason codes this pack's lane emits. For a compiled-brain pack these are the L2
        # SITUATION TYPES, because `_emit_capability_signal` derives a signal's rule_id from the
        # capability id's last segment (`expertise.account_admin` -> `account_admin`) — the
        # delivery authority predicate re-derives it the same way.
        "signal_vocab": ["account_admin", "admin_contact"],
    },

    # Feeds the L2 extraction prompt's domain note (`extract/vocab.py::classifier_hints`). The L1
    # keyword gate is a separate, deterministic thing (`capture/domain/hints.py`) and is not
    # changed by this pack.
    "capture": {"classifier_hints": "admin: obligations with a deadline and an owner — approvals, "
                                    "filings, renewals, invoices, records, access and assets"},
}
