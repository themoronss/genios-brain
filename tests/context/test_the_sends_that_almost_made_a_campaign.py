"""The raise that went out eighteen times in eighteen different sentences.

`correlation_conversation` groups outbound mail by the EXACT sentence, and its refusal to do
anything softer is correct and quoted in full where this pass is declared: *"a similarity threshold
here would quietly merge two different pitches on a bad day … the one nobody can debug from a
stored score."*

The cost of that correctness is a blind spot with a strange shape. A founder who copies and pastes
gets one campaign; a founder who retypes each email gets eighteen unrelated threads. The difference
is a typing habit, not a fact about the fundraise.

THIS PASS ASSERTS NOTHING, and most of this file is about that. It mints no campaign and no card.
It publishes a CANDIDATE — a set of sends, in one window, to enough distinct counterparties,
sharing words this tenant does not use everywhere — WITH THE WORDS ATTACHED, so a human can agree
or dismiss in one second and a model can adjudicate one bounded instance instead of a threshold
guessing at all of them.

The two tests that carry the design are `test_the_founders_own_habits_never_group_anything` — the
answer to "why is this not just fuzzy matching" — and
`test_the_shared_words_are_common_to_every_member`, which is why a candidate row can be checked at
all.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.context.campaign_candidates import (MIN_SHARED_TOKENS, candidate_id_for,
                                                       distinctive_tokens, find_candidates,
                                                       read_candidates, tokenise)
from genios_engine.context.correlation_conversation import _rows_to_campaigns

NOW = datetime(2026, 8, 11, 3, 2, tzinfo=timezone.utc)
ORG = "o"
US = "rohit@genios.ai"

#: A signature, a sign-off and a scheduling link — the words this founder puts in everything.
BOILERPLATE = ("Best, Rohit — founder at Genios. Book time on my calendar link below whenever "
               "suits you, always happy to chat further about any of this.")


def _row(node, quote, *, minutes=0, event=None, actor=US, recipient=None):
    return {"node_id": node,
            "recipient_key": recipient if recipient is not None else f"{node}@example.com",
            "event_id": event or f"e_{node}_{minutes}",
            "sent_at": NOW + timedelta(minutes=minutes),
            "actor": json.dumps({"email": actor}),
            "evidence_refs": json.dumps([{"quote": quote}])}


#: THE ORDINARY MAIL A CAMPAIGN HIDES IN, and it is not scenery. Distinctiveness is measured as
#: "rare in this tenant's own sends", so it can only separate a campaign from a habit when there is
#: mail OUTSIDE the campaign to compare against — see `MIN_CORPUS_SENDS`. A fixture of four sends
#: and nothing else is a mailbox where every word appears in every message, and the pass correctly
#: declines to name anything in it. Each of these carries the same signature as the raise, which is
#: exactly what makes the signature disqualify itself.
_ERRANDS = (
    "Confirming the invoice was settled on Friday afternoon as discussed",
    "Here is the signed NDA, apologies for the delay getting it back",
    "Could we push tomorrow's call to the afternoon instead of the morning",
    "Sending over the deck you asked for after yesterday's introduction",
    "Thanks for the referral, I have written to them separately today",
    "The office move happens next month so post should go elsewhere",
    "Attaching last quarter's summary for your records as requested",
    "Happy to review the contract draft once your counsel has seen it",
    "Our accountant needs the reconciliation before the audit begins",
    "I have booked the venue for the offsite in the first week of March",
    "The laptop order shipped yesterday and arrives by the weekend",
    "Please ignore my previous message, the attachment was the wrong version",
    "Welcome aboard, your accounts should be provisioned by Wednesday",
    "The renewal paperwork is with procurement and moves slowly there",
    "Sharing the recording of this morning's session for anyone who missed it",
    "We have updated the pricing page, nothing changes for existing customers",
    "The visa appointment is confirmed for the twelfth at eleven",
    "I am out next week, my colleague will pick up anything urgent",
    "The warehouse confirmed stock levels are back to normal again",
    "Your feedback on the onboarding flow was passed to the design team",
    "The insurance certificate expires shortly and needs renewing soon",
    "Dinner is booked for eight, let me know if that no longer works",
    "The tax filing deadline moved, which buys everyone another fortnight",
    "I have archived the old repository since nobody has touched it",
)


def _corpus(start=200):
    """Two dozen unremarkable sends, every one wearing the founder's signature.

    EACH SENTENCE IS DISTINCT, which matters: an earlier fixture repeated eight errands three
    times and those repeats were themselves exact-sentence campaigns — `find_campaigns` found
    nine of them. A mailbox where the ordinary mail is copy-pasted is not an ordinary mailbox.
    """
    return [_row(f"n_err{i}", f"{text}. {BOILERPLATE}", minutes=start + i * 7,
                 event=f"e_err_{i}")
            for i, text in enumerate(_ERRANDS)]


def _filler(count, start=900):
    """Mail that exists only to be COUNTED — frequency mass, not scenery.

    A second attempt at scaling `_corpus` repeated each errand five times with a unique tail, and
    the detector correctly found twenty-four near-miss groups in it: five near-identical sends to
    five different people IS the thing this pass looks for. The fixture was wrong, not the rule.

    So every sentence here shares only the signature — which disqualifies itself — and is
    otherwise built from words unique to it, which are distinctive but can never be shared by
    three sends. The result adds frequency mass and forms no group of its own.
    """
    return [_row(f"n_fill{i}",
                 f"Regarding matter {i}: zeta{i} kappa{i} lambda{i} omicron{i} noted. {BOILERPLATE}",
                 minutes=start + i * 3, event=f"e_fill_{i}")
            for i in range(count)]


def _paraphrases():
    """One raise, retyped four times, inside a mailbox of ordinary mail.

    The shared words are the ones about the round; the signature every send carries is what the
    frequency rule throws away without being told to.
    """
    return [
        _row("n_peak", f"We are raising a preseed round with traction at 3k MRR. {BOILERPLATE}",
             minutes=0),
        _row("n_afore", f"Quick note on our preseed — traction is now about 3k MRR. {BOILERPLATE}",
             minutes=30),
        _row("n_neon", f"Sharing that we opened a preseed; MRR traction sits near 3k. {BOILERPLATE}",
             minutes=90),
        _row("n_surge", f"Our preseed is open and traction reached 3k MRR this month. {BOILERPLATE}",
             minutes=120),
    ] + _corpus()


def _ids(candidates):
    return [c.candidate_id for c in candidates]


# ── what the deterministic layer already owns is never re-proposed ───────────────────────────

def test_one_sentence_sent_eighteen_times_is_not_a_candidate() -> None:
    """THE PILOT'S ACTUAL CASE, and `find_campaigns` gets it right. Proposing it would spend a
    model call rediscovering a correct answer."""
    sentence = ("we can expect the numbers to hit nearly ~$2-3k MRR by the end of this quarter "
                "across the pilot accounts")
    rows = [_row(f"n_{i}", sentence, minutes=i * 10) for i in range(18)]

    assert len(_rows_to_campaigns(rows, org_id=ORG)) == 1
    found, _cut = find_candidates(rows)
    assert found == ()


def test_a_reworded_raise_is_a_candidate_the_campaign_finder_missed() -> None:
    """THE BLIND SPOT, from the other side. Four sends, four different sentences, one raise."""
    rows = _paraphrases()
    assert _rows_to_campaigns(rows, org_id=ORG) == ()

    [candidate], _cut = find_candidates(rows)
    assert set(candidate.recipients) == {"n_peak", "n_afore", "n_neon", "n_surge"}
    assert len(candidate.sentences) == 4
    assert {"preseed", "traction", "mrr"} <= set(candidate.shared_tokens)


# ── why this is not fuzzy matching ───────────────────────────────────────────────────────────

def test_the_founders_own_habits_never_group_anything() -> None:
    """THE ANSWER TO THE OBJECTION `correlation_conversation` RAISES. Distinctiveness is MEASURED
    against this tenant's own mail, not read off a list: a signature, a sign-off and a calendar
    link appear in nearly every send, so they disqualify themselves. A stopword list would have to
    be maintained and would be wrong for the next tenant."""
    from genios_engine.context.campaign_candidates import _sends

    rows = _corpus()
    assert len(rows) >= 20, "the frequency signal needs a corpus; see MIN_CORPUS_SENDS"
    assert find_candidates(rows)[0] == ()

    distinctive = distinctive_tokens(_sends(rows))
    for habit in ("rohit", "genios", "calendar", "always", "happy", "below"):
        assert habit not in distinctive, habit


def test_the_shared_words_are_common_to_every_member() -> None:
    """WHAT MAKES A CANDIDATE CHECKABLE. The published words are the INTERSECTION across the whole
    group, not a pairwise resemblance. Connected components over pairwise similarity were the
    obvious alternative and chain A to C because both resemble B — leaving a group with nothing a
    reader can point at."""
    rows = _paraphrases()
    [candidate], _cut = find_candidates(rows)

    from genios_engine.context.campaign_candidates import _sends

    members = [send for send in _sends(rows) if send.event_id in candidate.event_ids]
    assert len(members) == len(candidate.event_ids) >= 3
    for token in candidate.shared_tokens:
        assert all(token in send.tokens for send in members), token

    # …and NOT merely present somewhere in the mailbox: a word every send happens to contain is
    # the founder's habit, and the frequency rule has already thrown those away.
    outsiders = [send for send in _sends(rows) if send.event_id not in candidate.event_ids]
    assert not any(set(candidate.shared_tokens) <= send.tokens for send in outsiders)


def test_two_shared_words_are_a_coincidence_not_a_campaign() -> None:
    """Two business emails can reach two words in common by accident. Three is the floor, and it
    is the floor for the group's INTERSECTION."""
    rows = [
        _row("n_a", f"Our preseed round is progressing nicely this month. {BOILERPLATE}"),
        _row("n_b", f"The preseed conversation continues to move along. {BOILERPLATE}", minutes=10),
        _row("n_c", f"Preseed discussions are ongoing at the moment here. {BOILERPLATE}",
             minutes=20),
    ]
    found, _cut = find_candidates(rows)
    assert all(len(c.shared_tokens) >= MIN_SHARED_TOKENS for c in found)


