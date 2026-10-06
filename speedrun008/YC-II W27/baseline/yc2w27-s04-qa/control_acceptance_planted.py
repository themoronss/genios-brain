"""Negative controls for tests/replays/test_we_are_never_the_subject.py: each planted defect must
turn the acceptance red. Run: GENIOS_TEST_DATABASE_URL=… pytest <this file> -q -s (copied into
tests/replays/ for the run, removed after)."""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from tests.replays import test_we_are_never_the_subject as T
from tests.replays.founder_case import load_cases

pytestmark = [pytest.mark.pg]

PLANTS = {
    "card subject": ("insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
                     "score, why, actions, artifact, state, expires_at, business_subject) values "
                     "('c_planted', 'sig_planted', :o, 'review', 'low', 'h', 's', 10, cast('[]' as jsonb), "
                     "cast('[]' as jsonb), cast('{}' as jsonb), 'queued', :exp, 'Ms Meera Iyer')"),
    "card words": ("insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
                   "score, why, actions, artifact, state, expires_at, business_subject) values "
                   "('c_words', 'sig_words', :o, 'review', 'low', 'ceo@kitebird.test and Meera Iyer have been waiting longest', "
                   "'s', 10, cast('[]' as jsonb), cast('[]' as jsonb), cast('{}' as jsonb), 'queued', :exp, 'Cohort')"),
    "thread name": ("insert into graph_nodes (org_id, node_id, node_type, canonical_key, display_name) values "
                    "(:o, 'n_thread_planted', 'thread', 'thread:planted', 'Meera Iyer — Seed round for Kitebird')"),
}


@pytest.mark.parametrize("plant", sorted(PLANTS))
def test_each_planted_defect_turns_the_acceptance_red(monkeypatch, plant):
    from tests.replays import engine_runner
    real = engine_runner.run_case
    case = next(c for c in load_cases() if c.case_id == "F42")

    def planted(case, llm, **kw):
        run = real(case, llm, **kw)
        from genios_engine.api import routes
        with routes._graph.engine.begin() as c:
            c.execute(text(PLANTS[plant]), {"o": run.org_id,
                                            "exp": datetime.now(timezone.utc) + timedelta(days=2)})
        return run
    monkeypatch.setattr(engine_runner, "run_case", planted)
    with pytest.raises(AssertionError) as red:
        T.test_we_are_never_the_subject(case)
    print(f"\n  {plant}: red — {str(red.value).splitlines()[0][:120]}")
