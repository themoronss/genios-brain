from datetime import datetime, timedelta, timezone

from genios_engine.context.model_audit import model_run_id


def test_model_run_identity_is_prompt_and_subject_scoped():
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    base = dict(org_id="org_1", site="resolution", subject_ref="event:1",
                prompt_version="m4.v1", prompt_hash="abc", model_snapshot="model-1",
                called_at=now)
    assert model_run_id(**base) == model_run_id(**base)
    assert model_run_id(**base) != model_run_id(**{**base, "prompt_hash": "def"})
    assert model_run_id(**base) != model_run_id(
        **{**base, "called_at": now + timedelta(seconds=1)})


def test_model_run_table_is_erased_on_tenant_reset():
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES

    assert "l2_model_runs" in _ORG_SCOPED_TABLES
