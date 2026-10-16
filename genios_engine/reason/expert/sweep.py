"""The expert pass — each file that changed, reviewed once, in the sweep (STEP-12).

Tree `yc2_w27_s12` M32.C3.L-integration.V2.U04. It runs FIRST in `reason/runner.run_all`, ahead of the
compiled lane (M33.C1.L-integration.V2.U07), for a tenant with the L4 feature `expert_review` on — read
ONCE, so a switch flipped halfway cannot leave two files of one pass judged under different rules:

  1. every file of the tenant (`context/workstreams.files_for`), each read once into its dossier's parts
     (`dossier.read_parts`), and its fingerprint (`fingerprint.fingerprint_inputs`) — except a file whose
     counterparty is US: a node of ours (`platform/self_identity.is_us_node` — a domain only when
     declared, as STEP-04 rules) or one NAMED for the company or the founder as the tenant records them
     (`names_us`, whole words). We are never the subject, and a mail that names the founder's own company
     must not buy a review of it (`03` F158);
  2. a fingerprint a standing review answers is UNCHANGED — no call;
  3. a file nothing touched since its last standing review is UNTOUCHED — no call (`05` §5,
     `triggers.triggers_for`);
  4. a fingerprint whose review FAILED lately waits `RETRY_FAILED_AFTER`, and one carried for want of
     budget waits for the next day — the day's budget is spent;
  5. the rest NEAREST MEETING OR DEADLINE FIRST (a past-due promise first of all; a file with neither
     last), at most `MAX_PER_PASS` a pass, each reviewed once (`review.review_file`) through ONE gate
     with the expert's own budget (`06` D7: $2 a day). The first refusal for want of budget stops the
     pass: the files it did not reach are CARRIED, counted — "a busy day reviews the nearest deadlines
     first and carries the rest, said";
  6. a valid review that proposes a kind of work — the proposal standing its check — writes the founder
     a proposal (`kind_proposal.propose_kind`).

WHAT IS CHECKED (STEP-13, `yc2_w27_s13` M35.C3.L-integration.V1.U01). Every review is checked before it
covers anything (`reason/expert/verify`, against the file's people — `dossier.people_of`): a review written
now is checked by the run that writes it; a standing valid review checked under an older check version is
checked again before it covers.

⛔ WHEN A VERSION MOVES (`06` D48, answered 12 Oct; M35.C3.L-integration.V1.U06 — the crosscheck's X11, X13). A
prompt or check version change re-checks each standing review against the dossier it was reviewed on — the row
keeps it (0202, `review.recheck`) — and the file is reviewed again only when the file moved. MOVED is the
fingerprint's own measure: its inputs (the events, the asks, whose move, the clocks as rungs, the brief, the
playbook, the verdicts, the answers) beside what the review saw (`expert_reviews.inputs`), who decides aside —
never a digest of today's dossier, which moves with the clock. A file whose fingerprint a standing review
answers did not move: its review is checked again. A quiet file nothing triggered, whose last review was
written or checked under another version: checked again when it is the file that review saw, reviewed again
(`VERSION_MOVED`, inside the day's budget, nearest first) when it moved — and covered by the review that stood
until that review is written, so a version change never uncovers a file. Before D48 a check bump counted such a
file `unchecked` and decided it per situation again, its file card never cleared; a prompt bump re-reviewed
nothing.

THE ENGINE (STEP-13b, `yc2_w27_s13b` M37.C5.L-integration.V11.U03). Every file is read once for its fingerprint, which names
the engine it reads cheaply (its route key and the learned brains' snapshot, `fingerprint`), and the company's record
and the tenant's switched-on corpora are read ONCE a pass. The engine itself — the Domain Expertise of the file's
situations and kind, what the brains learned, the units in shadow — is read for the files DUE for review only (at most
`MAX_PER_PASS`); the receipt counts the reads (`engine_reads`), what they cut (`engine_cut`), the reads that could not
be made (`engine_unread`: the file is still reviewed, on its data) and the files whose engine moved (`engine_moved`).
A file whose ONLY triggers are `engine_moved` or `self_moved` is reviewed again and COVERED meanwhile by the review that
stands (checked again first when the check moved): its facts did not. A fingerprint input a review stored before this
step never named (`engine`, `self`) is read as `none` on both sides — a deploy moves no file by itself (s13b-F6).

WHAT IT COVERS (M33.C1.L-data.V0.U06). The receipt says which files a VALID review now answers —
`covered`, file → the fingerprint of that review — for the compiled lane to decide each once, from it,
its situations standing down (`reason/domain_shadow`, M33.C1.L-integration.V1.U02, under `06` D1). A file
is covered when the review that stands for it is valid: its fingerprint's own (unchanged), the last one
when nothing has touched the file since (untouched), or the one written this pass. Never a file that is
ours, one whose review was refused or cut, one waiting on a failed review or carried for want of budget —
the file moved and nothing has judged it yet — and never a file the pass could not read: each of those
is decided as before, situation by situation. A tenant without the feature or without a model covers
nothing. Beside it, `people` (M33.C1.L-data.V1.U11): each covered file's people — the anchor when it is a
person, everyone who works at it when it is a company (`context/workstreams.WorkFile.people`) — so either
lane can tell what belongs to a file (`reason/expert/cover`) without reading the files again.

The sweep runs this pass FIRST and hands `covered` to the compiled lane (M33.C1.L-integration.V2.U07),
which decides each covered file from its review; the pass itself writes reviews and proposals, never a
decision. A tenant without the feature, or with no model configured, costs no file read. Never raises
past a file: one file that cannot be read is counted and the pass goes on.
"""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

