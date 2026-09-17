"""The one configuration where the fail-closed rule was false is the one a global flag creates.

    pytest tests/reason/test_an_unactivatable_situation_is_never_live.py -q

`domain_shadow`'s own comment has always said what happens to a situation whose L2 domain no
corpus claims: it *"compiles in measurement mode, publishes no package and emits no signal — on
EVERY tenant configuration, including one with every corpus switched on."*

The expression beside it did not say that. It read

    live_row = bool(live or (row_domain is not None and row_domain in live_domains))

and `live` — the global `platform/config.use_domain_compiler` — is checked FIRST. With that flag
on, an unactivatable situation got `live_row=True`, and the branch below it does not `continue`:
it falls through to `compiler = compiler_live if live_row ...`. So the deployment that turned the
global switch on is exactly the deployment where a domain with no doctrine could publish a package
and emit a signal.

Measured on the pilot 2026-09-16: 12 of 103 live situations are unactivatable (`fundraising`),
and a measurement run passing `live=True` counted all 103 as live rather than 91.

WHAT THIS DOES NOT DO. It does not retire the flag. That is gated on a pilot passing J5, and the
reason is stated where the gate is: deleting a kill switch in the same change that installs its
subject leaves a cutover with no way back. What it removes is the flag's ability to contradict the
fail-closed rule while it waits — and the tests below pin what the flag actually is, which is a
global ON switch, not a way back.
"""
from __future__ import annotations

import pytest

from genios_engine.reason.domain_shadow import live_lane

pytestmark = pytest.mark.unit

ACTIVATED = frozenset({"admin", "customer_support", "sales"})


def test_an_activated_corpus_is_live_with_the_global_flag_off() -> None:
    """The production configuration today: the flag is False everywhere, and L3 still runs live.
    This is why switching the flag off is not a way back."""
    assert live_lane(forced=False, domain="admin", activated=ACTIVATED) is True


def test_a_corpus_the_tenant_has_not_switched_on_stays_in_shadow() -> None:
    assert live_lane(forced=False, domain="customer_support", activated=frozenset({"admin"})) is False


def test_deleting_the_activation_row_is_what_takes_a_tenant_off_the_live_lane() -> None:
    """The real way back, stated as a property: with no activated corpus, nothing is live —
    and the global flag being off is not what achieved that."""
    assert live_lane(forced=False, domain="admin", activated=frozenset()) is False


def test_an_unactivatable_domain_is_not_live_even_with_the_global_flag_on() -> None:
    """THE DEFECT. `domain is None` means no corpus claims this situation, so there is no doctrine
    to compile — and the global flag must not be able to hand it the live compiler anyway."""
    assert live_lane(forced=True, domain=None, activated=ACTIVATED) is False
    assert live_lane(forced=True, domain=None, activated=frozenset()) is False


def test_an_unactivatable_domain_is_not_live_with_the_flag_off_either() -> None:
    """The direction that already held. Both must, or the fix traded one asymmetry for another."""
    assert live_lane(forced=False, domain=None, activated=ACTIVATED) is False


def test_the_global_flag_still_forces_a_real_corpus_live() -> None:
    """Its documented behaviour for a deployment that has already set it is unchanged. Narrowing
    it further would be retiring it early, which is the gated decision this change does not make."""
    assert live_lane(forced=True, domain="sales", activated=frozenset()) is True
