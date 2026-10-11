"""The expert pass — each file that changed, reviewed once, in the sweep, in shadow (STEP-12).

Tree `yc2_w27_s12` M32.C3.L-integration.V2.U04. It runs at the end of `reason/runner.run_all`, beside the
narration, for a tenant with the L4 feature `expert_review` on — read ONCE, so a switch flipped halfway
cannot leave two files of one pass judged under different rules:

  1. every file of the tenant (`context/workstreams.files_for`), each read once into its dossier's parts
     (`dossier.read_parts`), and its fingerprint (`fingerprint.fingerprint_inputs`) — except a file whose
     counterparty is US (`platform/self_identity.is_us_node`): we are never the subject (STEP-04), and a
     mail that names the founder's own company must not buy a review of it (`03` F158);
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
  6. a valid review that proposes a kind of work writes the founder a proposal
     (`kind_proposal.propose_kind`).

SHADOW. Nothing reads a review for a decision yet (M33); like the narration, this pass cannot change
what the sweep decided. A tenant without the feature, or with no model configured, costs no file read.
Never raises past a file: one file that cannot be read is counted and the pass goes on.
"""
from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from genios_engine.platform.l4_activation import FEATURE_EXPERT_REVIEW, activated_features
from genios_engine.platform.logging import get_logger
from genios_engine.reason.bundle.budget import NarrativeBudget
from genios_engine.reason.bundle.gate import RSiteGate
from genios_engine.reason.bundle.sites import SITE_EXPERT, tier_for
from genios_engine.reason.bundle.store import BundleStore
from genios_engine.reason import llm_sites

from . import store as reviews
from .dossier import build_dossier, read_parts
from .fingerprint import file_fingerprint, fingerprint_inputs, nearest_due
from .kind_proposal import propose_kind
from .prompt import PROMPT_VERSION
from .review import review_file
from .triggers import triggers_for

_log = get_logger("genios.reason.expert.sweep")

#: How many files one pass may review. A tenant switched on after months of mail must not spend its
#: first sweep — or its first day's budget — on the files that matter least: the nearest go first and
#: the rest are carried to the next sweep, counted.
MAX_PER_PASS = 10

#: How long a fingerprint whose review failed waits before it is tried again — a network blip is
#: retried within the day, an answer that stays misshapen does not spend every sweep's budget.
RETRY_FAILED_AFTER = timedelta(hours=6)


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
    # The R-sites' own door, read when the pass runs — what production's wiring sets and the golden
    # runner opens (`tests/replays/engine_runner.py`); a name bound at import would never see it.
    client = llm if llm is not None else llm_sites.make_site_client(tier_for(SITE_EXPERT))
    if client is None:
        return {"skipped": "no_model_configured"}
    model = getattr(client, "model", None) or llm_sites.tier_model(tier_for(SITE_EXPERT))

    from genios_engine.context.workstreams import files_for
    receipt: dict[str, Any] = {"files": 0, "ours": 0, "unchanged": 0, "untouched": 0, "unreadable": 0,
                               "waiting": Counter(), "reviewed": Counter(), "carried": 0,
                               "proposed_kinds": 0, "cost_micro_usd": 0}
    due = []
    from genios_engine.platform.self_identity import identity_for
    with engine.connect() as conn:
        files = files_for(conn, org_id, now=now).files
        us = identity_for(conn, org_id)
    receipt["files"] = len(files)
    for order, work in enumerate(files):
        if us.is_us_node(work.counterparty_type, work.counterparty_key):
            receipt["ours"] += 1
            continue
        try:
            with engine.connect() as conn:
                parts = read_parts(conn, org_id, work.file_id, now=now)
                if parts is None:
                    receipt["unreadable"] += 1
                    continue
                inputs = fingerprint_inputs(parts, model=model, prompt_version=PROMPT_VERSION)
                fp = file_fingerprint(parts, model=model, prompt_version=PROMPT_VERSION)
                row = reviews.read_review(conn, org_id, work.file_id, fp)
                if row is not None and row.status in reviews.STANDING:
                    receipt["unchanged"] += 1
                    continue
                waiting = _waiting(row, now)
                if waiting:
                    receipt["waiting"][waiting] += 1
                    continue
                last = reviews.latest_standing(conn, org_id, work.file_id)
            found = triggers_for(parts, inputs, last=last)
            if not found:
                receipt["untouched"] += 1
                continue
            due.append((_hours_to_nearest(parts), order, parts, inputs, fp, found))
        except Exception:      # noqa: BLE001 — one unreadable file is not a failed pass
            _log.exception("the expert pass could not read file=%s org=%s", work.file_id, org_id)
            receipt["unreadable"] += 1

    due.sort(key=lambda d: (d[0], d[1]))
    # ⛔ THE LEDGER. Every consult is a row of `l4_r_site_calls` (the gate's receipt), and the expert's
    # own budget opens each pass from today's R-7 rows there — without it, `06` D7's $2 a day would
    # bind within one pass and never across a day's passes.
    gate = RSiteGate(org_id=org_id, engine=engine, client=client, store=BundleStore(engine),
                     activated=activated,
                     budget=budget or NarrativeBudget.for_site(SITE_EXPERT, org_id=org_id,
                                                               engine=engine, now=now),
                     cost_recorder=getattr(store, "record_cost", None), eval_time=now)
    for i, (_hours, _order, parts, inputs, fp, found) in enumerate(due):
        if i >= max_per_pass:
            receipt["carried"] += len(due) - i
            break
        result = review_file(engine, org_id=org_id, dossier=build_dossier(parts), fingerprint=fp,
                             inputs=inputs, triggers=found, gate=gate, at=now)
        receipt["reviewed"][result.status or "skipped"] += 1
        if result.receipt is not None:
            receipt["cost_micro_usd"] += result.receipt.cost_micro_usd
        if result.status == reviews.OVER_BUDGET:
            receipt["carried"] += len(due) - i - 1
            break
        if result.status == reviews.VALID and result.review.proposed_kind is not None:
            with engine.begin() as conn:
                if propose_kind(conn, org_id=org_id, review=result.review, file=parts.file,
                                fingerprint=fp, at=now).line_id:
                    receipt["proposed_kinds"] += 1
    receipt["waiting"] = dict(receipt["waiting"])
    receipt["reviewed"] = dict(receipt["reviewed"])
    if receipt["reviewed"] or receipt["carried"]:
        _log.info("the expert pass org=%s %s", org_id, receipt)
    return receipt


__all__ = ["MAX_PER_PASS", "RETRY_FAILED_AFTER", "expert_pass"]
