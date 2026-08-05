"""sales pack v1.0.0 — DATA, not code. The engine reads this; it hardcodes nothing about
sales. Adding admin/finance later = a new pack like this one, zero engine change. Rules
read typed L2 facts only (whitelisted funcs); scoring_defaults feed L3's arithmetic; plays
declare the artifact + success signal for L5. Constants are HYPs (L6-calibratable via LVL3)."""

SALES_V1 = {
    "id": "sales",
    "version": "1.4.0",              # 1.3.0 derived-metric+cross-entity rules · 1.3.1 composite deal-health
                                      # · 1.4.0 moved 4 non-deal-specific rules out to packs/general_v1.py
    "requires": {"engine": ">=0.1.0"},

    # L3 scoring configuration (was hardcoded in the engine — now pack data)
    "scoring_defaults": {
        "weights": {"u": 45, "i": 35, "r": 20},              # S = C·(0.45U+0.35I+0.20R)
        "c_weights": {"conf": 50, "fresh": 30, "corr": 20},  # score.v0.3
        "corroboration": {"one": 60, "two": 85, "three_plus": 100, "rank3_full": True},
        "gate": {"s_min": 55, "c_min": 60},                  # c_min ≥ 50 guardrail
        "budget_per_user_day": 7,                            # ≤ 15 guardrail
        "impact": {"i_floor": 40, "i_floor_scope": "deal_linked", "p90_default": 50000},
        "r_half_life": {"countdown_h": 24, "elapsed_h": 72},
        # L5 band cuts (spec §5.11 Finding B — must be pack data, not engine constants). S<high
        # = standard, [high,critical) = high, ≥critical = critical. Small-deal tenants can't reach
        # critical (I floored at 50 → S_max 83); kept at 85, documented, tunable without a deploy.
        "bands": {"high": 70, "critical": 85},
    },

    "rules": [
        {"id": "stalled_deal", "level": "prescriptive", "scope": "deal",
         "when": [{"path": "deal.status", "op": "=", "value": "open"},
                  {"fn": "days_since", "path": "deal.last_inbound", "op": ">=", "value": 7}],
         "urgency": {"type": "elapsed", "path": "deal.last_inbound", "h": 3},
         "reason_code": "stalled_deal", "play": "follow_up", "cooldown_hours": 72,
         "linked_deal": True, "evidence_fields": ["deal.status", "deal.last_inbound"]},

        # commitment_overdue, unanswered_email, champion_quiet and meeting_no_followup moved to
        # packs/general_v1.py — they fire for ANY contact (not deal-linked by nature) and were
        # mislabeling every card "sales" regardless of who the contact was.

        # objection handling — a prospect raised a concern (L2 observation 'objection') and the
        # ball is still with us: the highest-leverage moment in a deal to respond specifically.
        {"id": "objection_open", "level": "prescriptive", "scope": "person",
         "when": [{"has_obs": "objection"},
                  {"path": "thread.ball_in_court", "op": "=", "value": "us"},
                  {"fn": "days_since", "path": "thread.last_inbound", "op": ">=", "value": 1}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 2},
         "reason_code": "objection_open", "play": "handle_objection", "cooldown_hours": 48,
         "linked_deal": True, "evidence_fields": ["thread.ball_in_court", "thread.last_inbound"]},

        # buying signal — budget/authority surfaced (L2 observation 'budget_approved'); advance the
        # deal while intent is hot. Opportunity, not a chore → different play than a follow-up.
        {"id": "buying_signal", "level": "prescriptive", "scope": "person",
         "when": [{"has_obs": "budget_approved"},
                  {"path": "thread.ball_in_court", "op": "=", "value": "us"}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 4},
         "reason_code": "buying_signal", "play": "advance_deal", "cooldown_hours": 72,
         "linked_deal": True, "evidence_fields": ["thread.last_inbound"]},

        # ── cross-signal / derived-metric rules (v1.3.0) — these read the DERIVED continuous signals
        # (momentum/engagement/sentiment) and the graph NEIGHBOURHOOD (edges/neighbour obs), which the
        # threshold-only rules above never could. This is the multi-hop, trajectory-aware layer. ──

        # cooling deal — a contact tied to a LIVE deal (neighbour has an open deal) whose two-way
        # interaction has thinned to half its prior fortnight. Predictive: the deal is losing heat
        # before anyone's gone formally silent. derived.engagement ≤ 0.5 = volume halved.
        {"id": "cooling_deal", "level": "predictive", "scope": "person",
         "when": [{"path": "derived.engagement", "op": "<=", "value": 0.5},
                  {"neighbor_fact": "deal.status", "op": "=", "value": "open"}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 6},
         "reason_code": "cooling_deal", "play": "re_engage", "cooldown_hours": 96,
         "linked_deal": True, "evidence_fields": ["derived.engagement", "thread.last_inbound"]},

        # single-threaded deal — an open deal with ≤1 relationship in the graph = key-person risk
        # (the whole deal rides one contact). Coarse threading proxy via edge_count; tunable.
        {"id": "single_threaded_deal", "level": "predictive", "scope": "deal",
         "when": [{"path": "deal.status", "op": "=", "value": "open"},
                  {"fn": "edge_count", "op": "<=", "value": 1}],
         "urgency": {"type": "elapsed", "path": "deal.last_inbound", "h": 8},
         "reason_code": "single_threaded_deal", "play": "multi_thread", "cooldown_hours": 168,
         "linked_deal": True, "evidence_fields": ["deal.status"]},

        # competitor in a live deal — a competitor was named in the account's comms (neighbour obs)
        # while the deal is still open. The moment to differentiate, before it's a lost-reason.
        {"id": "competitor_in_live_deal", "level": "predictive", "scope": "deal",
         "when": [{"path": "deal.status", "op": "=", "value": "open"},
                  {"neighbor_has_obs": "competitor"}],
         "urgency": {"type": "elapsed", "path": "deal.last_inbound", "h": 5},
         "reason_code": "competitor_in_live_deal", "play": "defend_position", "cooldown_hours": 120,
         "linked_deal": True, "evidence_fields": ["deal.status"]},

        # going dark after proposal — pricing was on the table (obs 'pricing_discussed'), the ball is
        # with THEM, and they've been silent past a few days. The classic post-quote stall.
        {"id": "going_dark_after_proposal", "level": "predictive", "scope": "person",
         "when": [{"has_obs": "pricing_discussed"},
                  {"path": "thread.ball_in_court", "op": "=", "value": "them"},
                  {"fn": "days_since", "path": "thread.last_inbound", "op": ">=", "value": 4}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 4},
         "reason_code": "going_dark_after_proposal", "play": "re_engage", "cooldown_hours": 96,
         "linked_deal": True, "evidence_fields": ["thread.ball_in_court", "thread.last_inbound"]},

        # deal sentiment turned negative — the qualitative balance on a contact tied to a live deal
        # is net-negative (more objections/competitor/pushback than positive intent). derived.sentiment.
        {"id": "deal_sentiment_negative", "level": "predictive", "scope": "person",
         "when": [{"path": "derived.sentiment", "op": "<=", "value": -0.34},
                  {"neighbor_fact": "deal.status", "op": "=", "value": "open"}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 6},
         "reason_code": "deal_sentiment_negative", "play": "re_engage", "cooldown_hours": 120,
         "linked_deal": True, "evidence_fields": ["derived.sentiment"]},
    ],

    # plays — the artifact L5 renders + the graph event that marks success (D8/D9). Read-only:
    # a play produces a draft/recap; it never sends. success_signal closes it (L3 lifecycle + D9).
    "plays": {
        "follow_up":          {"artifact": "draft_followup", "success_signal": "inbound_received", "window_days": 7},
        "re_engage":          {"artifact": "draft_reengage", "success_signal": "inbound_received", "window_days": 14},
        "handle_objection":   {"artifact": "draft_objection_reply", "success_signal": "outbound_sent", "window_days": 2},
        "advance_deal":       {"artifact": "draft_advance",  "success_signal": "outbound_sent",     "window_days": 3},
        "multi_thread":       {"artifact": "draft_multithread", "success_signal": "inbound_received", "window_days": 10},
        "defend_position":    {"artifact": "draft_competitive", "success_signal": "outbound_sent",    "window_days": 3},
        # composite (C3) — the deal-health verdict's play: address the biggest driver first.
        "review_deal":        {"artifact": "draft_deal_action", "success_signal": "outbound_sent",    "window_days": 3},
    },

    # L5 card templates — the third versioned input in card = f(signal, play, template). Each
    # reason_code gets: a render_hint (guides E1's one temp-0 call to fill headline/situation/
    # artifact) and a deterministic `fallback` (pure slot-interpolation from facts, no LLM) used
    # when the invention validator or length caps reject the model output. Fallbacks NEVER
    # invent — they only place fact-derived slots — so a card always ships, honest either way.
    "templates": {
        # manager mode — headline is a direct order (verb first, name who), never a passive fact.
        "_version": "cards.v2",
        "stalled_deal": {
            "artifact_kind": "draft_followup",
            "render_hint": ("Headline: a direct order to re-engage this deal today, naming who — "
                            "imperative voice, not a status line. Situation: what they last said, "
                            "the stage and $ value. Artifact: a warm 2-3 sentence re-engagement "
                            "email — no fluff, one clear ask."),
            "fallback": {"headline": "Re-engage {entity} today",
                         "situation": "Deal quiet {days}d · {stage} stage · {money}"}},
        "objection_open": {
            "artifact_kind": "draft_objection_reply",
            "render_hint": ("Headline: a direct order to handle this person's objection now, naming "
                            "them. Situation: what concern they raised, how long ago. Artifact: a "
                            "concise, empathetic reply that acknowledges the objection and moves the "
                            "deal forward."),
            "fallback": {"headline": "Handle {entity}'s objection now",
                         "situation": "Raised {days}d ago — still unanswered"}},
        "buying_signal": {
            "artifact_kind": "draft_advance",
            "render_hint": ("Headline: a direct order to advance the deal with this person now — "
                            "budget/authority surfaced, intent is hot. Situation: what signalled. "
                            "Artifact: a short note advancing to the next step (proposal or meeting) "
                            "while intent is hot."),
            "fallback": {"headline": "Advance the deal with {entity}",
                         "situation": "Budget signalled — move now while hot"}},
        "cooling_deal": {
            "artifact_kind": "draft_reengage",
            "render_hint": ("Headline: a direct order to re-engage this person — their deal is "
                            "cooling. Situation: how much the interaction has dropped. Artifact: a "
                            "light-touch, value-led check-in that revives the conversation."),
            "fallback": {"headline": "Re-engage {entity} — deal cooling",
                         "situation": "Two-way engagement halved on an open deal"}},
        "single_threaded_deal": {
            "artifact_kind": "draft_multithread",
            "render_hint": ("Headline: a direct order to widen the contacts on this deal — it rides "
                            "a single relationship, key-person risk. Situation: the deal, the lone "
                            "relationship. Artifact: a note that asks for an intro to another "
                            "stakeholder (procurement, exec sponsor)."),
            "fallback": {"headline": "Widen contacts on the {entity} deal",
                         "situation": "Only one relationship — key-person risk"}},
        "competitor_in_live_deal": {
            "artifact_kind": "draft_competitive",
            "render_hint": ("Headline: a direct order to defend position on this deal — a competitor "
                            "is in play. Situation: which account/deal, that a rival was named. "
                            "Artifact: a concise, non-defensive note that reinforces our unique "
                            "value — no bashing."),
            "fallback": {"headline": "Defend position on the {entity} deal",
                         "situation": "Rival named on an open deal — differentiate now"}},
        "going_dark_after_proposal": {
            "artifact_kind": "draft_reengage",
            "render_hint": ("Headline: a direct order to re-engage this person post-quote — they "
                            "went quiet after seeing pricing. Situation: how long since the "
                            "proposal/quote. Artifact: a warm nudge that lowers the cost of "
                            "replying — offer to answer questions or adjust scope."),
            "fallback": {"headline": "Re-engage {entity} post-quote",
                         "situation": "Silent {days}d since pricing shared"}},
        "deal_sentiment_negative": {
            "artifact_kind": "draft_reengage",
            "render_hint": ("Headline: a direct order to address concerns with this person — "
                            "sentiment on their deal has turned negative. Situation: that concerns "
                            "outweigh positive signals. Artifact: a note that surfaces and addresses "
                            "the concern directly."),
            "fallback": {"headline": "Address concerns with {entity}",
                         "situation": "Sentiment turned negative on an open deal"}},
        # composite deal-health verdict (C3) — the evidence chain here is the member reason_codes
        # (field='signal'), so the render composes them into ONE story instead of listing alerts.
        "deal_health": {
            "artifact_kind": "draft_deal_action",
            "render_hint": ("Headline: a direct order to review this deal now — ONE verdict that "
                            "composes the listed concern signals into a single story (e.g. \"Review "
                            "{entity} deal now — at risk: quiet + objection + competitor\") — do NOT "
                            "list them separately. Situation: the deal, its stage/value, and the "
                            "compound picture. Artifact: the single next-best-action that addresses "
                            "the biggest driver first."),
            "fallback": {"headline": "Review {entity} deal now",
                         "situation": "At risk: {concerns} · {stage} · {money}"}},
    },

    # L2 extraction whitelist + L1 hints (domain vocabulary lives here, not in the engine)
    "schema": {
        "fields": ["deal.status", "deal.last_inbound", "deal.value",
                   "thread.last_inbound", "thread.ball_in_court",
                   # derived continuous signals (engine-computed, not extracted) — declared so rules
                   # may cite them as evidence: momentum/engagement (trajectory) + sentiment (obs balance).
                   "derived.momentum", "derived.engagement", "derived.sentiment"],
        "signal_vocab": ["stalled_deal", "objection_open",
                         "buying_signal", "cooling_deal", "single_threaded_deal",
                         "competitor_in_live_deal", "going_dark_after_proposal",
                         "deal_sentiment_negative", "deal_health"],
    },
    "capture": {"classifier_hints": "sales: deals, pricing, proposals, demos, commitments, follow-ups"},
}
