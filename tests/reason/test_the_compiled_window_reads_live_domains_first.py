"""G012 H-24 · the compiled lane's window of situations goes to the live domains' first.

    pytest tests/reason/test_the_compiled_window_reads_live_domains_first.py -q

`domain_shadow._ACTIVE_SITUATIONS` reads at most `limit` (200) active situations. On the design partner's org (local
copy, 24 Oct) 562 were active and 259 a live domain's; ordered by confidence alone the window was mostly support and
sales readings no live lane can card, and the 11 Aug investor wave ("6 unanswered", confidence 10) ranked 298th and was
never compiled.
"""
from __future__ import annotations

import inspect

import pytest

from genios_engine.reason import domain_shadow

pytestmark = pytest.mark.unit


def test_the_window_orders_a_live_domains_situations_first_then_confidence():
    order = domain_shadow._ACTIVE_SITUATIONS.split("order by", 1)[1]
    assert order.strip().startswith("(s.domain = any(:live)) desc, s.confidence_overall desc")


def test_the_pass_reads_the_window_with_the_domains_live_here():
    source = inspect.getsource(domain_shadow.shadow_compile)
    assert '{"o": org_id, "lim": limit, "live": live_l2}' in source
    assert "live_lane(forced=live, domain=corpus, activated=live_domains)" in source