from genios_engine.platform.l4_activation import FEATURE_EXPERT_REVIEW, activated_features
from genios_engine.platform.logging import get_logger
from genios_engine.reason.bundle.budget import NarrativeBudget
from genios_engine.reason.bundle.gate import RSiteGate
from genios_engine.reason.bundle.sites import SITE_EXPERT, expert_ladder, tier_for
from genios_engine.reason.bundle.store import BundleStore
from genios_engine.reason import llm_sites

from . import store as reviews
from genios_engine.contracts.claim_check import CHECK_VERSION, REFUSED as CHECK_REFUSED

from .dossier import build_dossier, people_of, read_parts
from .fingerprint import NONE, file_fingerprint, fingerprint_inputs, nearest_due
from .kind_proposal import propose_kind
from .prompt import PROMPT_VERSION
from .ladder import Rung
from .review import recheck, review_file
from .triggers import ENGINE_MOVED, SELF_MOVED, triggers_for

_log = get_logger("genios.reason.expert.sweep")

#: How many files one pass may review. A tenant switched on after months of mail must not spend its
#: first sweep — or its first day's budget — on the files that matter least: the nearest go first and
#: the rest are carried to the next sweep, counted.
MAX_PER_PASS = 10

#: How long a fingerprint whose review failed waits before it is tried again — a network blip is
#: retried within the day, an answer that stays misshapen does not spend every sweep's budget.
RETRY_FAILED_AFTER = timedelta(hours=6)

#: What a review written because a version moved says triggered it (`06` D48) — beside the file's own
#: triggers (`reason/expert/triggers.KINDS`), and never one of them: a version is no change in the file.
VERSION_MOVED = "version_moved"
#: The triggers that say the file's FACTS did not move — only what it reads beside them did (STEP-13b): the file is
#: reviewed again, and covered by the review that stands until it is.
_SOFT = frozenset({ENGINE_MOVED, SELF_MOVED})
#: The fingerprint input that names who decides — the model, the prompt, the dossier's version. Whether the file
#: MOVED is read with it set aside (D48).
_WHO_DECIDES = "who_decides"


def _current(row) -> bool:
    """Was this standing review written and checked under the versions in force?"""
    return (row.checked is not None and row.checked.version == CHECK_VERSION
            and row.prompt_version == PROMPT_VERSION)


#: The inputs a review stored before STEP-13b never named: read as `none` on both sides, so a deploy that names them
#: moves no file by itself (`triggers.engine_moved` is the door a file's engine takes, and says what moved).
_NAMED_LATER = ("engine", "self")


