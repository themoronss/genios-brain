"""Operating-profile contract: handoff_mode → real L5 actions, and jsonb normalization.

These guard the invariant that flipping an agent to a draft/execute handoff actually GRANTS it
claim/result (not just a cosmetic label), and that a notify-only agent stays read-only.
"""

from genios_engine.api.agent_mgmt_routes import _actions_for_handoff, _load_profile

_READ = {"read_context", "signals.read", "artifacts.read"}
_CLAIM = {"signals.claim", "signals.result"}


def test_notify_agent_is_read_only():
    acts = set(_actions_for_handoff({"handoff_mode": "notify"}))
    assert acts == _READ
    assert not (acts & _CLAIM)


def test_no_profile_is_read_only():
    assert set(_actions_for_handoff(None)) == _READ


def test_draft_handoff_grants_claim_and_result():
    acts = set(_actions_for_handoff({"handoff_mode": "draft"}))
    assert _CLAIM <= acts and _READ <= acts


def test_execute_when_permitted_grants_claim_and_result():
    acts = set(_actions_for_handoff({"handoff_mode": "execute_when_permitted"}))
    assert _CLAIM <= acts


def test_unknown_handoff_mode_stays_read_only():
    assert not (set(_actions_for_handoff({"handoff_mode": "yolo"})) & _CLAIM)


def test_load_profile_handles_dict_str_and_none():
    assert _load_profile(None) is None
    assert _load_profile({"role": "SDR"}) == {"role": "SDR"}
    assert _load_profile('{"role": "SDR"}') == {"role": "SDR"}
    assert _load_profile("not json") is None


def test_p6_plays_grant_the_plays_and_actions_result():
    import pytest
    from fastapi import HTTPException

    from genios_engine.api.agent_mgmt_routes import _plays_from_scope
    plays = ["email.reschedule", "task.reassign", "email.follow_up_draft"]
    acts = _actions_for_handoff({"handoff_mode": "notify"}, plays)
    assert set(plays) <= set(acts) and "actions.result" in acts
    assert "actions.result" not in _actions_for_handoff(None, [])
    assert _plays_from_scope({"allowed_actions": plays}) == sorted(plays)
    assert _plays_from_scope({"segments": None}) is None
    for bad in (["email.send_now"], "email.reschedule", [1]):
        with pytest.raises(HTTPException) as e:
            _plays_from_scope({"allowed_actions": bad})
        assert e.value.status_code == 422
