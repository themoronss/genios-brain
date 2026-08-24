"""sales pack v1.0.0 — DATA, not code. The engine reads this; it hardcodes nothing about
sales. Adding admin/finance later = a new pack like this one, zero engine change. Rules
read typed L2 facts only (whitelisted funcs); scoring_defaults feed L3's arithmetic; plays
declare the artifact + success signal for L5. Constants are HYPs (L6-calibratable via LVL3)."""

SALES_V1 = {
    "id": "sales",
    "version": "1.11.0",             # 1.11.0: push bands calibrated to the live score
                                    #   distribution — 70/85 sat above the max reachable score,
                                    #   so no card ever pushed             # 1.10.0 staleness guard: timeline_slip/closed_lost_risk fire only when
                                      #   ball_in_court != them (missing_ok) — no "save now" after we've replied
                                      # 1.3.0 derived-metric+cross-entity rules · 1.3.1 composite deal-health
                                      # · 1.4.0 moved 4 non-deal-specific rules out to packs/general_v1.py
                                      # · 1.5.0 deep lifecycle corpus (pricing_objection, verbal_yes_not_closed,
                                      #   contract_requested, security_review_pending, champion_left, budget_freeze)
                                      #   + obs-kind normalizer · 1.6.0 +discount_pressure, legal_in_review,
                                      #   timeline_slip, demo_requested (18 rules) + enriched extraction vocab
                                      # · 1.8.0 L5 execution block: escalation ladder, reminder
                                      #   cadence, interruption budget — all tenant-tunable
    "requires": {"engine": ">=0.1.0"},

    # L3 scoring configuration (was hardcoded in the engine — now pack data)
    "scoring_defaults": {
        "weights": {"u": 45, "i": 35, "r": 20},              # S = C·(0.45U+0.35I+0.20R)
        "c_weights": {"conf": 50, "fresh": 30, "corr": 20},  # score.v0.3
        "corroboration": {"one": 60, "two": 85, "three_plus": 100, "rank3_full": True},
        "gate": {"s_min": 42, "c_min": 50},                  # c_min ≥ 50 guardrail; s_min lowered so
        #   real-but-lower-corroboration loops in a founder's own inbox (overdue commitments, quiet
        #   champions, deals to defend) surface instead of being cut with the low-value noise. The
        #   high-volume junk (a "send a recap" for every past meeting) still scores well under this.
        "budget_per_user_day": 15,                           # ≤ 15 guardrail — show the day's loops
        # i_floor is what a DEAL-LINKED rule scores when the deal's value is unknown.
        # 40 read the missing value as "assume a median deal" — but combined with the
        # gate it meant unknown-value deals could never clear s_min, i.e. the whole
        # no-CRM tenant saw nothing. Unknown is not small: the cost of missing a real
        # stalled deal dwarfs the cost of one extra card in a 7/day budget that is
        # ranked anyway. 55 = "assume it matters until we learn otherwise"; a known
        # value always overrides it. See tests/test_corpus_can_fire.py.
        "impact": {"i_floor": 55, "i_floor_scope": "deal_linked", "p90_default": 50000},
        "r_half_life": {"countdown_h": 24, "elapsed_h": 72},
        # L5 band cuts (spec §5.11 Finding B — must be pack data, not engine constants). S<high
        # = standard, [high,critical) = high, ≥critical = critical. Small-deal tenants can't reach
        # critical (I floored at 50 → S_max 83); kept at 85, documented, tunable without a deploy.
        # Calibrated to the LIVE score distribution (open signals: min 42, median 45.5, max 56),
        # not to aspiration. The old {high: 70, critical: 85} sat ABOVE the maximum reachable
        # score, so `high` was arithmetically unreachable, no card ever cleared the push band,
        # and the entire delivery layer ran with an empty input for months while reading as
        # healthy. 52/60 makes push a real, rare event (top quartile / exceptional) — bounded by
        # the 7/day budget, quiet hours and the interrupt-confidence floor, so miscalibration
        # costs a notification, not a 2am page. Revisit when the L4 formula takes scoring
        # authority from the override and the distribution widens.
        "bands": {"high": 52, "critical": 60},

        # L5 Executive Engine — how a recommendation becomes a tracked commitment. Pack DATA, so
        # a tenant retunes escalation and interruption through LVL2/LVL3 merge, pins and
        # guardrails like everything else here; the engine ships identical defaults so an
        # untuned pack behaves exactly as if this block were absent.
        "execution": {
            "planning": {
                # How soon the FIRST action is due, by urgency band. Urgency shapes when work
                # starts; the play's window_days shapes when it must finish. Conflating them is
                # how a fortnight-long commitment ends up demanded by this afternoon.
                "first_action_hours": {"critical": 4, "high": 24, "standard": 72},
                "max_actions": 12,
            },
            "communication": {
                # Interruption is a budget, not a feature. Raising interrupt_band to 'critical'
                # is the one dial to reach for when a tenant says "too noisy".
                "interrupt_band": "critical",
                "push_band": "high",
                # A 92-score conclusion the reasoner is 40% sure of should arrive calmly.
                "interrupt_min_confidence_bp": 6_000,
            },
            "escalation": {
                # Days from creation, not from the deadline: the useful intervention is early.
                # Scaled by band — critical work runs the same ladder at half the delay.
                "ladder": [
                    {"day": 1, "action": "notify", "audience": "owner", "interrupt": False},
                    {"day": 3, "action": "remind", "audience": "owner", "interrupt": True},
                    {"day": 7, "action": "escalate", "audience": "manager", "interrupt": False},
                    {"day": 14, "action": "critical", "audience": "executive",
                     "interrupt": True},
                ],
                "band_multiplier_bp": {"critical": 5_000, "high": 7_500, "standard": 10_000},
            },
            "reminder": {
                "min_interval_hours": 20,   # never twice inside a working day
                "max_reminders": 4,         # then escalation owns it — a fifth nudge gets muted
                "untouched_hours": 24,
                "deadline_warning_bp": 7_500,   # three quarters of the window burned
            },
            "monitor": {"stall_bp": 3_000, "stall_floor_hours": 12},
        },
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

        # ── deep lifecycle rules (v1.5.0) — obs-driven, deterministic via the L2 obs-kind normalizer
        #    (context.pipeline.norm_obs_kind). Person-scoped: fire on the contact, no CRM edges
        #    needed, so they work the day extraction runs. Full sales lifecycle coverage. ──

        # pricing objection — a price concern is on the table and the ball is with us: the moment to
        # respond specifically, before it becomes a lost-reason.
        {"id": "pricing_objection", "level": "prescriptive", "scope": "person",
         "when": [{"has_obs": "objection_price"},
                  {"path": "thread.ball_in_court", "op": "=", "value": "us"}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 2},
         "reason_code": "pricing_objection", "play": "handle_objection", "cooldown_hours": 48,
         "linked_deal": True, "evidence_fields": ["thread.ball_in_court", "thread.last_inbound"]},

        # verbal yes, not closed — they signalled a yes / next step but nothing's been sent to lock
        # it. Close the loop while intent is hot.
        {"id": "verbal_yes_not_closed", "level": "prescriptive", "scope": "person",
         "when": [{"has_obs": "verbal_yes"},
                  {"path": "thread.ball_in_court", "op": "=", "value": "us"}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 3},
         "reason_code": "verbal_yes_not_closed", "play": "advance_deal", "cooldown_hours": 72,
         "linked_deal": True, "evidence_fields": ["thread.ball_in_court", "thread.last_inbound"]},

        # contract requested — they asked for the contract / MSA / order form. Highest-intent signal
        # in the pipeline: send it today.
        {"id": "contract_requested", "level": "prescriptive", "scope": "person",
         "when": [{"has_obs": "contract_requested"},
                  {"path": "thread.ball_in_court", "op": "=", "value": "us"}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 2},
         "reason_code": "contract_requested", "play": "advance_deal", "cooldown_hours": 48,
         "linked_deal": True, "evidence_fields": ["thread.ball_in_court", "thread.last_inbound"]},

        # security review pending — a security questionnaire / vendor review is the gate; a stalled
        # review kills more deals than price. Keep it moving.
        {"id": "security_review_pending", "level": "prescriptive", "scope": "person",
         "when": [{"has_obs": "security_review_started"},
                  {"fn": "days_since", "path": "thread.last_inbound", "op": ">=", "value": 3}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 4},
         "reason_code": "security_review_pending", "play": "follow_up", "cooldown_hours": 96,
         "linked_deal": True, "evidence_fields": ["thread.last_inbound"]},

        # champion changed / left — the person driving the deal is moving on. Re-thread to another
        # stakeholder before the deal loses its internal sponsor.
        {"id": "champion_left", "level": "predictive", "scope": "person",
         "when": [{"has_obs": "champion_change"}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 6},
         "reason_code": "champion_left", "play": "multi_thread", "cooldown_hours": 168,
         "linked_deal": True, "evidence_fields": ["thread.last_inbound"]},

        # budget freeze — spending is on hold. Don't push; nurture so we're first when it thaws.
        # Slow-burn (long half-life) + long cooldown — a heads-up, not a nag.
        {"id": "budget_freeze", "level": "predictive", "scope": "person",
         "when": [{"has_obs": "budget_freeze"}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 12, "slow": True},
         "reason_code": "budget_freeze", "play": "re_engage", "cooldown_hours": 240,
         "linked_deal": True, "evidence_fields": ["thread.last_inbound"]},

        # discount pressure — they're pushing on price and the ball is with us. Hold margin: respond
        # with value + a considered concession path, not a reflex discount.
        {"id": "discount_pressure", "level": "prescriptive", "scope": "person",
         "when": [{"has_obs": "discount_pressure"},
                  {"path": "thread.ball_in_court", "op": "=", "value": "us"}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 3},
         "reason_code": "discount_pressure", "play": "handle_objection", "cooldown_hours": 72,
         "linked_deal": True, "evidence_fields": ["thread.ball_in_court", "thread.last_inbound"]},

        # legal in review — the contract sits with legal/redlines and it's gone quiet. A silent legal
        # cycle is where deals die slowly; check in and offer to unblock.
        {"id": "legal_in_review", "level": "prescriptive", "scope": "person",
         "when": [{"has_obs": "legal_review"},
                  {"fn": "days_since", "path": "thread.last_inbound", "op": ">=", "value": 3}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 5},
         "reason_code": "legal_in_review", "play": "follow_up", "cooldown_hours": 120,
         "linked_deal": True, "evidence_fields": ["thread.last_inbound"]},

        # timeline slip — they signalled the timeline is moving. Re-anchor the plan before the deal
        # loses urgency and slips a quarter.
        {"id": "timeline_slip", "level": "predictive", "scope": "person",
         "when": [{"has_obs": "timeline_slip"},
                  {"path": "thread.ball_in_court", "op": "!=", "value": "them", "missing_ok": True}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 8, "slow": True},
         "reason_code": "timeline_slip", "play": "re_engage", "cooldown_hours": 168,
         "linked_deal": True, "evidence_fields": ["thread.last_inbound"]},

        # demo requested — they asked to see it and the ball is with us. Speed-to-demo wins deals;
        # book it now.
        {"id": "demo_requested", "level": "prescriptive", "scope": "person",
         "when": [{"has_obs": "demo_requested"},
                  {"path": "thread.ball_in_court", "op": "=", "value": "us"}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 2},
         "reason_code": "demo_requested", "play": "advance_deal", "cooldown_hours": 48,
         "linked_deal": True, "evidence_fields": ["thread.ball_in_court", "thread.last_inbound"]},

        # proposal sent, no response — a proposal went out, the ball is with them, and they've gone
        # quiet. The single most common place deals stall (distinct trigger from pricing going dark).
        {"id": "proposal_no_response", "level": "prescriptive", "scope": "person",
         "when": [{"has_obs": "proposal_sent"},
                  {"path": "thread.ball_in_court", "op": "=", "value": "them"},
                  {"fn": "days_since", "path": "thread.last_inbound", "op": ">=", "value": 4}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 4},
         "reason_code": "proposal_no_response", "play": "re_engage", "cooldown_hours": 96,
         "linked_deal": True, "evidence_fields": ["thread.ball_in_court", "thread.last_inbound"]},

        # closed-lost risk — they hinted the deal may be lost / going with someone else. Last chance
        # to save it with a direct, specific save play before it's gone.
        {"id": "closed_lost_risk", "level": "predictive", "scope": "person",
         "when": [{"has_obs": "closed_lost_mention"},
                  {"path": "thread.ball_in_court", "op": "!=", "value": "them", "missing_ok": True}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 4},
         "reason_code": "closed_lost_risk", "play": "defend_position", "cooldown_hours": 120,
         "linked_deal": True, "evidence_fields": ["thread.last_inbound"]},
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
        # ── deep lifecycle templates (v1.5.0) ──
        "pricing_objection": {
            "artifact_kind": "draft_objection_reply",
            "render_hint": ("Headline: a direct order to answer {entity}'s price concern now, "
                            "naming them. Situation: the price objection they raised, how long "
                            "unanswered. Artifact: a concise reply that reframes value (not just "
                            "discounts), acknowledges the concern, and proposes a next step."),
            "fallback": {"headline": "Answer {entity}'s price concern now",
                         "situation": "Price objection open — ball with you"}},
        "verbal_yes_not_closed": {
            "artifact_kind": "draft_advance",
            "render_hint": ("Headline: a direct order to lock the deal with {entity} — they said "
                            "yes but nothing's been sent. Situation: what they agreed to. Artifact: "
                            "a short note that sends the concrete next step (order form / kickoff / "
                            "contract) to convert the verbal yes."),
            "fallback": {"headline": "Lock the deal with {entity}",
                         "situation": "Verbal yes — nothing sent to close it yet"}},
        "contract_requested": {
            "artifact_kind": "draft_advance",
            "render_hint": ("Headline: a direct order to send {entity} the contract today — highest "
                            "intent. Situation: they asked for the contract/MSA/order form. "
                            "Artifact: a brief covering note to send with the agreement, restating "
                            "terms and the path to signature."),
            "fallback": {"headline": "Send {entity} the contract today",
                         "situation": "They asked for it — don't stall the close"}},
        "security_review_pending": {
            "artifact_kind": "draft_followup",
            "render_hint": ("Headline: a direct order to unblock {entity}'s security review. "
                            "Situation: the review is the gate, quiet {days}d. Artifact: a note "
                            "offering the security package (SOC2/DPA/questionnaire) and a named "
                            "point of contact to keep it moving."),
            "fallback": {"headline": "Unblock {entity}'s security review",
                         "situation": "Review is the gate — quiet {days}d"}},
        "champion_left": {
            "artifact_kind": "draft_multithread",
            "render_hint": ("Headline: a direct order to re-thread the {entity} deal — the champion "
                            "is moving on. Situation: the sponsor change, the key-person risk. "
                            "Artifact: a warm note asking the outgoing champion for a handover intro "
                            "to their successor / another stakeholder."),
            "fallback": {"headline": "Re-thread the {entity} deal now",
                         "situation": "Champion moving on — secure a new sponsor"}},
        "budget_freeze": {
            "artifact_kind": "draft_reengage",
            "render_hint": ("Headline: a direct order to nurture {entity} through the budget freeze "
                            "— stay top-of-mind, don't push. Situation: spending on hold. Artifact: "
                            "a light, value-led touch (a relevant resource / a check-in on the thaw "
                            "date) that keeps us first in line, no hard ask."),
            "fallback": {"headline": "Nurture {entity} through the freeze",
                         "situation": "Budget on hold — stay first in line"}},
        "discount_pressure": {
            "artifact_kind": "draft_objection_reply",
            "render_hint": ("Headline: a direct order to answer {entity}'s discount push without "
                            "caving. Situation: they're pressing on price. Artifact: a reply that "
                            "reframes value first, then offers a considered trade (term/scope) if a "
                            "concession is warranted — never a reflex discount."),
            "fallback": {"headline": "Answer {entity}'s price push — hold margin",
                         "situation": "Discount pressure — reframe value first"}},
        "legal_in_review": {
            "artifact_kind": "draft_followup",
            "render_hint": ("Headline: a direct order to unblock the {entity} contract in legal. "
                            "Situation: it's with legal/redlines and quiet {days}d. Artifact: a "
                            "check-in offering to jump on a call with their legal, or a clause "
                            "summary, to keep the paper moving."),
            "fallback": {"headline": "Unblock {entity}'s contract in legal",
                         "situation": "With legal — quiet {days}d"}},
        "timeline_slip": {
            "artifact_kind": "draft_reengage",
            "render_hint": ("Headline: a direct order to re-anchor the {entity} timeline. Situation: "
                            "they signalled the date is moving. Artifact: a note that reconfirms the "
                            "value of moving now and proposes a concrete revised milestone, so the "
                            "deal keeps urgency."),
            "fallback": {"headline": "Re-anchor the {entity} timeline",
                         "situation": "Timeline slipping — reset the plan"}},
        "demo_requested": {
            "artifact_kind": "draft_advance",
            "render_hint": ("Headline: a direct order to get {entity} into a demo now — speed-to-demo "
                            "wins. Situation: they asked to see it, ball with you. Artifact: a short "
                            "note offering two concrete slots and what the demo will cover for their "
                            "use-case."),
            "fallback": {"headline": "Book {entity}'s demo now",
                         "situation": "They asked to see it — move fast"}},
        "proposal_no_response": {
            "artifact_kind": "draft_reengage",
            "render_hint": ("Headline: a direct order to chase {entity} on the sent proposal — "
                            "they've gone quiet. Situation: proposal out, silent {days}d. Artifact: "
                            "a low-friction nudge that offers to walk through it or adjust scope, "
                            "making it easy to reply."),
            "fallback": {"headline": "Chase {entity} on the proposal",
                         "situation": "Proposal sent — quiet {days}d"}},
        "closed_lost_risk": {
            "artifact_kind": "draft_competitive",
            "render_hint": ("Headline: a direct order to save the {entity} deal now — they hinted "
                            "it may be going elsewhere. Situation: the loss signal. Artifact: a "
                            "direct, non-desperate save note that reopens the conversation on the "
                            "one thing that would change their decision."),
            "fallback": {"headline": "Save the {entity} deal now",
                         "situation": "Loss signal — one last specific save"}},
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
                         "deal_sentiment_negative", "deal_health",
                         "pricing_objection", "verbal_yes_not_closed", "contract_requested",
                         "security_review_pending", "champion_left", "budget_freeze",
                         "discount_pressure", "legal_in_review", "timeline_slip", "demo_requested",
                         "proposal_no_response", "closed_lost_risk"],
    },
    "capture": {"classifier_hints": "sales: deals, pricing, proposals, demos, commitments, follow-ups"},
}


