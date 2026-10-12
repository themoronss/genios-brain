"""STEP-18 B20, its second half · every wipe of mail events deletes their fingerprints first.

    pytest tests/test_every_mail_wipe_takes_its_fingerprints.py -q

`yc2_w27_s18` M48.C3.L-data.V0.U11 (L1 Signals, `capture/`, and its scripts), STEP-18 §8.3 s18-F2.

⛔ WHAT WAS WRONG. A message's fingerprint claim names the event that first carried it, and a claim
by an event with no row is still honoured (`capture/screen/fingerprint._without_set_aside_claims`:
*"Deleting events is the caller's to clean up"*). `ba0577e3` taught the disconnect-with-wipe to
delete a source's fingerprints with its events; `scripts/gmail_l1.py` still deleted the gmail events
and left their fingerprints, so a re-run of it skipped every re-synced message as `seen_on_screen`
and extracted nothing — silently.

The rule, read off the AST of every module in `genios_engine/` and `scripts/`: a module that deletes
`source_events` deletes `message_fingerprints` before it — or is declared below, with why its events
are never fingerprinted (`capture/pipeline._seen_on_screen` claims gmail and outlook mail only, and
the screen promoter its own sessions).
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Modules that delete `source_events` of kinds no fingerprint is ever taken of, and why.
NOT_A_MESSAGE: dict[str, str] = {
    "genios_engine/api/upload_routes.py": "an uploaded file's events (`upload`), by their own ids — "
                                          "only gmail and outlook mail and screen sessions are "
                                          "fingerprinted",
    "genios_engine/api/knowledge_routes.py": "the tenant's internal knowledge (`source = "
                                             "'internal'`), by their own ids — never mail, never "
                                             "fingerprinted",
    "scripts/pause_notion_email.py": "Notion's events (`source = 'notion'`) — never fingerprinted",
}


def _deletes(source: str) -> list[tuple[int, str]]:
    """(line, the table) for every string in the module that begins `delete from <table>`."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            words = " ".join(node.value.lower().split()).split(" ")
            if words[:2] == ["delete", "from"] and len(words) > 2:
                out.append((node.lineno, words[2]))
    return sorted(out)


def _modules() -> dict[str, list[tuple[int, str]]]:
    found = {}
    for folder in ("genios_engine", "scripts"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            deletes = _deletes(path.read_text(encoding="utf-8"))
            if any(table == "source_events" for _line, table in deletes):
                found[str(path.relative_to(ROOT))] = deletes
    return found


def test_the_reader_finds_a_delete_in_a_list_and_in_a_call():
    """The positive control: `gmail_l1` keeps its statements in a list, the routes in `text()`."""
    src = ('SQL = ["delete from message_fingerprints where org_id=:o",\n'
           '       "delete from source_events where org_id=:o"]\n'
           'c.execute(text("delete  from  raw_payloads where 1=1"))\n')
    assert _deletes(src) == [(1, "message_fingerprints"), (2, "source_events"), (3, "raw_payloads")]


def test_every_mail_wipe_deletes_the_fingerprints_before_the_events():
    offenders = {}
    for module, deletes in _modules().items():
        if module in NOT_A_MESSAGE:
            continue
        events = min(line for line, table in deletes if table == "source_events")
        prints = [line for line, table in deletes if table == "message_fingerprints"]
        if not prints or min(prints) > events:
            offenders[module] = deletes
    assert offenders == {}, (
        "a wipe of mail events leaves their fingerprints: every re-synced message would be skipped "
        f"as seen_on_screen. Delete `message_fingerprints` first, or declare why: {offenders}")


def test_the_disconnect_and_the_l1_script_are_both_read():
    """Two wipes are known to take mail: if either stops deleting events, this file's premise moved."""
    modules = _modules()
    assert "genios_engine/api/routes.py" in modules
    assert "scripts/gmail_l1.py" in modules


def test_no_declaration_is_stale():
    """A declared module that no longer deletes events is a declaration nobody can check."""
    assert set(NOT_A_MESSAGE) <= set(_modules()), set(NOT_A_MESSAGE) - set(_modules())
