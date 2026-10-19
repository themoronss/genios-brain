"""GeniOS-008 L2 · THE PASS — every subject a new L1 bundle touched, reasoned once, in shadow.

The run, exactly as `speedrun008/GeniOS-008/layer-2-reasoning/02-PLAN.md` §3 and `06-GAP-ANALYSIS.md` §3 draw it:

  R1  request     the bundles stored since this pass's watermark (`signal_bundles`, L1 E1), grouped by subject
                  (`inputs.read_subjects`: the file that holds their events, else their own thread); plus the
                  subjects whose evidence need was MET since (`evidence.reentries`) — trigger `new_evidence`;
  —   ours        a file whose counterparty is us is never a subject (the expert pass's rule, `03` F158);
  R2  snapshot    the bounded read around the subject (`snapshot.read_snapshot`), its revision kept;
  R3  history     comparable past work of the same kind (`history.history_for`);
  R4  expertise   the file's STEP-12 dossier whole — brief, playbook, numbers with n, corrections, what was
                  judged before — or, for a seed, the company brief;
  R7  tools       the arithmetic (`tools.run_tools`), at `now`;
  R5  plan        the depth and why (`plan.compile_plan`);
  STEP-02 gate    the fingerprint — the subject's inputs with every clock removed — and a standing row for it
                  answers: no call. A row that failed lately waits; one carried for budget waits a day;
  R6  judge       nearest due first, at most `MAX_PER_PASS` a pass, through R-9's gate (`judge.judge`);
  R8  needs       the decision-changing needs of each result, filed for L1;
  G1  write       every row, every need and the watermark, in ONE transaction at the end.

⛔ SHADOW. It writes `reasoning_results` and `evidence_needs` and nothing else: no card, no signal, no
situation. It runs after the expert pass in `reason/runner.run_all`, wrapped — a failure here costs this
pass's shadow rows, never the sweep.

⛔ THE WATERMARK NEVER PASSES A SUBJECT IT DID NOT REACH. A subject carried (the per-pass cap, the day's
budget, a read that failed) holds the watermark at its oldest bundle, so the next sweep reads it again; a
subject already answered reads as unchanged and costs nothing.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

from genios_engine.contracts.reasoning_result import (ENDED_OVER_BUDGET, TRIGGER_BUNDLE,
                                                      TRIGGER_NEW_EVIDENCE, L2Request, ReasoningReceipt,
                                                      stable_ref)
from genios_engine.platform.l4_activation import FEATURE_L2_REASONING, activated_features
from genios_engine.platform.logging import get_logger
from genios_engine.reason import llm_sites
from genios_engine.reason.bundle.budget import NarrativeBudget
from genios_engine.reason.bundle.gate import RSiteGate
from genios_engine.reason.bundle.sites import SITE_REASON, tier_for
from genios_engine.reason.bundle.store import BundleStore

from . import evidence, store as results
from .dossier import L2_DOSSIER_VERSION, build_l2_dossier
from .history import history_for
from .inputs import Subject, read_signals, read_subjects, seed_of
from .judge import judge
from .plan import PLAN_VERSION, compile_plan
from .prompt import PROMPT_VERSION, depth_note
from .snapshot import read_snapshot, seeds_for
from .tools import measured_inputs, run_tools

_log = get_logger("genios.reason.l2.sweep")

MAX_PER_PASS = 10
RETRY_FAILED_AFTER = timedelta(hours=6)
#: Each clock the tools read is a RUNG in the fingerprint, never a value: "past due" moves it, every hour does not.
_DUE_RUNGS = (-24, 0, 24, 48, 168)


def _rung(hours: Any) -> int | None:
    if not isinstance(hours, (int, float)):
        return None
    return sum(1 for r in _DUE_RUNGS if hours >= r)


def fingerprint_of(subject: Subject, *, file_inputs: Any, need_states: dict[str, str], model: str | None,
                   tools: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """The subject's inputs with every clock removed — the STEP-02 change gate's measure. Pure."""
    due = tools.get("nearest_due") if isinstance(tools.get("nearest_due"), dict) else {}
    inputs = {
        "subject": subject.subject_ref,
        "signals": sorted([s.signal_id, s.state, s.ball_in_court, s.due_at.isoformat() if s.due_at else None]
                          for s in subject.signals),
        "file": file_inputs,
        "needs": sorted(need_states.items()),
        "due_rung": _rung(due.get("hours")) if due else None,
        "who_decides": {"model": model, "prompt": PROMPT_VERSION, "dossier": L2_DOSSIER_VERSION,
                        "plan": PLAN_VERSION},
    }
    return stable_ref("l2fp", inputs), inputs


def _waiting(row: Any, now: datetime) -> str | None:
    if row is None:
        return None
    if row.status == results.FAILED and now - row.reasoned_at < RETRY_FAILED_AFTER:
        return "failed_lately"
    if row.status == results.OVER_BUDGET and row.reasoned_at.astimezone(timezone.utc).date() == \
            now.astimezone(timezone.utc).date():
        return "carried_today"
    return None


def _reentry_subject(conn, org_id: str, subject_ref: str, bundle_ids: tuple[str, ...], files: list,
                     met_at: datetime | None = None) -> Subject | None:
    from genios_engine.capture.esqe.bundle_store import read_bundles_by_id
    bundles = read_bundles_by_id(conn, org_id, bundle_ids)
    signals = read_signals(conn, org_id, (s for b in bundles for s in b.signal_ids))
    file_id = subject_ref.split(":", 1)[1] if subject_ref.startswith("file:") else None
    if file_id is None and not signals:
        return None
    seed = None if file_id else (seed_of(bundles[0], list(signals.values())) if bundles else None)
    # L2 rebuild A3 · the instant its need was met is where the watermark must stay if this run is not reached:
    # without it a carried re-entry let the watermark pass `closed_at`, and the met need was never read again.
    return Subject(subject_ref=subject_ref, file_id=file_id, seed_key=seed, bundle_ids=tuple(bundle_ids),
                   signals=tuple(signals.values()), coverage=tuple(dict(b.coverage) for b in bundles if b.coverage),
                   trigger=TRIGGER_NEW_EVIDENCE, oldest_bundle_at=met_at)


def l2_pass(*, store, org_id: str, now: datetime | None = None, llm=None, budget: NarrativeBudget | None = None,
            max_per_pass: int = MAX_PER_PASS) -> dict[str, Any]:
    """Reason every subject new bundles touched, once. Returns the pass's receipt; never raises past a subject."""
    now = now or datetime.now(timezone.utc)
    engine = getattr(store, "engine", None)
    if engine is None:
        return {"skipped": "no_engine"}
    activated = activated_features(engine, org_id)
    if FEATURE_L2_REASONING not in activated:
        return {"skipped": "l2_reasoning_not_activated"}
    client = llm if llm is not None else llm_sites.make_site_client(tier_for(SITE_REASON))
    if client is None:
        return {"skipped": "no_model_configured"}
    model = getattr(client, "model", None) or llm_sites.tier_model(tier_for(SITE_REASON))

    from sqlalchemy import text

    from genios_engine.context.workstreams import files_for
    from genios_engine.platform.company_brief import brief_for
    from genios_engine.platform.self_identity import identity_for, names_us
    from genios_engine.reason.expert.dossier import build_dossier, people_of, read_parts
    from genios_engine.reason.expert.fingerprint import fingerprint_inputs
    from genios_engine.reason.expert.prompt import PROMPT_VERSION as EXPERT_PROMPT

    receipt: dict[str, Any] = {"subjects": 0, "ours": 0, "unchanged": 0, "waiting": Counter(), "unreadable": 0,
                               "ended": Counter(), "not_reached": Counter(), "carried": 0, "needs_filed": 0,
                               "reentries": 0, "lanes": Counter(), "depths": Counter(), "cost_micro_usd": 0}
    with engine.connect() as conn:
        files = files_for(conn, org_id, now=now).files
        us = identity_for(conn, org_id)
        org = conn.execute(text("select name, company from orgs where id = :o"), {"o": org_id}).first()
        brief = brief_for(conn, org_id)
        after = results.read_watermark(conn, org_id)
        subjects, newest = read_subjects(conn, org_id, after=after, files=files)
        seen = {s.subject_ref for s in subjects}
        for subject_ref, bundle_ids, met_at in evidence.reentries(conn, org_id, since=after):
            if subject_ref not in seen:
                again = _reentry_subject(conn, org_id, subject_ref, bundle_ids, files, met_at)
                if again is not None:
                    subjects.append(again)
                    receipt["reentries"] += 1
    our_names = tuple(n for n in (getattr(org, "company", None), getattr(org, "name", None)) if n)
    by_file = {str(f.file_id): f for f in files}
    brief_block = brief.prompt_block().strip() if brief is not None and brief else None
    receipt["subjects"] = len(subjects)
    held: list[datetime] = []          # the oldest bundle of each subject not reached — the watermark stays there

    # L2 rebuild A1 + A2 · THE GATE BEFORE THE READS, THE CAP BEFORE THE READS.
    #
    # The fingerprint is made of the subject's signals, its file's parts, its needs' states and the due rung —
    # never of the snapshot or the history. Those two were read for every subject first (~50 round trips each)
    # and then thrown away for every unchanged subject and for every subject past `max_per_pass`. Now a subject
    # is first read only as far as its fingerprint (one connection for all of them), the standing rows answer,
    # the rest are ordered nearest-due first, and only the ones that WILL be judged read their snapshot and
    # history. What a judged subject is shown is unchanged.
    due: list[tuple] = []
    with engine.connect() as conn:
        for order, subject in enumerate(subjects):
            work = by_file.get(subject.file_id) if subject.file_id else None
            if work is not None and (us.is_us_node(work.counterparty_type, work.counterparty_key)
                                     or names_us(work.counterparty, us, names=our_names)):
                receipt["ours"] += 1
                continue
            try:
                parts = file_dossier = people = None
                if subject.file_id:
                    parts = read_parts(conn, org_id, subject.file_id, now=now)
                    if parts is not None:
                        file_dossier = build_dossier(parts)
                        people = people_of(parts, us=us, our_names=our_names)
                latest = results.latest_result(conn, org_id, subject.subject_ref)
                asked = tuple((latest.receipt or {}).get("needs_raised") or ()) if latest is not None else ()
                # L2 rebuild · an OPEN need is the question the last run asked, not something that arrived: only
                # a SETTLED one (met / unavailable) is new input. Counting `open` made every run that raised a need
                # look changed on the next read of the same inputs — one more model call for nothing.
                states = {k: v for k, v in evidence.need_states(conn, org_id, asked).items() if v != "open"}
                tools = run_tools(subject.signals, eval_time=now, file=getattr(parts, "file", None))
                measured = measured_inputs(tools)
                asked_deeper = None
                if latest is not None and isinstance(latest.result, dict):
                    asked_deeper = ((latest.result.get("judgment") or {}).get("deeper"))
                importance = max((s.importance_bp for s in subject.signals if s.importance_bp is not None),
                                 default=None)
                file_inputs = fingerprint_inputs(parts, model=model, prompt_version=EXPERT_PROMPT) if parts else None
                fp, _inputs = fingerprint_of(subject, file_inputs=file_inputs, need_states=states, model=model,
                                             tools=measured)
                row = results.read_result(conn, org_id, subject.subject_ref, fp)
            except Exception:      # noqa: BLE001 — one unreadable subject is not a failed pass
                _log.exception("the L2 pass could not read subject=%s org=%s", subject.subject_ref, org_id)
                conn.rollback()    # the shared connection reads on for the next subject
                receipt["unreadable"] += 1
                if subject.oldest_bundle_at is not None:
                    held.append(subject.oldest_bundle_at)
                continue
            if row is not None and row.status in results.STANDING:
                receipt["unchanged"] += 1
                continue
            waiting = _waiting(row, now)
            if waiting:
                receipt["waiting"][waiting] += 1
                if subject.oldest_bundle_at is not None:
                    held.append(subject.oldest_bundle_at)
                continue
            hours = (measured.get("nearest_due") or {}).get("hours") if isinstance(measured.get("nearest_due"), dict) else None
            key = (hours if hours is not None else float("inf"), -(importance or 0), order)
            due.append((key, subject, parts, file_dossier, people, tools, measured, importance, asked_deeper, fp))

    due.sort(key=lambda d: d[0])
    if len(due) > max_per_pass:
        receipt["carried"] += len(due) - max_per_pass
        held.extend(d[1].oldest_bundle_at for d in due[max_per_pass:] if d[1].oldest_bundle_at is not None)
        due = due[:max_per_pass]
    ready: list[tuple] = []
    with engine.connect() as conn:
        for (_key, subject, parts, file_dossier, people, tools, measured, importance, asked_deeper, fp) in due:
            try:
                snapshot = read_snapshot(conn, org_id, seeds_for(conn, org_id, file_id=subject.file_id,
                                                                 events=subject.events))
                history = history_for(conn, org_id, files=files,
                                      work_kind=getattr(getattr(parts, "file", None), "work_kind", None),
                                      exclude=subject.file_id)
            except Exception:      # noqa: BLE001 — one unreadable subject is not a failed pass
                _log.exception("the L2 pass could not read subject=%s org=%s", subject.subject_ref, org_id)
                conn.rollback()
                receipt["unreadable"] += 1
                if subject.oldest_bundle_at is not None:
                    held.append(subject.oldest_bundle_at)
                continue
            plan = compile_plan(tools=measured, file_id=subject.file_id, unresolved=subject.unresolved,
                                truncated=snapshot.truncated,
                                situations=len(getattr(getattr(parts, "lifecycle", None), "situations", ()) or ()),
                                importance_bp=importance, asked_deeper=asked_deeper)
            ready.append((subject, parts, file_dossier, people, snapshot, history, tools, measured, plan, fp))

    gate = RSiteGate(org_id=org_id, engine=engine, client=client, store=BundleStore(engine), activated=activated,
                     budget=budget or NarrativeBudget.for_site(SITE_REASON, org_id=org_id, engine=engine, now=now),
                     cost_recorder=getattr(store, "record_cost", None), eval_time=now)
    rows: list[results.L2Row] = []
    needs = []
    for i, (subject, parts, file_dossier, people, snapshot, history, tools, measured, plan, fp) in enumerate(ready):
        request = L2Request(org_id=org_id, subject_ref=subject.subject_ref,
                            trigger=subject.trigger if subject.trigger else TRIGGER_BUNDLE, eval_time=now,
                            bundle_ids=subject.bundle_ids, fingerprint=fp)
        dossier = build_l2_dossier(org_id=org_id, subject=subject, as_of=now, snapshot=snapshot, history=history,
                                   tools=tools, file_dossier=file_dossier,
                                   brief_block=None if file_dossier is not None else brief_block,
                                   depth_note=depth_note(plan))
        expertise_ref = stable_ref("pkg", {"dossier": file_dossier.digest if file_dossier is not None else None,
                                           "brief": brief_block, "prompt": PROMPT_VERSION})
        judged = judge(org_id=org_id, request_ref=request.request_id, dossier=dossier, plan=plan, gate=gate,
                       fingerprint=fp, context_ref=snapshot.ref, expertise_ref=expertise_ref, at=now, people=people)
        rcpt = judged.receipt
        receipt["cost_micro_usd"] += int(getattr(rcpt, "cost_micro_usd", 0) or 0)
        if judged.ended is None:
            receipt["not_reached"][judged.reason or "unknown"] += 1
            if subject.oldest_bundle_at is not None:
                held.append(subject.oldest_bundle_at)
            continue
        receipt["ended"][judged.ended] += 1
        receipt["depths"][plan.depth] += 1
        result = judged.result
        raised = []
        if result is not None:
            raised = evidence.needs_from(result, org_id=org_id, trace_id=request.request_id, eval_time=now)
            needs.extend(raised)
            receipt["lanes"][result.lane] += 1
        audit = ReasoningReceipt(
            request_ref=request.request_id, org_id=org_id, subject_ref=subject.subject_ref, trigger=request.trigger,
            context_ref=snapshot.ref, expertise_ref=expertise_ref, depth=plan.depth, depth_why=plan.why,
            groups_run=plan.groups_run, groups_skipped=plan.groups_skipped,
            tool_results={k: v for k, v in measured.items()}, model=rcpt.model or model,
            prompt_version=PROMPT_VERSION, calls=int(getattr(rcpt, "attempts", 0) or 0), termination=judged.ended,
            validation=result.problems if result is not None else (), needs_raised=evidence.ids_of(raised),
            output_hash=result.output_hash() if result is not None else None,
            cost_micro_usd=int(getattr(rcpt, "cost_micro_usd", 0) or 0), bundle_ids=subject.bundle_ids)
        if result is not None:
            result = replace(result, receipt_ref=audit.ref)
        rows.append(results.L2Row(
            org_id=org_id, subject_ref=subject.subject_ref, fingerprint=fp, request_id=request.request_id,
            trigger=request.trigger, status=judged.ended, reason=judged.reason, depth=plan.depth,
            lane=result.lane if result is not None else None,
            lane_reason=result.lane_reason if result is not None else None,
            result=result.as_mapping() if result is not None else judged.raw, receipt=audit.as_mapping(),
            dossier={"text": dossier.text, "evidence_ids": sorted(dossier.catalogue.evidence_ids),
                     "numbers": sorted(dossier.catalogue.numbers), "stages": list(dossier.catalogue.stages)},
            model=rcpt.model or model, prompt_version=PROMPT_VERSION,
            input_tokens=int(getattr(rcpt, "input_tokens", 0) or 0),
            output_tokens=int(getattr(rcpt, "output_tokens", 0) or 0),
            cost_micro_usd=int(getattr(rcpt, "cost_micro_usd", 0) or 0), reasoned_at=now,
            bundle_ids=subject.bundle_ids))
        if judged.ended == ENDED_OVER_BUDGET:
            receipt["carried"] += len(ready) - i - 1
            held.extend(d[0].oldest_bundle_at for d in ready[i:] if d[0].oldest_bundle_at is not None)
            break

    watermark = newest
    if held and newest is not None:
        watermark = min(min(held) - timedelta(microseconds=1), newest)
        if after is not None and watermark <= after:
            watermark = None           # nothing new can be passed over: keep the old one
    try:
        from genios_engine.context.evidence_need_store import store_needs
        with engine.begin() as conn:
            receipt["written"] = results.write_sweep(conn, rows, org_id=org_id, watermark=watermark)
            receipt["needs_filed"] = store_needs(conn, needs)
    except Exception:      # noqa: BLE001 — a shadow write that failed loses this pass's rows, not the sweep
        _log.exception("the L2 pass could not write its %d row(s) org=%s", len(rows), org_id)
        receipt["write_failed"] = True
    for k in ("waiting", "ended", "not_reached", "lanes", "depths"):
        receipt[k] = dict(receipt[k])
    if rows or receipt["carried"]:
        _log.info("the L2 pass org=%s %s", org_id, {k: v for k, v in receipt.items() if k != "subjects"})
    return receipt


__all__ = ["MAX_PER_PASS", "RETRY_FAILED_AFTER", "fingerprint_of", "l2_pass"]
