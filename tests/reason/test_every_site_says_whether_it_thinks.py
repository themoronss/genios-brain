"""Every R-site says whether it may think, how long it may take, and a ceiling sized for what it is asked.

    pytest tests/reason/test_every_site_says_whether_it_thinks.py -q

⛔ `yc2_w27_s18` M50.C2.L-contract.V1.U02 (the 13 Oct audit's T5-3; s5t-F2, F4, F10). Claude Sonnet 5
thinks by default and its thinking counts toward `max_tokens`. The R-site ceilings were sized for a model
that does not think — and R-2's "measured" 737–1,400 was read off a model that did, so its thinking
tokens were counted as prose. `06` D71 (13 Oct): every site asks with thinking OFF, which restores what
the ceilings were sized for. R-7 cannot fit a review in 4,000 even without thinking (Haiku, which does
not think, measured p50 2,737, p90 3,509, max 3,990 and six answers cut at 4,000), so its ceiling is
6,000 — and 6,000 tokens take longer than the client's 60 s (4,000 took 37–45 s apart on 12 Oct), so it
has a timeout of its own.
"""
from __future__ import annotations

import pytest

from genios_engine.context.llm.client import LLMClient, THINKING_MODES, THINKING_OFF
from genios_engine.reason.bundle import sites as S

pytestmark = pytest.mark.unit


def test_every_site_has_a_thinking_mode_from_the_clients_vocabulary():
    assert set(S.SITE_THINKING) == set(S.R_SITES)
    assert set(S.SITE_THINKING.values()) <= set(THINKING_MODES)


def test_every_site_asks_with_thinking_off_by_06_D71():
    """Until a measurement says otherwise (`06` D72 is the R-7 comparison)."""
    assert {S.thinking_mode(site) for site in S.R_SITES} == {THINKING_OFF}


def test_an_unknown_site_has_no_mode():
    with pytest.raises(ValueError, match="unknown R-site"):
        S.thinking_mode("R-99")
    with pytest.raises(ValueError, match="unknown R-site"):
        S.timeout_s("R-99")


def test_the_expert_ceiling_holds_a_review_a_model_that_does_not_think_writes():
    """Haiku's measured max was 3,990 and six answers were cut at 4,000: 6,000 is 1.7x its p90."""
    assert S.max_output_tokens(S.SITE_EXPERT) == 6000
    assert S.max_output_tokens(S.SITE_EXPERT) >= 1.5 * 3509


def test_the_expert_has_time_to_write_its_ceiling():
    """At the 12 Oct pace (4,000 tokens in 37–45 s), 6,000 tokens need ~56–68 s — past the client's own
    60 s, after which the SDK retries a call whose answer may already be paid for."""
    seconds_per_token = 45.3 / 4000
    assert S.timeout_s(S.SITE_EXPERT) >= 1.5 * seconds_per_token * S.max_output_tokens(S.SITE_EXPERT)


def test_a_site_that_fits_the_clients_own_timeout_keeps_it():
    """None means the client's 60 s. R-2's 2,400 is ~27 s at that pace."""
    assert S.timeout_s(S.SITE_NARRATE) is None
    # GeniOS-008: R-9, the L2 judgment pass, is R-7's review plus its judgment half — 8,000 tokens, past the
    # client's 60 s on R-7's own measurement, so it keeps a timeout of its own as R-7 does.
    assert {site for site in S.R_SITES if S.timeout_s(site) is not None} == {S.SITE_EXPERT, S.SITE_REASON}


def test_the_client_default_timeout_is_what_none_means():
    """If the client's own timeout ever moves, the sizing above is re-read."""
    import inspect
    assert "timeout=60.0" in inspect.getsource(LLMClient._c)
