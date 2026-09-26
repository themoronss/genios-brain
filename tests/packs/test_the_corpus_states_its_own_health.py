"""L2-0-U4/U5 · the corpus counts its own refusals, per domain, by named reason.

⛔ **THIS UNIT EXISTS BECAUSE A NUMBER NOBODY COULD PRINT WAS WRONG FOR WEEKS AND WAS PLANNED
AGAINST.** The Layer 2 plan recorded *"534 capabilities, 200 admissible (37%), so
`require_admission=True` at cutover takes 334 dark"* and built step 4 and step 8 around it.

Measured 2026-09-24: **155 capabilities, 155 admissible, 0 hollow.** The 534 counted FILES —
`capability.yaml` + `objects.yaml` + `knowledge.yaml` are three files of ONE capability — and the
37% was that file count divided into a capability count. `require_admission=True` takes **zero**
dark, which makes the cutover free rather than expensive.

`capability_resolver._hollow`'s own docstring still says *"136 of the corpus's capabilities are
stable, approved and hash-pinned over a file whose own notes read 'Phase 1 stub'"*. True when
written; the corpus has since been authored out from under it. **A count in prose is a count that
goes stale**, and this repository has caught that exact drift five times.

So the rule is not "assert 155". It is: **the corpus can be asked, in one call, and the answer
comes from the SAME function the compiler admits with** — never a second copy that can disagree.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from genios_engine.packs.compiler.authoring import ExpertBrainCatalog
from genios_engine.packs.compiler.capability_resolver import (
    _admission_reason, _hollow, corpus_health, domain_health,
)

CORPUS_ROOT = "Domain Expertise"


@pytest.fixture(scope="module")
def catalog() -> ExpertBrainCatalog:
    return ExpertBrainCatalog(CORPUS_ROOT)


def test_every_authored_domain_is_counted(catalog):
    """A domain the catalog loaded and the report omits is a silent domain."""
    health = corpus_health(catalog)
    assert set(health) == set(catalog.domains), (
        "the health report and the catalog disagree about which domains exist")


def test_the_totals_close(catalog):
    """admitted + inadmissible = total, per domain. An unexplained remainder is a hidden set."""
    for domain, row in corpus_health(catalog).items():
        assert row.admitted + row.inadmissible == row.total, (
            f"{domain}: {row.admitted} + {row.inadmissible} != {row.total}")
        assert row.hollow <= row.admitted, (
            f"{domain}: a hollow capability is one that WAS admitted; "
            f"{row.hollow} hollow cannot exceed {row.admitted} admitted")


def test_the_report_reads_the_compilers_own_rule_and_not_a_copy(catalog):
    """⛔ Two hand-kept copies of one rule drift. The report must call `_admission_reason`."""
    for domain, record in catalog.domains.items():
        expected_bad = sum(1 for c in record.capabilities.values() if _admission_reason(c))
        expected_hollow = sum(1 for c in record.capabilities.values() if _hollow(c))
        row = corpus_health(catalog)[domain]
        assert row.inadmissible == expected_bad
        assert row.hollow == expected_hollow


def test_a_capability_that_goes_stub_is_counted_with_its_reason(catalog):
    """Sensitivity — technique 3. Neutralise the corpus's health and the report must see it."""
    record = next(iter(catalog.domains.values()))
    victim = next(iter(record.capabilities.values()))
    broken = replace(victim, content={**victim.content,
                                      "identity": {**victim.content["identity"], "stub": True}})
    assert _admission_reason(broken) == "stub", (
        "the probe does not actually break admission, so it proves nothing")

    row = domain_health(record.domain.id, {**record.capabilities, victim.id: broken})
    assert row.inadmissible == 1
    assert row.by_reason.get("stub") == 1, (
        "the reason must be NAMED — 'one inadmissible' does not tell an author what to fix")


def test_every_reason_the_rule_can_give_has_a_row(catalog):
    """A reason that appears only when it fires is a reason nobody knows exists.

    The same declared-silence idiom as `UNROUTED_PATTERN_TYPES` and `lane_health.SILENT_LANES`:
    the table carries a row per member, at zero, so the shape of the answer never depends on the
    data. `identity_status_*` is generated from the file's own value and cannot be enumerated, so
    it carries one representative row rather than being omitted.
    """
    from genios_engine.packs.compiler.capability_resolver import ADMISSION_REASONS

    for row in corpus_health(catalog).values():
        assert set(row.by_reason) == set(ADMISSION_REASONS), (
            "the reason table must be built from the rule, not from what happened to fire")


def test_the_measured_corpus_is_healthy_and_says_so(catalog):
    """⛔ Not a pin. It records what was measured on 2026-09-24 and where the plan was wrong.

    If an author adds a stub tomorrow this goes red, and that is the point: the number stops
    being a sentence in a plan and becomes something a run can contradict.
    """
    health = corpus_health(catalog)
    total = sum(r.total for r in health.values())
    admitted = sum(r.admitted for r in health.values())
    assert total == 155, (
        f"the corpus is {total} capabilities, not 155 — update the plan's denominator; "
        f"the 534 in the plan counted FILES, three per capability")
    assert admitted == total, (
        f"{total - admitted} capabilities would go dark under require_admission=True; "
        f"the plan's cutover cost is no longer zero")


