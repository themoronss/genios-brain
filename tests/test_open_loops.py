"""L2-16: completion closes ONE request, never a person.

`thread.ball_in_court` was the entire completion authority — one bit per human — so answering
any of somebody's three questions read as answering all of them, and a card expiring was
indistinguishable from the request resolving. The ledger gives each request its own row.
"""
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, text  # noqa: E402

from genios_engine.context.open_loops import (  # noqa: E402
    close_loops_for_reply,
    open_loop_counts,
    record_ask,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("""
            create table open_loops (
                org_id text not null, loop_id text not null,
                subject_node_id text not null, kind text not null, thread_id text,
                status text not null default 'open',
                opened_at timestamp not null, last_seen_at timestamp not null,
                ask_count int not null default 1, opened_by_event text not null,
                closed_at timestamp, closed_by_event text,
                primary key (org_id, loop_id))"""))
    with engine.begin() as c:
        yield c


def test_a_repeat_ask_is_the_same_loop_not_a_second_one(conn):
    a = record_ask(conn, org_id="o", subject_node_id="n1", kind="question",
                   thread_id="t1", event_id="e1", at=NOW)
    b = record_ask(conn, org_id="o", subject_node_id="n1", kind="question",
                   thread_id="t1", event_id="e2", at=NOW + timedelta(days=1))
    assert a == b
    row = conn.execute(text("select ask_count, status from open_loops")).one()
    assert row.ask_count == 2 and row.status == "open"


def test_our_reply_closes_only_that_threads_loops(conn):
    """Answering ONE conversation must not mark every other conversation answered."""
    record_ask(conn, org_id="o", subject_node_id="n1", kind="question",
               thread_id="t1", event_id="e1", at=NOW)
    record_ask(conn, org_id="o", subject_node_id="n1", kind="demo_requested",
               thread_id="t2", event_id="e2", at=NOW)
    closed = close_loops_for_reply(conn, org_id="o", subject_node_id="n1",
                                   thread_id="t1", event_id="e3", at=NOW + timedelta(hours=1))
    assert closed == 1
    assert open_loop_counts(conn, "o") == {"n1": 1}      # t2's demo ask is still open


def test_asking_again_after_our_answer_reopens_the_loop(conn):
    """Their asking again is direct evidence our answer did not resolve it."""
    record_ask(conn, org_id="o", subject_node_id="n1", kind="question",
               thread_id="t1", event_id="e1", at=NOW)
    close_loops_for_reply(conn, org_id="o", subject_node_id="n1",
                          thread_id="t1", event_id="e2", at=NOW + timedelta(hours=1))
    assert open_loop_counts(conn, "o") == {}
    record_ask(conn, org_id="o", subject_node_id="n1", kind="question",
               thread_id="t1", event_id="e3", at=NOW + timedelta(hours=2))
    assert open_loop_counts(conn, "o") == {"n1": 1}


def test_a_reply_cannot_answer_a_question_not_yet_asked(conn):
    record_ask(conn, org_id="o", subject_node_id="n1", kind="question",
               thread_id="t1", event_id="e1", at=NOW + timedelta(days=1))
    closed = close_loops_for_reply(conn, org_id="o", subject_node_id="n1",
                                   thread_id="t1", event_id="e2", at=NOW)
    assert closed == 0


def test_a_threadless_ask_closes_on_any_direct_reply(conn):
    """A person-wide loop has no conversation identity — a direct reply to that person is the
    best completion evidence it can ever have."""
    record_ask(conn, org_id="o", subject_node_id="n1", kind="question",
               thread_id=None, event_id="e1", at=NOW)
    closed = close_loops_for_reply(conn, org_id="o", subject_node_id="n1",
                                   thread_id="t9", event_id="e2", at=NOW + timedelta(hours=1))
    assert closed == 1


def test_the_regeneration_gate_defers_to_the_ledger_for_ask_rules():
    """An OPEN loop with no new evidence is exactly the case that SHOULD re-surface — they
    asked, we never answered, silence is not resolution. The ledger going quiet on our reply is
    what stops an ANSWERED ask from returning."""
    import inspect

    from genios_engine.reason import runner

    assert "unanswered_email" in runner._LOOP_GATED_REASON_CODES
    src = inspect.getsource(runner.run)
    assert "loop_still_open" in src
    assert "open_loop_counts" in src