# ── Actionability: what each card's ACTION needs, distinct from what its RULE matched on ──
#
# An undeclared reason code fails CLOSED (see reason/actionability.py). This block is the only
# place that keeps a new rule from silently shipping a confident imperative it cannot ground:
# adding a rule below without adding an entry here is a named test failure, not a surprise in
# production three weeks later.
SALES_V1_ACTIONABILITY = {

    "stalled_deal": {
        "facts": ['deal.stage', 'deal.value', 'thread.last_inbound'],
        "obs": ['next_step_agreed', 'proposal_sent', 'question'],
        "label": 'what the deal was last waiting on',
        "message": "The deal has gone quiet, but we don't have the last open item on record.",
        "recommended": 'Open the thread to see where it stopped before re-engaging.'},
    "objection_open": {
        "facts": ['derived.objection'],
        "obs": ['objection', 'pricing_objection', 'question'],
        "label": 'the objection itself',
        "message": 'We can see the deal stalled after pushback, but not what the pushback was.',
        "recommended": 'Open the thread and read the objection before answering it.'},
    "buying_signal": {
        "obs": ['demo_requested', 'contract_requested', 'proposal_sent', 'next_step_agreed', 'question'],
        "label": 'what they actually asked for',
        "message": "Their reply reads as intent, but we haven't captured the specific ask.",
        "recommended": "Open the email to see what they're asking for before advancing."},
    "cooling_deal": {
        "facts": ['derived.engagement', 'thread.last_inbound'],
        "obs": ['next_step_agreed', 'proposal_sent'],
        "label": 'what to re-engage them about',
        "message": "Engagement is falling, but we don't have an open thread to reopen.",
        "recommended": 'Review the account history before reaching out.'},
    "single_threaded_deal": {
        "facts": ['deal.stage', 'company'],
        "obs": ['next_step_agreed'],
        "label": 'who else is on the account',
        "message": "Only one contact is engaged, but we don't know enough about the account to name a second.",
        "recommended": 'Check the account for other stakeholders before multi-threading.'},
    "competitor_in_live_deal": {
        "facts": ['derived.competitor'],
        "obs": ['competitor_mentioned', 'objection'],
        "label": 'which competitor and on what',
        "message": "A competitor came up, but we haven't captured which one or what they're being compared on.",
        "recommended": 'Open the thread to see the comparison before defending.'},
    "going_dark_after_proposal": {
        "facts": ['deal.stage'],
        "obs": ['proposal_sent', 'next_step_agreed'],
        "label": 'what was proposed',
        "message": "They stopped replying after a proposal we don't have on record.",
        "recommended": 'Open the proposal thread before following up.'},
    "deal_sentiment_negative": {
        "facts": ['derived.sentiment', 'thread.last_inbound'],
        "obs": ['objection', 'competitor_mentioned'],
        "label": 'what turned it negative',
        "message": 'Sentiment dropped, but not what caused it.',
        "recommended": 'Read the recent exchange before responding.'},
    "pricing_objection": {
        "facts": ['derived.objection'],
        "obs": ['pricing_objection', 'objection'],
        "label": 'the pricing pushback',
        "message": "Price came up as a blocker, but we haven't captured the specific concern.",
        "recommended": 'Open the thread and read what they said about price.'},
    "verbal_yes_not_closed": {
        "obs": ['verbal_yes', 'next_step_agreed', 'contract_requested'],
        "label": 'what they agreed to',
        "message": 'Something reads like agreement, but not what was agreed.',
        "recommended": 'Confirm the scope in the thread before sending paperwork.'},
    "contract_requested": {
        "obs": ['contract_requested', 'next_step_agreed'],
        "label": 'which contract they asked for',
        "message": "They asked for paperwork; we haven't captured which terms.",
        "recommended": 'Open the request before sending a contract.'},
    "security_review_pending": {
        "facts": ['thread.last_inbound'],
        "obs": ['security_review', 'question'],
        "label": 'what security asked for',
        "message": "A security review is open, but not what it's blocked on.",
        "recommended": 'Open the review thread to see the outstanding items.'},
    "champion_left": {
        "facts": ['company', 'deal.stage'],
        "obs": ['champion_left'],
        "label": 'who replaces them',
        "message": "Your contact has moved on and we don't have a successor on the account.",
        "recommended": 'Find the new owner before re-opening the deal.'},
    "budget_freeze": {
        "facts": ['thread.last_inbound'],
        "obs": ['budget_freeze', 'objection'],
        "label": 'the scope of the freeze',
        "message": 'Budget is frozen, but not for how long or over what.',
        "recommended": 'Read the thread to see when it reopens before re-engaging.'},
    "discount_pressure": {
        "obs": ['discount_pressure', 'pricing_objection', 'objection'],
        "label": 'what discount was asked for',
        "message": "They're pushing on price without a captured number.",
        "recommended": 'Open the thread to see what they asked for.'},
    "legal_in_review": {
        "facts": ['thread.last_inbound'],
        "obs": ['legal_review', 'question'],
        "label": 'what legal is holding',
        "message": "Legal has it, but we don't have the open redlines.",
        "recommended": 'Check the review thread for the outstanding clauses.'},
    "timeline_slip": {
        "facts": ['deal.close_date'],
        "obs": ['timeline_slip', 'next_step_agreed'],
        "label": 'which date moved',
        "message": "The timeline slipped, but we don't have the original or the new date.",
        "recommended": 'Confirm the dates in the thread before pushing.'},
    "demo_requested": {
        "obs": ['demo_requested', 'meeting_request'],
        "label": 'what they want to see',
        "message": 'They asked for a demo without a captured agenda.',
        "recommended": 'Open the request to see what they want covered.'},
    "proposal_no_response": {
        "facts": ['deal.stage'],
        "obs": ['proposal_sent'],
        "label": 'what was proposed',
        "message": "A proposal is outstanding that we don't have on record.",
        "recommended": 'Open the proposal before chasing it.'},
    "closed_lost_risk": {
        "facts": ['derived.sentiment', 'deal.stage'],
        "obs": ['objection', 'competitor_mentioned', 'budget_freeze'],
        "label": "why it's slipping",
        "message": "This deal is at risk, but we haven't captured the reason.",
        "recommended": 'Read the recent thread before trying to save it.'},
}