# ── the bounds it shares with the campaign finder ────────────────────────────────────────────

def test_two_recipients_are_a_conversation_not_a_campaign() -> None:
    rows = _paraphrases()[:2]
    assert find_candidates(rows)[0] == ()


def test_a_send_outside_the_window_is_a_different_attempt() -> None:
    """The same rule `_rows_to_campaigns` keeps: a run breaks when the gap from its FIRST send
    exceeds the window, so one raise is not merged with the next quarter's."""
    rows = _paraphrases()
    rows[3]["sent_at"] = NOW + timedelta(hours=100)
    found, _cut = find_candidates(rows)
    assert all(len(c.recipients) == 3 for c in found)


def test_a_short_sentence_is_not_evidence() -> None:
    """`MIN_SENTENCE_CHARS` — below it a shared sentence is a greeting or a subject fragment. The
    same exclusion the campaign finder applies, so the two passes see the same mail."""
    rows = [_row(f"n_{i}", "thanks!", minutes=i * 5) for i in range(6)]
    assert find_candidates(rows)[0] == ()


def test_we_are_never_a_recipient_of_our_own_campaign() -> None:
    """`thread.last_outbound` is written on every participant node including ours, which inflated
    the live tenant's campaign by one. Excluded here exactly as it is there."""
    rows = _paraphrases()
    rows.append(_row("n_us", f"We are raising a preseed with traction at 3k MRR. {BOILERPLATE}",
                     minutes=15, recipient=US))
    [candidate], _cut = find_candidates(rows)
    assert "n_us" not in candidate.recipients