def _comparable(inputs: dict) -> dict:
    """A fingerprint's inputs as files are compared: who decides aside, the later-named inputs read as `none`."""
    return {**{k: NONE for k in _NAMED_LATER}, **{k: v for k, v in inputs.items() if k != _WHO_DECIDES}}


def _same_file(then, now) -> bool:
    """Is the file the one its review saw (D48)? The fingerprint's inputs alike, who decides aside. A row that
    kept no inputs (before 0198) saw a file nobody can compare: it moved."""
    return isinstance(then, dict) and _comparable(then) == _comparable(now)


def _version_trigger(row) -> dict[str, str]:
    """Why a file is reviewed again though nothing in it triggered: the versions that moved, from what to what."""
    moved = []
    then = row.checked.version if row.checked is not None else "none"
    if then != CHECK_VERSION:
        moved.append(f"the check moved: {then} → {CHECK_VERSION}")
    if row.prompt_version != PROMPT_VERSION:
        moved.append(f"the prompt moved: {row.prompt_version} → {PROMPT_VERSION}")
    return {"kind": VERSION_MOVED, "says": "; ".join(moved)}


def _hours_to_nearest(parts) -> float:
    """Hours to the file's next meeting or nearest promised date — negative when past due; a file
    with neither is never near."""
    dates = [t.at for t in parts.timeline.upcoming[:1]]
    due = nearest_due(parts)
    if due is not None:
        dates.append(due)
    return min((d - parts.as_of).total_seconds() / 3600 for d in dates) if dates else math.inf


def _waiting(row, now: datetime) -> str | None:
    """Why a fingerprint with a retryable row waits this pass, or None."""
    if row is None:
        return None
    if row.status == reviews.FAILED and now - row.reviewed_at < RETRY_FAILED_AFTER:
        return "failed_lately"
    if row.status == reviews.OVER_BUDGET and row.reviewed_at.astimezone(timezone.utc).date() == \
            now.astimezone(timezone.utc).date():
        return "carried_today"
    return None


def _cover(receipt: dict[str, Any], file_id: str, fingerprint: str, people) -> None:
    """A file a VALID review answers now: that review's fingerprint, and who is in the file."""
    receipt["covered"][file_id] = fingerprint
    receipt["people"][file_id] = sorted(str(p) for p in people or ())


def _with_engine(engine, org_id: str, parts, *, now, kind_numbers, domains_on, record, receipt):
    """The parts of a file DUE for review, with the engine read beside them (STEP-13b) — the Domain Expertise of its
    situations and kind, what the brains learned, the units in shadow — read for due files only, at most
    `MAX_PER_PASS` a pass. The receipt counts the read, what it cut, and a read that could not be made: the expert is
    then shown the data alone, as before. Never raises: a file whose engine cannot be read is still reviewed."""
    try:
        with engine.connect() as conn:
            full = read_parts(conn, org_id, parts.file_id, now=now, kind_numbers=kind_numbers, engine=True,
                              domains_on=domains_on, company_record=record)
    except Exception:      # noqa: BLE001 — see the docstring
        _log.exception("the engine could not be read for file=%s org=%s", parts.file_id, org_id)
        receipt["engine_unread"] += 1
        return parts
    if full is None:
        return parts
    if full.engine_error is not None:
        receipt["engine_unread"] += 1
    elif full.engine is not None:
        receipt["engine_reads"] += 1
        receipt["engine_cut"] += sum(full.engine.cut.values())
    return full


def _clients(llm, ladder, *, allow_opus: bool) -> list[tuple[str, Any]] | None:
    """The rungs' clients, cheapest first, as `(tier, client)` — or None when no model is configured. `llm` is a lone
    client (asked once, on the site's own tier), a mapping of tier → client (a ladder of those tiers), or None:
    production's — `ladder` (default `sites.expert_ladder`: Haiku-class then Sonnet-class; Opus-class only when the
    tenant allows it, off for all, s13b-D1), each tier's client from `llm_sites.make_site_client`."""
    if llm is not None and not isinstance(llm, Mapping):
        return [(tier_for(SITE_EXPERT), llm)]
    tiers = expert_ladder(sorted(llm) if llm is not None else ladder, allow_opus=allow_opus)
    made = [(tier, llm[tier] if llm is not None else llm_sites.make_site_client(tier)) for tier in tiers]
    return None if any(client is None for _tier, client in made) else made


