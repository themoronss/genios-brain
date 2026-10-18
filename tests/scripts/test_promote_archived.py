"""STEP-05 · an operator promotes one tenant's archived mail back to kept — by the rule that archived it.

    pytest tests/scripts/test_promote_archived.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_promote_archived.py -q

`scripts/promote_archived.py` (tree `yc2_w27_s05 · M23.C4.L-interface.V4.U04`). For Boardy's introductions,
archived on their unsubscribe header (N-02), once Rohit says. Dry run by default; the dry run lists event
ids, dates and sender domains and never a mail's words; `--apply` promotes, and the next chain pass reads
them (`capture/landing/promote`, `unread.queue_unread`).
"""
from __future__ import annotations

import ast
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "promote_archived.py"
WORDS = "Pankaj, meet Meera"


def _module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("promote_archived", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_target_is_resolved_through_the_guard_with_no_fallback():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    called = {getattr(n.func, "id", None) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "resolve_database_url" in called and "get_settings" not in called


def test_the_org_and_the_rule_are_required():
    mod = _module()
    with pytest.raises(SystemExit):
        mod.parse_args([])
    with pytest.raises(SystemExit):
        mod.parse_args(["--org", "o"])


def test_a_rule_the_gate_never_archives_with_is_refused_before_any_database():
    with pytest.raises(SystemExit, match="archives with"):
        _module().main(["--org", "o", "--rule", "N-05"])          # no --database-url given


@pytest.fixture
def tenant():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from sqlalchemy import create_engine, text

    from genios_engine.contracts.source_event import compute_dedup_key
    from genios_engine.platform.config import get_settings
    from genios_engine.platform.crypto import encrypt

    org = f"org_promote_cli_{uuid.uuid4().hex[:8]}"
    eng = create_engine(url)
    at = datetime.now(timezone.utc) - timedelta(days=2)
    events = [f"evt_{uuid.uuid4().hex[:12]}" for _ in range(2)]
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'promotion cli')"), {"o": org})
        for event_id, sender in zip(events, ("hello@boardy.test", "news@letters.test")):
            c.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, "
                " source_object_id, dedup_key, actor, occurred_at, captured_at, outcome, "
                " attention, attention_reason) values (:e, :o, 'con_x', 'gmail', 'email_message', "
                " :e, :dk, cast(:a as jsonb), :at, :at, 'archived', 'archive', 'N-02')"),
                {"e": event_id, "o": org, "at": at,
                 "dk": compute_dedup_key("gmail", "email_message", event_id, None),
                 "a": json.dumps({"type": "external_contact", "email": sender})})
            c.execute(text(
                "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, "
                " expires_at) values (:id, :o, :e, 'application/json', :enc, :exp)"),
                {"id": f"pay_{event_id}", "o": org, "e": event_id,
                 "enc": encrypt(json.dumps({"subject": "Intro", "body": WORDS}),
                                get_settings().crypto_key),
                 "exp": at + timedelta(days=180)})
    yield url, eng, org, events
    with eng.begin() as c:
        for table in ("raw_payloads", "source_events"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        c.execute(text("delete from orgs where id = :o"), {"o": org})


def _outcomes(eng, org) -> dict[str, str]:
    from sqlalchemy import text
    with eng.connect() as c:
        return dict(c.execute(text("select event_id, outcome from source_events where org_id = :o"),
                              {"o": org}).fetchall())


@pytest.mark.pg
def test_a_dry_run_lists_without_words_and_apply_promotes_only_what_it_named(tenant, capsys):
    url, eng, org, (boardy, letters) = tenant
    mod = _module()
    assert mod.main(["--org", org, "--rule", "N-02", "--sender-domain", "boardy.test",
                     "--database-url", url]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and boardy in out and letters not in out and WORDS not in out
    assert _outcomes(eng, org) == {boardy: "archived", letters: "archived"}

    assert mod.main(["--org", org, "--rule", "N-02", "--sender-domain", "boardy.test",
                     "--database-url", url, "--apply"]) == 0
    assert "PROMOTED 1" in capsys.readouterr().out
    assert _outcomes(eng, org) == {boardy: "emitted", letters: "archived"}