# ── stability, identity and bounds ───────────────────────────────────────────────────────────

def test_the_same_group_is_the_same_candidate_next_sweep() -> None:
    rows = _paraphrases()
    assert _ids(find_candidates(rows)[0]) == _ids(find_candidates(list(reversed(rows)))[0])


def test_a_member_joining_makes_it_a_different_candidate() -> None:
    """Content-addressed on the SET of sends, because a group with a new member is a different
    group — and a verdict about the old one should not silently cover it."""
    rows = _paraphrases()
    before = _ids(find_candidates(rows)[0])
    rows.append(_row("n_z", f"Preseed open, traction at 3k MRR, quick note. {BOILERPLATE}",
                     minutes=45))
    assert _ids(find_candidates(rows)[0]) != before


def test_the_id_is_order_independent() -> None:
    assert candidate_id_for(["e2", "e1"]) == candidate_id_for(["e1", "e2"])


def test_a_truncated_pass_says_so() -> None:
    """A cost ceiling, not a sample — and a pass that cut cannot look like a clean one."""
    rows = _paraphrases()
    assert find_candidates(rows)[0] != (), "fixture must produce something to truncate"
    found, cut = find_candidates(rows, limit=0)
    assert (found, cut) == ((), True)


def test_a_group_larger_than_the_carry_limit_still_reports_its_true_size() -> None:
    """THE NUMBER IS WHAT THE CARD WOULD SAY. An earlier cut sliced the members to
    `MAX_SENDS_PER_CANDIDATE` BEFORE counting recipients and intersecting tokens, so a group of
    twenty was judged on twelve of them and then reported twelve. `correlation_conversation`
    records the same failure pointing the other way — a campaign at twice its true size — and
    calls it worse than not finding the campaign at all.

    The cap belongs on what TRAVELS. `event_ids` is bounded because a payload should not grow
    without limit; `sends` and `recipients` are measured over everyone.
    """
    from genios_engine.context.campaign_candidates import MAX_SENDS_PER_CANDIDATE

    big = [_row(f"n_big{i}",
                f"Opening our preseed, traction near 3k MRR, note {i}. {BOILERPLATE}",
                minutes=i * 3, event=f"e_big_{i}")
           for i in range(MAX_SENDS_PER_CANDIDATE + 8)]
    # Five times the group in filler, because a campaign that DOMINATES a mailbox is invisible
    # to a frequency rule — see the note beside `MIN_CORPUS_SENDS`.
    [candidate], _cut = find_candidates(big + _filler(100))

    assert candidate.sends == MAX_SENDS_PER_CANDIDATE + 8
    assert len(candidate.recipients) == MAX_SENDS_PER_CANDIDATE + 8
    assert len(candidate.event_ids) == MAX_SENDS_PER_CANDIDATE