# ── L2-01: the situation is pack-readable, not just engine-attached ─────────────
def test_situation_fields_enter_the_fact_envelope_rules_already_read():
    """`ctx.situation` served two hardcoded consumers (dormancy suppress, confidence
    pass-through). As facts, the PACK can consume the substrate: an author writes
    `{"path": "situation.status", ...}` in rule data with zero engine change — the actual
    "flip the consumer" the audit asked for."""
    import inspect

    from genios_engine.reason import runner

    src = inspect.getsource(runner.run)
    for field in ("situation.status", "situation.type", "situation.confidence",
                  "situation.coverage"):
        assert f'"{field}"' in src
    # setdefault, never overwrite: a captured fact outranks a derived mirror
    assert "ctx.facts.setdefault(_field" in src


# ── the two live-data defects the local end-to-end caught ───────────────────────
def test_a_relationship_must_exist_before_it_can_be_at_risk():
    """`ball_in_court != them, missing_ok` narrows a population; on its own it also passes for
    every person we have never exchanged a message with. That is how `hello@forumvc.com` — a
    newsletter sender — got "Save the deal now" at CRITICAL band on the design partner's real
    inbox. The same fact is the rule's own urgency clock: without it, elapsed time was being
    computed from nothing."""
    from genios_engine.packs.sales_v1 import SALES_V1

    for rule_id in ("closed_lost_risk", "timeline_slip"):
        rule = next(r for r in SALES_V1["rules"] if r["id"] == rule_id)
        guarded = [c for c in rule["when"] if c.get("present") == "thread.last_inbound"]
        assert guarded, f"{rule_id} can fire on a stranger"
        # and the guard names the very fact the urgency clock reads
        assert rule["urgency"]["path"] == "thread.last_inbound"


