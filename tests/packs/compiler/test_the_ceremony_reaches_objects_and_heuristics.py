r"""Plane D · the admission ceremony reaches the two layers it had never been performed on.

⛔ WHAT WAS WRONG. `_admission_reason` asks a named human to accept a CAPABILITY's bytes.
`situation_admission_reason` asks the same of a SITUATION's words. An OBJECT and a HEURISTIC were
asked **nothing at all** — measured 2026-09-30:

    capabilities   155   all stable + approved + hash-accepted
    objects         75   66 draft, ZERO carrying an admission hash
    heuristics     283   218 draft, ZERO carrying an admission hash

⛔ And `heuristics/` is where `reads:` lives — the declaration of which objects a piece of doctrine
consults. **The widest surface in the corpus by file count is the one where somebody can change what
the expertise looks at, silently.**

⛔ IT REPORTS, IT DOES NOT GATE. Refusing 284 documents in one step on a corpus whose capabilities
all pass is not a measurement, it is an outage. `card_source` wrote the rule for the other cutover
here: measure both paths on one sweep before either is retired.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import textwrap

import pytest
import yaml

from genios_engine.packs.compiler import expertise_builder as EB
from genios_engine.packs.compiler.capability_resolver import (_admission_reason,
                                                              artifact_admission_reason,
                                                              situation_admission_reason)

REPO = pathlib.Path(__file__).resolve().parents[3]
CORPUS = REPO / "Domain Expertise"


# ── the verdicts ──────────────────────────────────────────────────────────────────────────────

def test_a_reviewed_document_passes():
    assert artifact_admission_reason({
        "identity": {"status": "stable"},
        "metadata": {"review_status": "approved", "reviewed_by": "harsh"}}) is None


@pytest.mark.parametrize("status,expected", [
    ("draft", "identity_status_draft"),
    ("deprecated", "identity_status_deprecated"),
    (None, "identity_status_absent"),
])
def test_anything_but_stable_is_named(status, expected):
    doc = {"identity": {} if status is None else {"status": status},
           "metadata": {"review_status": "approved", "reviewed_by": "harsh"}}
    assert artifact_admission_reason(doc) == expected


@pytest.mark.parametrize("review", ["unreviewed", "in_review", None, ""])
def test_anything_but_approved_is_refused(review):
    doc = {"identity": {"status": "stable"},
           "metadata": ({} if review is None else {"review_status": review}) | {"reviewed_by": "h"}}
    assert artifact_admission_reason(doc) == "review_not_approved"


def test_approved_by_nobody_is_refused():
    """⛔ `review_status: approved` with no name is the signature-shaped hole this whole ceremony
    exists to close: *"an author flipping `stub: true -> false` in a text editor granted production
    authority."*"""
    assert artifact_admission_reason({
        "identity": {"status": "stable"},
        "metadata": {"review_status": "approved", "reviewed_by": "  "}}) == "no_named_reviewer"


@pytest.mark.parametrize("doc", [None, {}])
def test_a_malformed_document_fails_closed_rather_than_raising(doc):
    """*"An empty or malformed one must fail closed, not raise into a compile that would then have
    no answer at all."*"""
    assert artifact_admission_reason(doc) == "identity_status_absent"


def test_the_wrong_type_raises_rather_than_answering():
    """⛔ BOTH SIBLINGS CARRY THIS SCAR. A function that turns a caller's type error into a plausible
    data verdict cost this programme two debugging passes against numbers that were never real —
    *"all 69 situations inadmissible"* and *"534 capabilities, 200 admissible"*."""
    class SourceDocumentish:
        content = {"identity": {"status": "stable"}}

    with pytest.raises(TypeError, match="parsed document mapping"):
        artifact_admission_reason(SourceDocumentish())
    with pytest.raises(TypeError):
        artifact_admission_reason("admin.obj.core.deadline")


def test_it_demands_no_content_hash_and_says_why():
    """⛔ No object or heuristic file carries an `admission` block to put one in, and requiring one
    would mean editing 358 files before the guard could be switched on at all — the same reason
    `situation_admission_reason` demands none."""
    assert artifact_admission_reason({
        "identity": {"status": "stable"},
        "metadata": {"review_status": "approved", "reviewed_by": "harsh"}}) is None
    assert "NO CONTENT HASH" in (artifact_admission_reason.__doc__ or "").upper()


def test_it_is_the_same_three_questions_the_other_two_ask():
    """⛔ One ceremony, asked of three kinds of document. Three slightly different ceremonies would
    disagree the first time one was tightened."""
    for fn in (situation_admission_reason, artifact_admission_reason):
        src = inspect.getsource(fn)
        assert 'identity.get("status")' in src
        assert 'metadata.get("review_status")' in src
        assert 'metadata.get("reviewed_by")' in src