@pytest.mark.parametrize("quote", ["", None, "   "])
def test_a_send_with_no_sentence_is_skipped(quote) -> None:
    rows = _paraphrases() + [_row("n_empty", quote or "")]
    found, _cut = find_candidates(rows)
    assert all("n_empty" not in c.recipients for c in found)


def test_tokenise_keeps_what_a_reader_would_recognise() -> None:
    """Crude on purpose: the words that come out here are the words published as evidence, so what
    a reader sees is exactly what the pass matched on. A stemmer would break that."""
    tokens = tokenise("We are raising a $2-3k preseed — traction is up!")
    assert {"raising", "preseed", "traction", "$2-3k"} <= tokens
    assert "a" not in tokens and "—" not in tokens


# ── reading it back ──────────────────────────────────────────────────────────────────────────

def test_a_mailbox_too_small_to_judge_is_declined_rather_than_guessed() -> None:
    """THE DECLARED LIMIT. Read only the four sends of one raise and every word appears in every
    message: no frequency rule can tell a pitch from a sign-off, because there is no mail outside
    the campaign to compare against. The pass says nothing, and says nothing BY RULE rather than
    by an arithmetic accident nobody chose."""
    just_the_raise = [row for row in _paraphrases() if not row["node_id"].startswith("n_err")]
    assert len(just_the_raise) == 4
    assert find_candidates(just_the_raise) == ((), False)