def test_the_present_operator_distinguishes_absent_from_permitted():
    """`missing_ok` makes an absent fact PASS a negative check — correct for narrowing, wrong as
    a rule's only gate. `present` is the positive counterpart."""
    from datetime import datetime, timezone

    from genios_engine.reason.engine import NodeContext, evaluate
    from genios_engine.reason.rules import rule_from_dict

    rule = rule_from_dict({
        "id": "t", "scope": "person", "reason_code": "t",
        "when": [{"present": "thread.last_inbound"}],
        "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 1}})
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)
    stranger = NodeContext(node_id="n1", node_type="person", facts={})
    known = NodeContext(node_id="n2", node_type="person",
                        facts={"thread.last_inbound": {"value": "2026-08-01T00:00:00+00:00"}})
    assert evaluate(stranger, rule, now) is False
    assert evaluate(known, rule, now) is True


def test_an_active_promoted_pack_carries_instructing_authority():
    """The abstention gate read ONLY a compiled expertise package's review_state — a key the
    legacy pack path never has — so 15 of 15 live cards were downgraded to `observation` while
    their headlines still read "Reply now". The two halves of every card contradicted each other.

    A tenant's ACTIVE pack is authored, versioned, content-addressed and explicitly promoted:
    that IS a human saying these rules may instruct. A paused or draft pack still abstains.
    """
    from genios_engine.deliver.pipeline import _apply_abstention

    signal = {"level": "prescriptive"}
    assert _apply_abstention(signal, {"state": "active"})["level"] == "prescriptive"
    assert _apply_abstention(signal, {"state": "paused"})["level"] == "observation"
    assert _apply_abstention(signal, {})["level"] == "observation"
    # a compiled accepted package still authorises on its own
    assert _apply_abstention(
        signal, {"expertise": {"review_state": "accepted"}})["level"] == "prescriptive"


# ── the lens: what a counterparty IS decides which expertise may speak ──────────
def test_every_deal_rule_requires_a_buying_relationship():
    """The engine held `company_type = "founder-only pre-seed VC"`, that fund's investment
    decision timeline and its closure rate — and still told the founder to "Save the deal now",
    because all of that sat in free-form fact names no rule could read. A pass from a fund is a
    fundraising outcome; a sales rule has no business narrating it."""
    from genios_engine.packs.sales_v1 import SALES_V1

    for rule in SALES_V1["rules"]:
        lens = [c for c in rule["when"] if c.get("path") == "relationship.nature"]
        assert lens, f"{rule['id']} can fire on an investor"
        assert set(lens[0]["value"]) == {"customer", "prospect", "unknown"}
        # missing_ok: this narrows a KNOWN-WRONG lens; it does not require the lens to be known,
        # or every untyped counterparty would silently drop out of the product.
        assert lens[0]["missing_ok"] is True


def test_the_relationship_vocabulary_is_closed():
    """An open vocabulary lets the model invent a lens nothing downstream knows how to apply."""
    from genios_engine.context.pipeline import (
        _RELATIONSHIP_DIRECTIONS,
        _RELATIONSHIP_NATURES,
    )

    assert "investor" in _RELATIONSHIP_NATURES
    assert "unknown" in _RELATIONSHIP_NATURES, "admitting ignorance must be expressible"
    assert _RELATIONSHIP_DIRECTIONS == {"they_evaluate_us", "we_evaluate_them", "peer"}


def test_the_lens_is_typed_from_content_not_from_the_address():
    """A domain list would work for one inbox and fail for the next tenant — the opposite of
    what this layer is for."""
    import inspect

    from genios_engine.context.extract import prompt

    src = inspect.getsource(prompt)
    assert "never from the domain name" in src
    assert "investor" in src and "they_evaluate_us" in src


def test_a_new_extraction_shape_cannot_serve_a_cached_old_one():
    """The cache key carries the prompt and schema version: a consumer that now looks for
    `relationships` must not be handed a payload that never had them."""
    from genios_engine.context.pipeline import EXTRACTION_SCHEMA_VERSION, PROMPT_VERSION

    assert PROMPT_VERSION == "b3-4"
    assert EXTRACTION_SCHEMA_VERSION == "3"


# ── concurrency must follow the pooler, not a comment ───────────────────────────
def test_concurrency_is_derived_from_the_pooler_not_hardcoded():
    """The 3/3/8+4 budget was the SESSION-pooler answer (15 concurrent clients, hard cap). The
    deployment moved to the TRANSACTION pooler — the very thing the old comment recommended —
    and nothing re-read the numbers, so capture throttled itself against a limit that no longer
    existed. Nobody regressed it; the calibration went stale where it could not be seen.
    Deriving from the port is what stops that recurring."""
    import inspect

    from genios_engine.capture.acquire import sync_runner
    from genios_engine.context import runner as l2_runner
    from genios_engine.platform import db

    for mod, fn in ((sync_runner, "_default_workers"), (l2_runner, "_default_l2_workers")):
        src = inspect.getsource(getattr(mod, fn))
        assert ":6543/" in src, f"{fn} must read the pooler mode"
        assert src.rstrip().endswith("else 3"), (
            f"{fn} must stay conservative on the session pooler")

    pool_src = inspect.getsource(db.get_engine)
    assert 'transaction_pooler = ":6543/" in url' in pool_src
    assert "(24, 12) if transaction_pooler else (8, 4)" in pool_src


def test_the_env_override_still_wins():
    """A local run sharing the prod DB must be able to dial itself down and not starve the live
    app — the reason these were env-overridable in the first place."""
    import inspect

    from genios_engine.capture.acquire import sync_runner

    src = inspect.getsource(sync_runner)
    assert "GENIOS_L1_WORKERS" in src and "_default_workers()" in src


# ── a paused org must stop the BACKGROUND writer, not just inbound requests ─────
def test_sweep_skips_a_paused_org():
    """The wipe kept 'failing': every deleted row came back within a minute. The delete was fine —
    the scheduler sweep refilled the graph from Gmail because `check_org_kill` is a FastAPI
    dependency and a background thread never passes through one. A tenant-level 'stop everything'
    that leaves the largest writer running is not a stop."""
    import inspect

    from genios_engine.api import routes

    src = inspect.getsource(routes.run_sync_sweep)
    assert "_org_paused(conn.org_id)" in src, "sweep must consult the per-org kill switch"
    assert "l1_paused += 1" in src and "continue" in src, "a paused org must be skipped, not synced"
    assert "if not paused.get(c.org_id)" in src, "a paused org must not be reasoned either"

    guard = inspect.getsource(routes._org_paused)
    assert "kill_switch:" in guard
    assert "return False" in guard.split("except")[-1], "must fail OPEN on infra error"


# ── an org-level API key must read the org's queue, not nobody's ────────────────
def test_org_key_with_no_person_sees_the_org_queue():
    """The desktop app authenticated correctly, carried `cards.read`, and got an empty list every
    time. A dashboard-minted key has agent_id and actor_id NULL — it is issued to an ORGANISATION,
    not a human — so the queue filter bound :a to NULL, `k.assignee = NULL` was never true, and the
    `assignee is null` fallback matched nothing because L5 routes every card to a seat."""
    from genios_engine.platform.auth import AuthCtx

    # Build the ctx EXACTLY as get_auth_ctx does, synthesised actor_id and all. The first attempt
    # at this fix tested `actor_id is None`, which reads true on a hand-made AuthCtx and false on
    # every real request — the API-key branch sets
    # `actor_id = row.agent_id or f"api_key:{hashed[:12]}"`, so actor_id is never None there.
    # It shipped, deployed, and changed nothing. Mirror the real construction or the test is theatre.
    org_key = AuthCtx(org_id="org_1", agent_id=None, actor_id="api_key:a1b2c3d4e5f6",
                      scopes=["cards.read"], source="api_key")
    assert org_key.sees_org_queue, "a key bound to no agent must read the org queue"

    jwt = AuthCtx(org_id="org_1", actor_id="owner@example.com", scopes=None, source="jwt")
    assert jwt.sees_org_queue, "owner session unchanged"

    agent_key = AuthCtx(org_id="org_1", agent_id="agent_a", actor_id="agent_a",
                        scopes=["cards.read"], source="api_key")
    assert not agent_key.sees_org_queue, "an agent-bound key keeps its own lane"


def test_queue_does_not_filter_by_a_person_when_there_is_no_person():
    """`assignee is not None` is the load-bearing half. Without it the SQL still appends
    `k.assignee = NULL`, which no row satisfies."""
    import inspect

    from genios_engine.deliver.store import CardStore

    src = inspect.getsource(CardStore.queue)
    assert "if not admin and assignee is not None:" in src


def test_seeing_a_card_and_acting_on_it_use_the_same_rule():
    """A credential allowed to READ a card must be allowed to ACT on it. Fixing only the read path
    would surface 13 cards whose buttons all 403."""
    import inspect

    from genios_engine.api import routes

    for fn in (routes.list_cards, routes.get_card, routes.card_action,
               routes.context_match, routes.digest):
        src = inspect.getsource(fn)
        assert "sees_org_queue" in src, f"{fn.__name__} still uses the old scopes check"
        assert "ctx.scopes is None" not in src, f"{fn.__name__} has a stale scopes check"


# ── L1 must overlap the provider wait with the capture that follows it ─────────
def test_next_page_is_fetched_before_the_current_one_is_captured():
    """Measured on the live mailbox: a page costs ~16s of provider wait (Composio list ~10.8s,
    relevance gate ~4.5s, 12-way body fetch ~1.1s) and the capture after it another ~16s. Serially
    those add — the backfill ledger showed 35 rounds at a median 32.1s. The next page's cursor is
    known the moment a page lands, so the two can overlap."""
    import inspect

    from genios_engine.capture.acquire import sync_runner

    src = inspect.getsource(sync_runner.run_sync)
    submit = src.index("pool.submit(")
    capture = src.index("ThreadPoolExecutor(max_workers=_CAPTURE_WORKERS)")
    assert submit < capture, "the next page must be submitted BEFORE the capture, or nothing overlaps"
    assert "prefetch.cancel()" in src and "pool.shutdown(wait=False)" in src


def test_backfill_asks_for_enough_pages_to_overlap():
    """A prefetch is dead code at one page per call: there is never a next page to fetch ahead.
    backfill_drain passed max_pages=1, which is the path a new tenant's first sync takes."""
    import inspect

    from genios_engine.capture.acquire.sync_runner import backfill_drain

    sig = inspect.signature(backfill_drain)
    assert sig.parameters["pages_per_round"].default > 1
    src = inspect.getsource(backfill_drain)
    assert "take = min(pages_per_round, budget)" in src and "max_pages=take" in src, (
        "pages must be batched into one run_sync call for the prefetch to have a next page")
    assert "budget = max_rounds" in src, (
        "the runaway guard must still count PAGES — batching must not multiply the ceiling")


# ── derived.* had no writer, so every rule gated on it was dead ────────────────
def test_derived_fields_have_a_writer():
    """`derived.engagement`, `derived.sentiment` and `derived.momentum` are read by the sales pack
    (`derived.engagement <= 0.5`) and required by the compiled L3 capabilities, and the extraction
    vocabulary excludes them on purpose — vocab.py: "computed by the reasoner, never extracted".
    Nothing computed them. The deep sales rules never fired once and all 18 compiled capabilities
    returned INSUFFICIENT_CONTEXT against a graph that already held everything else."""
    import inspect

    from genios_engine.context import derived, runner

    src = inspect.getsource(derived.compute)
    for field in ("derived.engagement", "derived.sentiment", "derived.momentum"):
        assert field in src, f"{field} still has no writer"
    assert "compute_derived(store, org_id)" in inspect.getsource(runner.process_pending), (
        "L2 must derive after extraction — a writer nothing calls is the same as no writer")


def test_engagement_is_relative_to_the_account_and_deal_value_is_never_invented():
    """Engagement must be a ratio against this relationship's own history: "halved" has to mean
    halved for THIS account whether it ran at forty emails a week or four. And a value nobody
    stated must stay missing — a guessed deal size flows straight into prioritisation."""
    import inspect

    from genios_engine.context import derived

    # Pinned on `_metrics` rather than `compute`, because that is where the arithmetic moved when
    # `compute_account_view` began deriving the same three fields for companies and deals. The
    # point of the shared helper is that there is exactly ONE engagement formula: the sales pack
    # compares person-level and account-level `derived.engagement` against the same threshold, so
    # a second copy of this expression would diverge silently.
    src = inspect.getsource(derived._metrics)
    assert "recent_rate / baseline_rate" in src, "engagement must be a ratio, not a raw count"
    assert "1.0 if baseline_rate <= 0" in src, "a new contact must read neutral, not cold"
    assert "_metrics(acc)" in inspect.getsource(derived.compute), (
        "compute must use the shared formula, not a second copy of it")
    assert "_metrics(acc)" in inspect.getsource(derived.compute_account_view), (
        "the account roll-up must use the shared formula, not a second copy of it")
    # Check the CODE, not the prose. The first version of this assertion matched the docstring
    # sentence saying deal.value is never derived, and would have passed just as happily on a
    # function that derived it while claiming otherwise.
    body = inspect.getsource(derived.compute_deal_view)
    body = body[body.index('"""', body.index('"""') + 3) + 3:]      # drop the docstring
    written = {line.split('"')[1] for line in body.splitlines()
               if '"deal.' in line and 'pairs.append' in line}
    assert written == {"deal.last_inbound", "deal.status", "deal.stage"}, (
        f"compute_deal_view must write only rolled-up truth, writes {written}")
    # `deal.stage` joined this set when the roll-up stopped writing its own vocabulary
    # (`engaged`, `evaluating`, `proposing`) straight into `deal.status` at authority rank 100 —
    # which outranks the extraction path and un-routed every Sales deal situation on the next
    # sync. It is not a new claim: it is the same word already derived from observations,
    # published where readers expect the rich version, exactly as pipeline.py does.
    #
    # The guard this test exists for is `deal.value`, and it is now asserted directly rather
    # than implied by the set — a guessed deal size flows straight into prioritisation.
    assert "deal.value" not in written, "deal.value must never be derived; nobody stated it"


# ── one intelligence, four surfaces ────────────────────────────────────────────
def test_a_settled_deal_leaves_the_app_queue_but_stays_answerable():
    """antler.co, rejected 6 Aug, deadline 14 Aug passed, momentum zero — shown inside "62 OPEN
    LOOPS" in an app whose job is to say what needs you now. The same text is the complete answer
    to "what happened with Antler?", so the card is not wrong; serving one row to four different
    questions is."""
    from genios_engine.deliver.card_builder import _surfaces

    settled = {"deal.status": {"value": "rejected"}, "derived.momentum": {"value": 0}}
    assert _surfaces(settled, {}, [{"action": "run_play"}]) == ["ask", "api"]

    # Either condition alone is not enough: a live deal at zero momentum is exactly what the app
    # exists to surface, and a won deal still moving is an expansion conversation.
    live = {"deal.status": {"value": "open"}, "derived.momentum": {"value": 0}}
    assert "app" in _surfaces(live, {}, [{"action": "reply"}])


def test_agent_surface_needs_something_to_execute():
    """An agent can only act on a play it was handed. A card whose actions are human judgement
    calls has nothing to delegate, whatever else is true of it."""
    from genios_engine.deliver.card_builder import _surfaces

    facts = {"deal.status": {"value": "open"}}
    assert "agent" in _surfaces(facts, {}, [{"action": "run_play"}])
    assert "agent" not in _surfaces(facts, {}, [{"action": "reply"}])


def test_the_app_queue_filters_on_the_surface():
    import inspect

    from genios_engine.deliver.store import CardStore

    assert "'app' = any(k.surfaces)" in inspect.getsource(CardStore.queue)