# =================================================================================================
# The SECOND half of the ceremony — the authored SITUATIONS, which have their own rule.
#
# ⛔ THE PRE-FLIGHT MIXED THREE DOCUMENT KINDS INTO ONE DENOMINATOR. It counted every YAML under
# `capabilities/` — `capability.yaml` + `objects.yaml` + `knowledge.yaml` + the situation files
# nested beside them — and applied the CAPABILITY rule to all of them. Hence "534 authored, 200
# admissible, 63% inadmissible". Three kinds, three rules, one number.
#
# The situation rule is deliberately different and says so: NO CONTENT HASH, because a situation
# file carries no `admission` block. And its consequence is not a drop — `admission_gaps` ->
# `plan.admitted=False` -> `review_state='draft'` -> `_apply_abstention` downgrades the card to an
# OBSERVATION. **The intelligence still ships; it stops instructing.**
# =================================================================================================

def test_authored_situations_are_counted_by_their_own_rule(catalog):
    """A situation is not a capability and must not be judged by the capability ceremony."""
    from genios_engine.packs.compiler.capability_resolver import situation_admission_reason

    for domain, record in catalog.domains.items():
        expected = sum(1 for s in record.situations.values()
                       if situation_admission_reason(s.content))
        row = corpus_health(catalog)[domain]
        assert row.situations == len(record.situations)
        assert row.situations_unreviewed == expected


def test_a_draft_situation_is_reported_because_its_card_cannot_instruct(catalog):
    """⛔ **The consequence is in the rule's own docstring** — a draft situation's package goes
    `review_state='draft'`, `_apply_abstention` downgrades the card to an OBSERVATION, and the
    founder is told a thing is happening without being told what to do about it.

    Measured 2026-09-24: **24 of 69**, and 16 of those are Customer Support's 20. A one-word edit
    per file, by an author. The report exists so somebody knows which twenty-four.

    ⛔ **IT FELL TO 23 ON 2026-09-26, AND THIS MESSAGE ASKED TO BE TOLD SO.**
    `admin.sit.document_under_control` went `draft -> stable` and was re-stamped with
    `Domain Expertise/_tools/admit.py --accept`. It was the one draft situation whose block was a
    LAG rather than a review: it already carried `review_status: approved` and
    `reviewed_by: harsh`, and its own note said the gap it was authored to name *"turned out to be
    a projection rather than a connector… and now bound"*.

    That note was verified before the flip rather than taken on trust: Admin is the only domain
    that declares the `document` anchor, `spec_for("admin").type_for("document")` returns
    `document_under_control`, the situation matches exactly that type, and
    `context/document_register.py` writes it. So the binding is real and the `draft` was stale.

    ⛔ **The remaining 23 are NOT one more edit each.** Admin's 7 split two ways: four are declared
    `pending_l2_types` in `registry/situation-capability-map.yaml` and MUST NOT be flipped — one of
    them records that flipping it *"would cost a false assurance"* — and three carry
    `review_status: unreviewed`, meaning no human has read their prose. Those three need a named
    reviewer, which is the half of the ceremony no tool may perform.
    """
    health = corpus_health(catalog)
    total = sum(r.situations for r in health.values())
    unreviewed = sum(r.situations_unreviewed for r in health.values())
    assert total == 69, f"the corpus has {total} authored situations, not 69 — update the plan"
    assert unreviewed == 23, (
        f"{unreviewed} authored situations cannot instruct, not 23. If this FELL, say so in the "
        f"findings — it is the cheapest quality win in Layer 2 and it is authoring, not code")
    assert health["customer_support"].situations_unreviewed == 16, (
        "Customer Support carries two thirds of the gap and that concentration is the finding")


def test_the_situation_rule_is_read_and_not_reimplemented(catalog):
    """⛔ Sensitivity, technique 3 — make the two rules DISAGREE and see which the report obeys.

    On today's corpus both rules happen to give the same answer, which is exactly when a wrong
    rule is invisible. So a situation is edited after its acceptance: the CAPABILITY rule then
    says `content_changed_since_acceptance`, and the SITUATION rule says nothing, because it
    checks no hash — *"a situation file carries no `admission` block to put one in"*.

    The report must follow the situation rule. If it followed the other, every edited situation
    would be reported as unable to instruct when it is perfectly able to.
    """
    from genios_engine.packs.compiler.capability_resolver import situation_admission_reason

    record = catalog.domains["admin"]
    sid, original = next((k, v) for k, v in record.situations.items()
                         if situation_admission_reason(v.content) is None)
    edited = replace(original, content={**original.content, "description": "edited after review"})

    assert _admission_reason(edited) == "content_changed_since_acceptance"
    assert situation_admission_reason(edited.content) is None, (
        "the two rules do not disagree on this probe, so it proves nothing")

    row = domain_health("admin", record.capabilities, {**record.situations, sid: edited})
    assert row.situations_unreviewed == _BASELINE_ADMIN_DRAFTS, (
        "the report counted an edited-but-reviewed situation as unable to instruct — it is "
        "applying the capability ceremony to a situation, which is the mistake that produced "
        "the plan's 63%-inadmissible headline")


#: Admin's own draft count. Named rather than inlined so the sensitivity test above reads as
#: "unchanged by the edit" instead of as a second magic number.
#:
#: ⛔ 8 on 2026-09-24, **7 from 2026-09-26**: `admin.sit.document_under_control` was flipped to
#: `stable` and re-stamped, its binding having been verified rather than assumed. Of the seven that
#: remain, four are declared `pending_l2_types` and must stay draft, and three are awaiting a named
#: human reviewer. See the docstring above.
_BASELINE_ADMIN_DRAFTS = 7