def test_the_floor_is_a_rule_and_not_a_rounding_artefact() -> None:
    """WHERE THE FLOOR ACTUALLY DECIDES. Below about fifteen sends the ceiling arithmetic already
    yields nothing, so a four-send mailbox proves nothing about `MIN_CORPUS_SENDS`. Between
    fifteen and nineteen it does not: at sixteen sends the ceiling is three, a three-member group
    sits exactly on it, and without the floor this pass would start naming candidates off a
    sample too small to distinguish a pitch from a habit.

    Removing the floor makes THIS test fail, which is what makes it a rule rather than a comment.
    """
    from genios_engine.context.campaign_candidates import MIN_CORPUS_SENDS

    raise_ = [_row(f"n_r{i}", f"{text}. {BOILERPLATE}", minutes=i * 20, event=f"e_r{i}")
              for i, text in enumerate((
                  "We are raising a preseed round with traction at 3k MRR",
                  "Quick note on our preseed, traction is now about 3k MRR",
                  "Sharing that we opened a preseed and MRR traction sits near 3k"))]
    small = raise_ + _filler(13)
    assert len(small) == 16 < MIN_CORPUS_SENDS
    assert find_candidates(small) == ((), False)

    # …and the SAME raise, in a mailbox big enough to judge it against, is found.
    assert find_candidates(raise_ + _filler(40))[0] != ()


def test_the_exact_sentence_rule_still_wins_inside_a_real_mailbox() -> None:
    """The same campaign, copy-pasted, inside the same ordinary mail: `find_campaigns` owns it and
    this pass stays quiet. The two must not both speak about one group."""
    sentence = ("we can expect the numbers to hit nearly ~$2-3k MRR by the end of this quarter "
                "across the pilot accounts")
    rows = [_row(f"n_v{i}", sentence, minutes=i * 10, event=f"e_v{i}") for i in range(4)] + _corpus()
    assert len(_rows_to_campaigns(rows, org_id=ORG)) == 1
    assert all("n_v0" not in c.recipients for c in find_candidates(rows)[0])


def test_reading_candidates_without_a_tenant_node_is_empty_not_an_error() -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table graph_nodes (org_id text, node_id text, canonical_key text, "
                       "node_type text, valid_to text)"))
        c.execute(text("create table graph_facts (org_id text, subject_node_id text, field text, "
                       "value text, status text, valid_to text)"))
        assert read_candidates(c, ORG) == ()


# =================================================================================================
# THE SWEEP HALF — the code that had never run
# =================================================================================================
#
# `find_candidates` is pure and everything above tests it without a database. The half that
# publishes was, until this section existed, NEVER EXECUTED BY ANYTHING: it looks up the tenant
# node, reads the rows, calls the publisher and closes what it did not republish, and a wrong
# keyword or a stale import in any of that would have surfaced on a real tenant rather than here.
# The branch has that failure on record — a constant whose NAME a source-scan test found while the
# runtime raised `NameError`, caught only once a behavioural test drove the real path.
#
# The publisher's own SQL takes `select … for update`, which SQLite has no form of, so the sibling
# correlators test their publish paths against `pg_store` and skip where there is no Postgres.
# These run everywhere: a recording stub stands in for the two publisher calls, so every line of
# this module executes and the recorded keywords are bound against the REAL signatures — which is
# what makes "it was called correctly" a check rather than a hope.

