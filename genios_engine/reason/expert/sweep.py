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
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

from genios_engine.platform.l4_activation import FEATURE_EXPERT_REVIEW, FEATURE_L2_CARDS, activated_features
from genios_engine.platform.logging import get_logger
from genios_engine.reason.bundle.budget import NarrativeBudget
from genios_engine.reason.bundle.gate import RSiteGate
from genios_engine.reason.bundle.sites import SITE_EXPERT, tier_for
from genios_engine.reason.bundle.store import BundleStore
from genios_engine.reason import llm_sites

from . import store as reviews
from genios_engine.contracts.claim_check import CHECK_VERSION, REFUSED as CHECK_REFUSED

from .dossier import build_dossier, people_of, read_parts
from .fingerprint import file_fingerprint, fingerprint_inputs, nearest_due
from .kind_proposal import propose_kind
from .prompt import PROMPT_VERSION
from .review import recheck, review_file
from .triggers import triggers_for

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
#: The fingerprint input that names who decides — the model, the prompt, the dossier's version. Whether the file
#: MOVED is read with it set aside (D48).
_WHO_DECIDES = "who_decides"


def _current(row) -> bool:
    """Was this standing review written and checked under the versions in force?"""
    return (row.checked is not None and row.checked.version == CHECK_VERSION
            and row.prompt_version == PROMPT_VERSION)


def _same_file(then, now) -> bool:
    """Is the file the one its review saw (D48)? The fingerprint's inputs alike, who decides aside. A row that
    kept no inputs (before 0198) saw a file nobody can compare: it moved."""
    return isinstance(then, dict) and ({k: v for k, v in then.items() if k != _WHO_DECIDES}
                                       == {k: v for k, v in now.items() if k != _WHO_DECIDES})


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


def expert_pass(*, store, org_id: str, now: datetime | None = None, llm=None,
                budget: NarrativeBudget | None = None, max_per_pass: int = MAX_PER_PASS) -> dict[str, Any]:
    """Review every changed file of the tenant once. Returns the pass's receipt; never raises past a file."""
    now = now or datetime.now(timezone.utc)
    engine = getattr(store, "engine", None)
    if engine is None:
        return {"skipped": "no_engine"}
    activated = activated_features(engine, org_id)
    if FEATURE_EXPERT_REVIEW not in activated:
        return {"skipped": "expert_review_not_activated"}
    # L2 rebuild C1 · with `l2_cards` the Layer 2 judgment writes a file's review (`reason/l2/sweep`): this pass
    # still reads every file, answers from the standing reviews and covers what they decide — and makes NO R-7
    # call. A file that moved is the L2 pass's to judge (`to_l2`), so a file is judged once and paid once.
    l2_judges = FEATURE_L2_CARDS in activated
    # The R-sites' own door, read when the pass runs — what production's wiring sets and the golden
    # runner opens (`tests/replays/engine_runner.py`); a name bound at import would never see it.
    client = None if l2_judges else (llm if llm is not None else llm_sites.make_site_client(tier_for(SITE_EXPERT)))
    if client is None and not l2_judges:
        return {"skipped": "no_model_configured"}
    model = getattr(client, "model", None) or llm_sites.tier_model(tier_for(SITE_EXPERT))

    from genios_engine.context.kind_numbers import numbers_for_kind
    from genios_engine.context.workstreams import files_for
    receipt: dict[str, Any] = {"files": 0, "ours": 0, "unchanged": 0, "untouched": 0, "unreadable": 0,
                               "waiting": Counter(), "reviewed": Counter(), "carried": 0,
                               "proposed_kinds": 0, "cost_micro_usd": 0, "covered": {}, "people": {},
                               "unchecked": 0, "checked": Counter(), "rechecked": 0, "version_moved": 0}
    due = []
    from sqlalchemy import text

    from genios_engine.platform.self_identity import identity_for, names_us
    with engine.connect() as conn:
        files = files_for(conn, org_id, now=now).files
        us = identity_for(conn, org_id)
        org = conn.execute(text("select name, company from orgs where id = :o"), {"o": org_id}).first()
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
                parts = read_parts(conn, org_id, work.file_id, now=now, kind_numbers=numbers_by_kind)
                if parts is None:
                    receipt["unreadable"] += 1
                    continue
                inputs = fingerprint_inputs(parts, model=model, prompt_version=PROMPT_VERSION)
                fp = file_fingerprint(parts, model=model, prompt_version=PROMPT_VERSION)
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
    if l2_judges:
        receipt["to_l2"] = len(due)
        receipt["waiting"] = dict(receipt["waiting"])
        receipt["reviewed"] = dict(receipt["reviewed"])
        receipt["checked"] = dict(receipt["checked"])
        return receipt
    # ⛔ THE LEDGER. Every consult is a row of `l4_r_site_calls` (the gate's receipt), and the expert's
    # own budget opens each pass from today's R-7 rows there — without it, `06` D7's $2 a day would
    # bind within one pass and never across a day's passes.
    gate = RSiteGate(org_id=org_id, engine=engine, client=client, store=BundleStore(engine),
                     activated=activated,
                     budget=budget or NarrativeBudget.for_site(SITE_EXPERT, org_id=org_id,
                                                               engine=engine, now=now),
                     cost_recorder=getattr(store, "record_cost", None), eval_time=now)
    for i, (_hours, _order, parts, inputs, fp, found, people) in enumerate(due):
        if i >= max_per_pass:
            receipt["carried"] += len(due) - i
            break
        result = review_file(engine, org_id=org_id, dossier=build_dossier(parts), fingerprint=fp,
                             inputs=inputs, triggers=found, gate=gate, at=now, people=people, parts=parts)
        receipt["reviewed"][result.status or "skipped"] += 1
        if result.status == reviews.VALID:
            receipt["checked"][result.checked.fate] += 1
            _cover(receipt, parts.file_id, fp, parts.file.people)
        if result.receipt is not None:
            receipt["cost_micro_usd"] += result.receipt.cost_micro_usd
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
    if receipt["reviewed"] or receipt["carried"]:
        _log.info("the expert pass org=%s %s", org_id, receipt)
    return receipt


__all__ = ["MAX_PER_PASS", "RETRY_FAILED_AFTER", "VERSION_MOVED", "expert_pass"]
