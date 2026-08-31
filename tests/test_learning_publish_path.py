"""L7-02: the review endpoint renamed the row and never published.

Approving wrote `state='promoted'` and stopped: no brain version, no knowledge_suggestions
update — the API reported success while nothing any decision path reads had changed. A
false-positive success receipt is more dangerous than a visible failure.

Then the publish path itself had two never-executed defects stacked on top:

  * the rehydration passed four kwargs `LearningObject` does not have and handed dicts where
    `LearningEvidence`/`Visibility` instances are required — TypeError on EVERY call, absorbed
    into "object_unreadable";
  * `_target_state_for` returned PUBLISHED, which `publisher.publish` dispatches to its
    else-branch: "rejected". The dispatcher's vocabulary is the INPUT state (PROMOTED), not the
    outcome.

Live proof on the design partner's real proposal (rolled back): sink `published_v1`, one row in
`learned_brain_entries` — the first brain publish in the system's history.
"""
import inspect

from genios_engine.api import learning_routes
from genios_engine.contracts.learning import LearningState, LearningTarget


def test_rehydration_matches_the_constructor_field_for_field():
    """Every kwarg passed must exist on the dataclass — the previous version failed on its
    first argument and nobody saw, because the except clause read as a data guard."""
    from genios_engine.contracts.learning import LearningObject

    src = inspect.getsource(learning_routes._publish_approved)
    fields = set(LearningObject.__dataclass_fields__)
    for bad in ("learning_id=", "semantic_hash=", "visibility_scope=", "policy_revision="):
        name = bad.rstrip("=")
        if name not in fields:
            assert f"\n            {bad}" not in src, (
                f"{name} is not a LearningObject field; passing it raises TypeError "
                "on every rehydration")
    assert "LearningEvidence(**" in src, "evidence must be the typed contract, not a dict"


def test_approval_publishes_through_promoted_not_published():
    """PUBLISHED is publish()'s OUTPUT for brain targets, never its input — handing it in
    falls through to the else-branch and returns 'rejected' for every approval."""
    class _Obj:
        target = LearningTarget.ORGANIZATION

    assert learning_routes._target_state_for(_Obj()) is LearningState.PROMOTED

    class _Lease:
        target = LearningTarget.ADAPTIVE

    assert learning_routes._target_state_for(_Lease()) is LearningState.TEMPORARY


def test_the_review_handler_settles_both_ledgers():
    """A knowledge suggestion carries its own review row; leaving it `human_review` forever
    re-lists work a human already judged."""
    src = inspect.getsource(learning_routes.review)
    assert "update knowledge_suggestions" in src
    assert "_publish_approved" in src


# ── L4-05 + L2-14: the decision survives onto the signal, the ask carries its loop ──
def test_the_signal_row_carries_the_decisions_own_content():
    """`signals` carried only score/reason_code/evidence/play, so the card layer rebuilt its
    recommendation from the reason_code STRING through an API if/elif chain — a parallel
    generator sharing nothing with Layer 4 but one label. This is why cards read as activity
    reminders whatever the engine decided."""
    import inspect

    from genios_engine.reason import runner

    src = inspect.getsource(runner._emit)
    for col in ("do_nothing_consequence", "uncertainty", "outcome_window_days",
                "rejected_candidates", "candidate_steps"):
        assert col in src, f"signals insert must write {col}"


def test_the_projection_prefers_decided_steps_over_the_reason_code_chain():
    import inspect

    from genios_engine.api import routes

    src = inspect.getsource(routes._decision_projection)
    assert "decided_steps" in src
    # the chain survives only as the fallback for pre-0070 rows
    assert src.index("decided_steps") < src.index('reason_code == "unanswered_email"')


def test_an_ask_observation_is_born_with_its_loop_identity():
    """A follow-up repeating the ask lands on the SAME loop; a different thread's same-kind ask
    is a different one; and re-extraction by a future model version cannot move it."""
    from genios_engine.contracts.open_loop import is_ask, open_loop_id

    same_a = open_loop_id(org_id="o", subject_node_id="n1", kind="question", thread_id="t1")
    same_b = open_loop_id(org_id="o", subject_node_id="n1", kind="question", thread_id="t1")
    other_thread = open_loop_id(org_id="o", subject_node_id="n1", kind="question", thread_id="t2")
    other_kind = open_loop_id(org_id="o", subject_node_id="n1", kind="demo_requested",
                              thread_id="t1")
    assert same_a == same_b
    assert len({same_a, other_thread, other_kind}) == 3
    assert is_ask("question") and is_ask("demo_requested")
    assert not is_ask("email_relevance"), "a score is information, not a request"