def expert_pass(*, store, org_id: str, now: datetime | None = None, llm=None,
                budget: NarrativeBudget | None = None, max_per_pass: int = MAX_PER_PASS,
                ladder: tuple[str, ...] | None = None, allow_opus: bool = False) -> dict[str, Any]:
    """Review every changed file of the tenant once. Returns the pass's receipt; never raises past a file.

    STEP-13b: the file's review climbs a LADDER — `ladder` names its rungs (default Haiku-class then Sonnet-class),
    `allow_opus` the tenant's leave for an Opus-class third (off for all). `llm`: a lone client (asked once), or a
    mapping of tier → client for a ladder of those tiers."""
    now = now or datetime.now(timezone.utc)
    engine = getattr(store, "engine", None)
    if engine is None:
        return {"skipped": "no_engine"}
    activated = activated_features(engine, org_id)
    if FEATURE_EXPERT_REVIEW not in activated:
        return {"skipped": "expert_review_not_activated"}
    # The R-sites' own door, read when the pass runs — what production's wiring sets and the golden
    # runner opens (`tests/replays/engine_runner.py`); a name bound at import would never see it.
    clients = _clients(llm, ladder, allow_opus=allow_opus)
    if clients is None:
        return {"skipped": "no_model_configured"}

    from genios_engine.context.kind_numbers import numbers_for_kind
    from genios_engine.context.workstreams import files_for
    receipt: dict[str, Any] = {"files": 0, "ours": 0, "unchanged": 0, "untouched": 0, "unreadable": 0,
                               "waiting": Counter(), "reviewed": Counter(), "carried": 0,
                               "proposed_kinds": 0, "cost_micro_usd": 0, "covered": {}, "people": {},
                               "unchecked": 0, "checked": Counter(), "rechecked": 0, "version_moved": 0,
                               "engine_reads": 0, "engine_cut": 0, "engine_unread": 0, "engine_moved": 0,
                               "attempts": Counter(), "climbs": Counter(), "cost_by_tier": Counter(),
                               "stood": Counter()}
    due = []
    from sqlalchemy import text

    from genios_engine.context.company_record import read_company_record
    from genios_engine.platform.l3_activation import activated_domains
    from genios_engine.platform.self_identity import identity_for, names_us
    with engine.connect() as conn:
        files = files_for(conn, org_id, now=now).files
        us = identity_for(conn, org_id)
        org = conn.execute(text("select name, company from orgs where id = :o"), {"o": org_id}).first()
        # ONCE a pass (STEP-13b, `06` D63): what the company says of itself in its own kept mail, across every file,
        # and the corpora this tenant has switched on. A record that cannot be read is no record: the pass goes on.
        try:
            record = read_company_record(conn, org_id, now=now)
        except Exception:      # noqa: BLE001 — see above
            _log.exception("the company's record could not be read org=%s", org_id)
            record = None
    domains_on = activated_domains(engine, org_id)
    our_names = tuple(n for n in (getattr(org, "company", None), getattr(org, "name", None)) if n)
    receipt["files"] = len(files)
    # STEP-16 (M47.C2.L-logic.V4.U02): your numbers for a kind of work, measured ONCE a pass over its files — every
    # dossier of the kind reads the same numbers, whichever file the pass reads first (all are read before any is
    # reviewed), and no file reads the tenant's files again.
    kind_files: dict[str, tuple[str, ...]] = {}
    for work in files:
        if work.work_kind:
            kind_files[work.work_kind] = (*kind_files.get(work.work_kind, ()), work.file_id)
    numbers_by_kind: dict[str, Any] = {}
    for order, work in enumerate(files):
        if us.is_us_node(work.counterparty_type, work.counterparty_key) \
                or names_us(work.counterparty, us, names=our_names):
            receipt["ours"] += 1
            continue
        try:
            with engine.connect() as conn:
                if work.work_kind and work.work_kind not in numbers_by_kind:
                    numbers_by_kind[work.work_kind] = numbers_for_kind(conn, org_id, work.work_kind, now=now,
                                                                       files=kind_files[work.work_kind])
                parts = read_parts(conn, org_id, work.file_id, now=now, kind_numbers=numbers_by_kind,
                                   domains_on=domains_on, company_record=record)
                if parts is None:
                    receipt["unreadable"] += 1
                    continue
                inputs = fingerprint_inputs(parts, prompt_version=PROMPT_VERSION)
                fp = file_fingerprint(parts, prompt_version=PROMPT_VERSION)
                people = people_of(parts, us=us, our_names=our_names)
                row = reviews.read_review(conn, org_id, work.file_id, fp)
            if row is not None and row.status in reviews.STANDING:
                receipt["unchanged"] += 1
                if row.status == reviews.VALID:
                    checked = row.checked
                    if checked is None or checked.version != CHECK_VERSION:
                        # The same fingerprint is the same file (D48): checked again, on the dossier it was
                        # reviewed on — the check kept, and when it ran.
                        checked = recheck(row, people, today=build_dossier(parts))
                        with engine.begin() as conn:
                            reviews.write_check(conn, org_id=org_id, file_id=work.file_id,
                                                fingerprint=fp, checked=checked, at=now)
                        receipt["rechecked"] += 1
                    receipt["checked"][checked.fate] += 1
                    if checked.fate != CHECK_REFUSED:
                        _cover(receipt, work.file_id, fp, work.people)
                continue
            with engine.connect() as conn:
                waiting = _waiting(row, now)
                if waiting:
                    receipt["waiting"][waiting] += 1
                    continue
                last = reviews.latest_standing(conn, org_id, work.file_id)
            found = triggers_for(parts, inputs, last=last)
            if any(t.kind == ENGINE_MOVED for t in found):
                receipt["engine_moved"] += 1
            if found and last is not None and last.status == reviews.VALID and last.checked is not None \
                    and all(t.kind in _SOFT for t in found):
                # Only what the file reads beside its facts moved: the review that stands keeps covering it until
                # the new one is written — checked again first when the check moved (never a bump that uncovers).
                if last.checked.version != CHECK_VERSION:
                    checked = recheck(last, people, today=build_dossier(parts))
                    with engine.begin() as conn:
                        reviews.write_check(conn, org_id=org_id, file_id=work.file_id,
                                            fingerprint=last.fingerprint, checked=checked, at=now)
                    receipt["rechecked"] += 1
                    last = replace(last, checked=checked)
                if last.checked.fate != CHECK_REFUSED:
                    _cover(receipt, work.file_id, last.fingerprint, work.people)
            if not found:
                receipt["untouched"] += 1
                if last is None or last.status != reviews.VALID:
                    continue
                if not _current(last):
                    if _same_file(last.inputs, inputs):
                        # A version moved and the file did not (D48): its review checked again, on its own
                        # dossier — when it is the check that moved.
                        if last.checked is None or last.checked.version != CHECK_VERSION:
                            checked = recheck(last, people, today=build_dossier(parts))
                            with engine.begin() as conn:
                                reviews.write_check(conn, org_id=org_id, file_id=work.file_id,
                                                    fingerprint=last.fingerprint, checked=checked, at=now)
                            receipt["rechecked"] += 1
                            receipt["checked"][checked.fate] += 1
                            last = replace(last, checked=checked)
                    else:
                        # A version moved AND the file moved since its review (D48): reviewed again, inside the
                        # day's budget — covered meanwhile by the review that stood, never uncovered by a bump.
                        receipt["version_moved"] += 1
                        due.append((_hours_to_nearest(parts), order, parts, inputs, fp,
                                    [_version_trigger(last)], people))
                if last.checked is not None and last.checked.fate != CHECK_REFUSED:
                    _cover(receipt, work.file_id, last.fingerprint, work.people)
                else:
                    receipt["unchecked"] += 1
                continue
            due.append((_hours_to_nearest(parts), order, parts, inputs, fp, found, people))
        except Exception:      # noqa: BLE001 — one unreadable file is not a failed pass
            _log.exception("the expert pass could not read file=%s org=%s", work.file_id, org_id)
            receipt["unreadable"] += 1

    due.sort(key=lambda d: (d[0], d[1]))
    # ⛔ THE LEDGER. Every consult is a row of `l4_r_site_calls` (the gate's receipt), and the expert's
    # own budget opens each pass from today's R-7 rows there — without it, `06` D7's $2 a day would
    # bind within one pass and never across a day's passes.
    day = budget or NarrativeBudget.for_site(SITE_EXPERT, org_id=org_id, engine=engine, now=now)
    gates = [(tier, RSiteGate(org_id=org_id, engine=engine, client=client, store=BundleStore(engine),
                              activated=activated, budget=day,
                              cost_recorder=getattr(store, "record_cost", None), eval_time=now))
             for tier, client in clients]
    # ONE DAY FOR EVERY RUNG: the rungs' gates share the day's budget. A lone client (a test's, a caller's) is asked once
    # as before; a ladder of clients (production's, or a mapping of tiers) climbs.
    rungs = None if (llm is not None and not isinstance(llm, Mapping)) else [Rung(tier, gate) for tier, gate in gates]
    gate = gates[0][1]
    for i, (_hours, _order, parts, inputs, fp, found, people) in enumerate(due):
        if i >= max_per_pass:
            receipt["carried"] += len(due) - i
            break
        parts = _with_engine(engine, org_id, parts, now=now, kind_numbers=numbers_by_kind, domains_on=domains_on,
                             record=record, receipt=receipt)
        result = review_file(engine, org_id=org_id, dossier=build_dossier(parts), fingerprint=fp,
                             inputs=inputs, triggers=found, gate=gate, at=now, people=people, parts=parts,
                             ladder=rungs)
        receipt["reviewed"][result.status or "skipped"] += 1
        if result.status == reviews.VALID:
            receipt["checked"][result.checked.fate] += 1
            _cover(receipt, parts.file_id, fp, parts.file.people)
        receipt["cost_micro_usd"] += result.cost_micro_usd
        for attempt in result.attempts:
            receipt["attempts"][f"{attempt.tier}:{attempt.consult}"] += 1
            if attempt.climbed_because:
                receipt["climbs"][attempt.climbed_because] += 1
            receipt["cost_by_tier"][attempt.tier] += attempt.cost_micro_usd
        if result.rung is not None and result.status == reviews.VALID:
            receipt["stood"][f"T{result.rung}"] += 1
        if result.status == reviews.OVER_BUDGET:
            receipt["carried"] += len(due) - i - 1
            break
        if result.status == reviews.VALID and result.review.proposed_kind is not None \
                and result.checked.stands("kind"):
            try:
                with engine.begin() as conn:
                    if propose_kind(conn, org_id=org_id, review=result.review, file=parts.file,
                                    fingerprint=fp, at=now, why=result.checked.words.kind).line_id:
                        receipt["proposed_kinds"] += 1
            except Exception:      # noqa: BLE001 — a proposal that failed is no failed pass
                _log.exception("the expert's kind proposal failed file=%s org=%s",
                               parts.file_id, org_id)
                receipt["unreadable"] += 1
    receipt["waiting"] = dict(receipt["waiting"])
    receipt["reviewed"] = dict(receipt["reviewed"])
    receipt["checked"] = dict(receipt["checked"])
    for key in ("attempts", "climbs", "cost_by_tier", "stood"):
        receipt[key] = dict(receipt[key])
    if receipt["reviewed"] or receipt["carried"]:
        _log.info("the expert pass org=%s %s", org_id, receipt)
    return receipt


__all__ = ["MAX_PER_PASS", "RETRY_FAILED_AFTER", "VERSION_MOVED", "expert_pass"]