def test_the_capability_ceremony_is_still_the_strictest():
    """⛔ It alone checks the content hash. Objects, heuristics and situations are flagged; a
    capability is DROPPED, because its expertise is what the answer is made of."""
    src = inspect.getsource(_admission_reason)
    assert "accepted_content_hash" in src
    assert "accepted_content_hash" not in inspect.getsource(artifact_admission_reason)


# ── it reaches the corpus, and is not vacuous ─────────────────────────────────────────────────

def _corpus(glob: str):
    for dom in sorted(CORPUS.glob("* Expertise")):
        for f in sorted(dom.glob(glob)):
            yield f, (yaml.safe_load(f.read_text()) or {})


def test_the_gate_reaches_every_object_and_returns_both_answers():
    """⛔ A guard that answers the same thing for every document in the corpus is not measuring
    anything — the trap `situation_admission_reason`'s own tests name."""
    verdicts = {artifact_admission_reason(d) for _, d in _corpus("objects/**/*.yaml")}
    assert len(verdicts) > 1, verdicts
    assert None in verdicts, "no object passes — the gate is vacuous in the refusing direction"


def test_the_gate_reaches_every_heuristic_and_returns_both_answers():
    verdicts = {artifact_admission_reason(d) for _, d in _corpus("heuristics/**/*.yaml")}
    assert len(verdicts) > 1, verdicts
    assert None in verdicts


def test_the_ungoverned_surface_is_large_and_that_is_the_finding():
    """⛔ THE MEASUREMENT THIS UNIT EXISTS FOR, KEPT AS A TEST. If these counts collapse, somebody
    reviewed the corpus — good — and this test should be updated with the new numbers rather than
    deleted, because the number is the decision input for whether to start gating."""
    objects = [artifact_admission_reason(d) for _, d in _corpus("objects/**/*.yaml")]
    heuristics = [artifact_admission_reason(d) for _, d in _corpus("heuristics/**/*.yaml")]
    assert len(objects) >= 70 and len(heuristics) >= 280
    assert sum(1 for v in objects if v is not None) >= 60
    assert sum(1 for v in heuristics if v is not None) >= 200


def test_not_one_object_or_heuristic_carries_an_admission_hash():
    """⛔ The other half of the finding, and the reason the hash is not demanded yet."""
    hashed = [f.name for f, d in _corpus("objects/**/*.yaml") if (d.get("admission") or {})]
    hashed += [f.name for f, d in _corpus("heuristics/**/*.yaml") if (d.get("admission") or {})]
    assert hashed == [], hashed


# ── and the count reaches the package, so it is not built and read by nothing ──────────────────

def test_the_builder_puts_both_censuses_on_the_package():
    """⛔ THE DEFECT THIS PROGRAMME HAS FOUND EIGHT TIMES. AST over the returned mapping's keys."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(EB.ExpertiseBuilder.build)))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys |= {k.value for k in node.keys
                     if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    assert "unreviewed_object_ids" in keys
    assert "unreviewed_artifact_ids" in keys


def test_the_builder_calls_the_gate_rather_than_restating_its_rules():
    src = inspect.getsource(EB.ExpertiseBuilder.build)
    assert "artifact_admission_reason(" in src
    assert "review_status" not in src, "the rule is restated in the builder; it must be asked"


def test_the_census_is_kept_apart_from_review_state():
    """⛔ `review_state` is an AUTHORITY verdict; this is a GOVERNANCE census. The codebase already
    states the principle for `hollow_capability_ids`: *"a thin capability is a content gap, an
    unadmitted one is an authority gap, and one number cannot mean both."*"""
    src = inspect.getsource(EB.ExpertiseBuilder.build)
    review_line = [ln for ln in src.splitlines() if '"review_state"' in ln]
    assert review_line, "review_state vanished"
    assert "unreviewed_object_ids" not in review_line[0]
    assert "plan.admitted" in review_line[0], "review_state must still come from admission alone"


def test_nothing_is_gated_on_the_new_census_yet_and_that_is_deliberate():
    """⛔ Refusing 284 documents in one step on a corpus whose capabilities all pass is not a
    measurement, it is an outage. `card_source`: measure both paths on one sweep before retiring
    either. This test fails the day somebody turns it into a refusal WITHOUT removing it — which is
    the moment to re-read why it was a count first."""
    src = inspect.getsource(EB.ExpertiseBuilder.build)
    for node in ast.walk(ast.parse(textwrap.dedent(src))):
        if isinstance(node, ast.Raise):
            raised = ast.unparse(node)
            assert "unreviewed" not in raised, f"the census now refuses: {raised}"