class _Stub:
    """A connection that answers the two queries this pass makes and records nothing else."""

    def __init__(self, rows, tenant="n_tenant"):
        self._rows, self._tenant = rows, tenant

    def execute(self, statement, params=None):
        # The tenant lookup does not come through here — `tenant_node_id` is patched at its own
        # module below, because `refresh_campaign_candidates` imports it INSIDE the function and
        # a patch on the importing module would never be seen.
        return _Rows(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _Store:
    def __init__(self, conn):
        self.engine = _Engine(conn)


class _Engine:
    def __init__(self, conn):
        self._conn = conn

    def begin(self):
        return self._conn


@pytest.fixture
def published(monkeypatch):
    """Record what the pass hands the publisher, and bind it against the real signature."""
    import inspect

    from genios_engine.context.analytic import publish as publish_module
    import genios_engine.context.campaign_candidates as module

    calls = {"publish": [], "close": []}
    real_publish = inspect.signature(publish_module.publish_derived_fact)
    real_close = inspect.signature(publish_module.close_derived_facts)

    class _Published:
        version_id = "fv_cand:1"
        wrote = True

    def fake_publish(target, **kw):
        real_publish.bind(target, **kw)          # a wrong keyword fails HERE, loudly
        calls["publish"].append(kw)
        return _Published()

    def fake_close(conn, **kw):
        real_close.bind(conn, **kw)
        calls["close"].append(kw)
        return 0

    from genios_engine.context import periodic as periodic_module

    monkeypatch.setattr(publish_module, "publish_derived_fact", fake_publish)
    monkeypatch.setattr(publish_module, "close_derived_facts", fake_close)
    # PATCHED WHERE IT LIVES, not where it is used: the pass imports this inside the function, so
    # the name is resolved at call time from `periodic` and a patch on the caller is never seen.
    monkeypatch.setattr(periodic_module, "tenant_node_id", lambda conn, org: conn._tenant)
    assert module.FIELD_CANDIDATE                 # the module under test is imported, not shadowed
    return calls


def _run(rows, published, tenant="n_tenant"):
    from genios_engine.context.campaign_candidates import refresh_campaign_candidates

    conn = _Stub(rows, tenant=tenant)
    return refresh_campaign_candidates(_Store(conn), ORG, eval_time=NOW + timedelta(hours=12))


def test_the_pass_publishes_what_it_found(published) -> None:
    """EVERY LINE OF THE SWEEP HALF, executed. The keywords are bound against the publisher's real
    signature, so a renamed parameter fails here instead of on a tenant."""
    report = _run(_paraphrases(), published)

    assert report.candidates == 1
    assert report.written == 1 and report.truncated is False
    [call] = published["publish"]
    assert call["field"] == "derived.conversation.campaign_candidate"
    assert call["subject_node_id"] == "n_tenant"
    [candidate] = call["value"]["candidates"]
    assert {"preseed", "traction", "mrr"} <= set(candidate["shared_tokens"])
    assert candidate["sends"] == len(candidate["event_ids"]) == 4


def test_a_tenant_with_no_near_misses_closes_the_row(published) -> None:
    """A tenant whose candidates were resolved must stop carrying last month's. Closed with
    `valid_to` rather than deleted, so an as-of read of last week keeps its answer."""
    report = _run(_corpus(), published)

    assert report.candidates == 0
    assert published["publish"] == []
    [close] = published["close"]
    assert close["keep"] == []


def test_a_graph_with_no_tenant_node_is_a_quiet_zero(published) -> None:
    """`tenant_node_id` returns None before the first sweep mints one. Minting one here would make
    this pass the reason a tenant node exists — a dependency nobody declared."""
    report = _run(_paraphrases(), published, tenant=None)

    assert report == type(report)()
    assert published["publish"] == [] and published["close"] == []


def test_the_value_survives_a_json_round_trip(published) -> None:
    """It is stored as `jsonb` and read back by an angle's gate, so everything in it has to be
    plain JSON — a `datetime` left in the payload serialises on Postgres and explodes on a driver
    that hands the dict straight to `json.dumps`."""
    _run(_paraphrases(), published)
    [call] = published["publish"]
    assert json.loads(json.dumps(call["value"])) == call["value"]
