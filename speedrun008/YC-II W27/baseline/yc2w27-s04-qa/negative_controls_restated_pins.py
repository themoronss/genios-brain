"""The six negative controls for the pins STEP-04 restated (commit 9a94b42c) — each restated pin must
go red under its own mutation. Run from the repository root: .venv/bin/python <this file>.
Recorded 2026-10-06: all six red as they must be."""
import importlib
import inspect
import sys

sys.path.insert(0, ".")
results = []


def control(name, fn):
    try:
        fn()
        results.append(f"CONTROL FAILED (pin still green): {name}")
    except AssertionError as e:
        msg = (str(e).splitlines() or ["(no message)"])[0][:90]
        results.append(f"control ok (pin red): {name} -- {msg}")


T = importlib.import_module("tests.api.test_a_cold_graph_must_not_decide_who_you_know")
orig = T.KNOWN_FROM_SENT_SQL
T.KNOWN_FROM_SENT_SQL = orig.replace("= any(:ours)", "is not null")
assert T.KNOWN_FROM_SENT_SQL != orig
control("cold graph: author check dropped", T.test_a_stranger_is_still_a_stranger)
T.KNOWN_FROM_SENT_SQL = orig
real_getsource = inspect.getsource


def mutated(target, old, new):
    def fake(obj, *a, **k):
        src = real_getsource(obj, *a, **k)
        if getattr(obj, "__name__", "") == target:
            assert old in src, (target, old)
            return src.replace(old, new)
        return src
    return fake


L = importlib.import_module("tests.test_l2_completeness")
inspect.getsource = mutated("backfill_correlations", "us.is_us_node(row.node_type, row.canonical_key)", "False")
control("backfill: is_us_node removed", L.test_backfill_excludes_our_own_people_like_the_live_path_does)
J = importlib.import_module("tests.context.test_a_join_on_a_fact_that_never_existed")
inspect.getsource = mutated("meeting_rows", "not us.is_us_node(a[1], a[2])", "True")
control("meeting_rows: is_us_node removed (join pin)", J.test_externality_is_still_decided_and_decided_by_who_we_are)
M = importlib.import_module("tests.test_meeting_touch")
control("meeting_rows: is_us_node removed (meeting_touch pin)", M.test_only_meetings_with_an_outside_party_are_touches)
inspect.getsource = real_getsource
from genios_engine.context import meeting_touch as mt  # noqa: E402
real_rows = mt.meeting_rows


def keeps_everyone(c, org_id, us):
    from genios_engine.platform.self_identity import SelfIdentity
    return real_rows(c, org_id, SelfIdentity())


mt.meeting_rows = keeps_everyone
control("meeting_rows keeps a meeting of only us", J.test_a_meeting_with_nobody_external_is_not_a_touch)
mt.meeting_rows = real_rows
orig_m = J._MEETINGS
J._MEETINGS = orig_m.replace("jsonb_agg(distinct jsonb_build_array(att.display_name", "max(att.display_name")
control("aggregate back to max()", J.test_every_external_attendee_is_kept)
J._MEETINGS = orig_m
print("\n".join(results))
sys.exit(0 if all(r.startswith("control ok") for r in results) else 1)
