"""L2-6 · the validator that makes a cheap model safe — deterministic, free, and handed to the gate.

⛔ **§0 IS RIGHT AND THE STEP OWES THE VALIDATOR, NOT A GATE.** `RSiteGate.consult` step 6 is
*"validate the output — the caller's validator"*, step 7 is *"on any failure: deterministic
fallback, recorded — never a retry storm, never silence."* Everything about WHEN a model may be
consulted, what it costs and what happens when it fails is already solved and property-tested.

⛔ **AND THE FOUR CHECKS HAD TO BE RE-AIMED, BECAUSE L2-2 DID NOT BUILD THE FIELDS THEY NAME.**
Check 2 reads `inferred_state → must cite ≥1 observed_fact`. Those fields do not exist: L2-2
measured that v2 is **already full of interpretation** and classified the 28 fields it has instead
of minting six more, deferring the genuinely-absent ones to L2-5 with their writer.

So a PROPOSAL is `{field: value}` over `claim_state.model_writable_fields()` — the list L2-2 built
for exactly this caller: *"L2-5's gate needs this list, and deriving it by hand at the call site is
how the list and the rule stop agreeing."*

**EVERY RULE IS READ, NEVER RE-IMPLEMENTED.** `model_may_write` decides authority, `RECEIPT_REQUIRED`
decides who owes a citation, `fact_write_action` decides what contradiction means, and V-10's
coverage rule decides when emptiness is a claim. A second copy of any of them is a second answer.

⛔ **THE REASON CODE CARRIES THE CHECK AND THE SUBJECT, BECAUSE THE TRACE IS NOT STORED.**
`BundleStore.record_call` persists `reason_codes` as jsonb and **not** `trace`. So
`l2_authority:evidence` is durable and `{"check": ..., "claim": ...}` is not — the same
`<rule>:<subject>` shape L2-2 used for `observed:V-9:anomalies[0]`.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

_RESOLVES_ALL = lambda refs: frozenset(refs)          # noqa: E731
_RESOLVES_NONE = lambda refs: frozenset()             # noqa: E731


def _anomaly(**over):
    from genios_engine.contracts.situation import Anomaly

    base = dict(metric="account.reply_latency", current_bp=9000, baseline_bp=1000, mad_bp=200,
                deviation_bp=8000, z_like_bp=4000, direction="above", periods_used=8,
                evidence_refs=("fv-1",))
    base.update(over)
    return Anomaly.model_construct(**base)


def _validate(proposal, **kw):
    from genios_engine.context.proposal_gate import validate_proposal

    kw.setdefault("resolve_refs", _RESOLVES_ALL)
    kw.setdefault("held_facts", {})
    kw.setdefault("coverage_ready", True)
    kw.setdefault("expected_facts", ())
    return validate_proposal(proposal, **kw)


# =================================================================================================
# The four outcomes — not two
# =================================================================================================

def test_there_are_four_outcomes_and_they_are_closed():
    """⛔ L1 learned this the hard way: a binary gate held 367 candidates and admitted 18."""
    from genios_engine.context.proposal_gate import Outcome

    assert {o.value for o in Outcome} == {"accept", "escalate", "refuse", "unknown"}


def test_a_clean_proposal_is_accepted():
    from genios_engine.context.proposal_gate import Outcome

    verdict = _validate({"anomalies": (_anomaly(),)})
    assert verdict.outcome is Outcome.ACCEPT
    assert verdict.reason_codes == ()


def test_unknown_commits_rather_than_looking_like_a_broken_generation():
    """⛔ **THE OUTCOME THE GATE'S PROTOCOL WOULD HAVE SWALLOWED.** `consult` returns RAN only
    when the validator's value is not None; a `None` is retried and recorded as
    FAILED_VALIDATION. So UNKNOWN — *a real answer* — must arrive as a VALUE, or it is
    indistinguishable from a model that produced garbage. That is the invisible-refusal defect
    L2-0 spent a whole step on."""
    from genios_engine.context.proposal_gate import Outcome

    verdict = _validate({"confidence": None})
    assert verdict.outcome is Outcome.UNKNOWN
    assert verdict.commits is True, "UNKNOWN is an answer; it must reach the gate as a value"


def test_refuse_does_not_commit_and_says_which_check():
    from genios_engine.context.proposal_gate import Outcome

    verdict = _validate({"evidence": ()})
    assert verdict.outcome is Outcome.REFUSE
    assert verdict.commits is False
    assert any(code.startswith("l2_authority:") for code in verdict.reason_codes)


def test_escalate_never_calls_anything_itself():
    """⛔ *"No R-site may call a model directly."* The validator has no client and no budget, so
    ESCALATE is a code the CALLER acts on — a second consult at a higher tier is L2-5's decision,
    not a verdict's side effect.

    ⛔ **ASSERTED OVER THE CODE, NOT THE TEXT, AND THIS MISTAKE HAS NOW BEEN MADE THREE TIMES.**
    L1 step 14 grepped a migration for `" not null"` and matched its own comment; step 18 repeated
    it and recorded that it had been made twice; the first draft of this test grepped this module's
    source for `"client"` and matched the docstring explaining that it has none. A blunt grep over
    a file that EXPLAINS a rule will always find the rule's own words.

    So the module is parsed and every name it actually uses is read from the AST. Prose is not
    code, and a probe that cannot tell them apart proves nothing about either.
    """
    import ast
    import inspect

    from genios_engine.context import proposal_gate

    tree = ast.parse(inspect.getsource(proposal_gate))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    names |= {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}

    forbidden = {"client", "consult", "anthropic", "complete", "engine", "connect", "execute"}
    reached = names & forbidden
    assert not reached, f"the validator reaches for {sorted(reached)}"

    # And no import from a package that could hand it one.
    modules = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not [m for m in modules if "bundle" in m or "llm" in m or "semantic" in m], modules


# =================================================================================================
# Check 1 · schema — V-8, no floats
# =================================================================================================

def test_a_float_anywhere_is_refused_by_the_law_that_already_owns_it():
    verdict = _validate({"anomalies": (_anomaly(z_like_bp=0.42),)})
    assert any(code.startswith("l2_schema:") for code in verdict.reason_codes)


def test_a_field_v2_does_not_have_is_refused():
    verdict = _validate({"vibes": "good"})
    assert any("l2_schema:vibes" == code for code in verdict.reason_codes)


# =================================================================================================
# Check 2 · authority — the check the plan could not write, and L2-2 made possible
# =================================================================================================

@pytest.mark.parametrize("field", ["evidence", "signal_ids", "entities", "timeline"])
def test_a_model_may_never_propose_an_observation(field):
    """⛔ *"A model that can write an observation is a model that can invent a fact."*"""
    from genios_engine.context.proposal_gate import Outcome

    verdict = _validate({field: ()})
    assert verdict.outcome is Outcome.REFUSE
    assert f"l2_authority:{field}" in verdict.reason_codes


@pytest.mark.parametrize("field", ["visibility", "org_id", "metadata"])
def test_a_model_may_never_propose_an_envelope_field(field):
    """`visibility` is refused for its own reason: a model that may set it may WIDEN an audience."""
    verdict = _validate({field: "anything"})
    assert f"l2_authority:{field}" in verdict.reason_codes


def test_the_authority_rule_is_read_and_not_copied():
    """Two hand-kept copies of one rule drift, and this repository has caught that five times."""
    import inspect

    from genios_engine.context import proposal_gate

    assert "model_may_write" in inspect.getsource(proposal_gate)


# =================================================================================================
# Check 3 · the receipt, and whether it RESOLVES
# =================================================================================================

def test_an_interpretation_citing_nothing_is_refused():
    """V-9's rule, read from `RECEIPT_REQUIRED` rather than restated."""
    verdict = _validate({"anomalies": (_anomaly(evidence_refs=()),)})
    assert "l2_receipt:anomalies[0]" in verdict.reason_codes


def test_a_citation_that_does_not_resolve_is_a_fabricated_receipt():
    """⛔ *"An unanchorable claim is kept and flagged, never invented."* A ref the Evidence Graph
    has never heard of is worse than no ref: it looks like proof."""
    verdict = _validate({"anomalies": (_anomaly(evidence_refs=("fv-ghost",)),)},
                        resolve_refs=_RESOLVES_NONE)
    assert "l2_unresolved:anomalies[0]" in verdict.reason_codes


def test_every_ref_resolves_in_one_read():
    """⛔ U1 — bounded and batched. One call with every ref, never one per claim."""
    calls: list = []

    def resolver(refs):
        calls.append(tuple(refs))
        return frozenset(refs)

    _validate({"anomalies": tuple(_anomaly(evidence_refs=(f"fv-{i}",)) for i in range(25)),
               "trends": ()}, resolve_refs=resolver)
    assert len(calls) == 1, f"the validator issued {len(calls)} reads"
    assert len(calls[0]) == 25


def test_nothing_is_read_when_nothing_cites():
    """A resolver call with an empty set is a round trip bought for nothing."""
    calls: list = []
    _validate({"confidence": None}, resolve_refs=lambda refs: calls.append(refs) or frozenset())
    assert calls == []


# =================================================================================================
# Check 4 · contradiction
# =================================================================================================

def test_a_proposal_that_disagrees_with_a_higher_authority_fact_is_refused():
    """The rule is `graph_store.fact_write_action`, read rather than restated — *"lower authority
    disagrees → flag, keep held"*."""
    verdict = _validate({"type": "renewal_at_risk"},
                        held_facts={"type": {"value": "deal_stalled", "authority_rank": 9}})
    assert "l2_contradiction:type" in verdict.reason_codes


def test_agreeing_with_a_held_fact_is_not_a_contradiction():
    verdict = _validate({"type": "deal_stalled"},
                        held_facts={"type": {"value": "deal_stalled", "authority_rank": 9}})
    assert not [c for c in verdict.reason_codes if c.startswith("l2_contradiction")]


# =================================================================================================
# Check 5 · uncertainty survives
# =================================================================================================

def test_the_model_does_not_get_to_decide_the_data_was_complete():
    """⛔ V-10's rule, one layer earlier. An empty `missing_facts` under low coverage is a claim
    of completeness the data does not support."""
    verdict = _validate({"missing_facts": ()}, coverage_ready=False,
                        expected_facts=("thread.ball_in_court",))
    assert "l2_completeness:missing_facts" in verdict.reason_codes


def test_a_type_with_nothing_expected_is_not_accused():
    """The same narrowing L2-2 measured: 11 of 37 situation types declare no expected fields."""
    verdict = _validate({"missing_facts": ()}, coverage_ready=False, expected_facts=())
    assert not [c for c in verdict.reason_codes if c.startswith("l2_completeness")]


# =================================================================================================
# The gate adapter — and the shape the ledger can actually keep
# =================================================================================================

def test_the_verdict_adapts_to_the_gates_three_tuple():
    from genios_engine.context.proposal_gate import as_gate_validator

    value, codes, record = as_gate_validator(resolve_refs=_RESOLVES_ALL)(
        {"anomalies": (_anomaly(),)})
    assert value is not None and codes == ()
    assert record["outcome"] == "accept"


def test_a_refusal_reaches_the_gate_as_none_with_durable_codes():
    """⛔ `BundleStore.record_call` persists `reason_codes` and NOT `trace`. So the check and the
    subject must be IN the code, or the ledger records that something failed and not what."""
    from genios_engine.context.proposal_gate import as_gate_validator

    value, codes, record = as_gate_validator(resolve_refs=_RESOLVES_ALL)({"evidence": ()})
    assert value is None
    assert "l2_authority:evidence" in codes
    assert record["outcome"] == "refuse"


def test_every_check_has_a_declared_code_prefix():
    """⛔ Totality, both directions — a check whose code nobody declared is a refusal nobody can
    count, which is the defect L2-0 spent a step on."""
    from genios_engine.context.proposal_gate import CHECKS

    for name, prefix in CHECKS.items():
        assert prefix.startswith("l2_") and name


# =================================================================================================
# L2-6-U4 · ⛔ TECHNIQUE 3 — neutralise each check and confirm its probe goes red.
#
# From L1 step 17: *"a fix is not accepted until technique 3 has been applied to it — neutralise
# the fix and confirm the probe goes red. A probe that passes with the fix removed proves
# nothing."*
#
# ⛔ **AND THESE NEUTRALISE THE RULE, NOT THE CHECK.** Breaking `proposal_gate`'s own code would
# only prove that its code runs. Breaking `claim_state.model_may_write`, `RECEIPT_REQUIRED` and
# `fact_write_action` proves the check is genuinely READING the rule it claims to read — which is
# the property that stops a second copy being written later.
# =================================================================================================

def test_the_authority_check_dies_with_claim_states_rule(monkeypatch):
    from genios_engine.contracts import claim_state

    assert "l2_authority:evidence" in _validate({"evidence": ()}).reason_codes

    monkeypatch.setattr(claim_state, "model_may_write", lambda state: True)
    after = _validate({"evidence": ()}).reason_codes
    assert not [c for c in after if c.startswith("l2_authority")], (
        "the authority check survived `model_may_write` being neutralised, so it is not reading "
        "it — it has its own copy of the rule")


def test_the_receipt_check_dies_with_v9s_table(monkeypatch):
    from genios_engine.contracts import situation

    assert "l2_receipt:anomalies[0]" in _validate(
        {"anomalies": (_anomaly(evidence_refs=()),)}).reason_codes

    monkeypatch.setattr(situation, "RECEIPT_REQUIRED", {})
    after = _validate({"anomalies": (_anomaly(evidence_refs=()),)}).reason_codes
    assert not [c for c in after if c.startswith("l2_receipt")], (
        "the receipt check survived `RECEIPT_REQUIRED` being emptied, so V-9's table is not what "
        "it consults")


def test_the_contradiction_check_dies_with_the_graph_stores_rule(monkeypatch):
    from genios_engine.context import graph_store

    held = {"type": {"value": "deal_stalled", "authority_rank": 9}}
    assert "l2_contradiction:type" in _validate({"type": "renewal_at_risk"},
                                                held_facts=held).reason_codes

    monkeypatch.setattr(graph_store, "fact_write_action", lambda **kw: "supersede")
    after = _validate({"type": "renewal_at_risk"}, held_facts=held).reason_codes
    assert not [c for c in after if c.startswith("l2_contradiction")], (
        "the contradiction check survived `fact_write_action` being neutralised, so it has "
        "re-derived what a contradiction is")


def test_the_resolution_check_dies_when_the_resolver_stops_refusing():
    """The resolver is handed in, so neutralising it is simply handing in a permissive one — which
    is also the shape of the bug this check exists to catch."""
    proposal = {"anomalies": (_anomaly(evidence_refs=("fv-ghost",)),)}
    assert "l2_unresolved:anomalies[0]" in _validate(
        proposal, resolve_refs=_RESOLVES_NONE).reason_codes
    assert not [c for c in _validate(proposal, resolve_refs=_RESOLVES_ALL).reason_codes
                if c.startswith("l2_unresolved")]


def test_the_completeness_check_dies_when_coverage_says_it_looked():
    """V-10's own reading: `coverage_ready=True` ends the question."""
    args = dict(coverage_ready=False, expected_facts=("thread.ball_in_court",))
    assert "l2_completeness:missing_facts" in _validate({"missing_facts": ()}, **args).reason_codes
    assert not [c for c in _validate({"missing_facts": ()},
                                     **{**args, "coverage_ready": True}).reason_codes
                if c.startswith("l2_completeness")]


def test_the_schema_check_dies_when_the_float_law_stops_refusing(monkeypatch):
    from genios_engine.contracts import conflict

    assert "l2_schema:float" in _validate({"anomalies": (_anomaly(z_like_bp=0.42),)}).reason_codes

    monkeypatch.setattr(conflict, "require_no_float", lambda value, label: value)
    after = _validate({"anomalies": (_anomaly(z_like_bp=0.42),)}).reason_codes
    assert "l2_schema:float" not in after, (
        "the schema check survived V-8's validator being neutralised, so it has its own float rule")


def test_every_declared_check_has_a_probe():
    """⛔ Totality over the probes themselves. A check with no mutation probe is a check nobody
    has proven sensitive, and criterion 4 asks for one per check."""
    from genios_engine.context.proposal_gate import CHECKS

    probed = {"schema", "authority", "receipt", "unresolved", "contradiction", "completeness"}
    assert probed == set(CHECKS), (
        f"checks with no mutation probe: {sorted(set(CHECKS) - probed)}")


# =================================================================================================
# L2-6 criterion 6 · ⛔ HANDED TO THE EXISTING GATE — NOT A SECOND GATE.
#
# §0: *"This step writes L2's validator and hands it to the existing gate."* A validator that has
# never been through `RSiteGate.consult` is a validator whose contract is a hope — and this
# project's recurring defect is *"a unit built, tested, green, and called by nothing on a real
# request path."*
#
# L2-5 is the caller and does not exist yet, so the strongest available proof is to drive the REAL
# gate with a fake client and this validator, and assert what the gate does with each outcome.
# =================================================================================================

class _Client:
    """The shape `RSiteGate` expects, copied from `tests/reason/test_r_site_gate.py`."""

    model = "claude-haiku-4-5-20251001"

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def call(self, prompt, *, max_tokens=400):
        from genios_engine.context.llm.client import LLMResult

        self.calls += 1
        return LLMResult(parsed=self.payload, raw="", ok=True, model=self.model,
                         input_tokens=900, output_tokens=120, error=None)


def _consult(payload, **kw):
    from genios_engine.context.proposal_gate import as_gate_validator
    from genios_engine.platform.l4_activation import FEATURE_BUNDLE
    from genios_engine.reason.bundle.gate import RSiteGate
    from genios_engine.reason.bundle.sites import SITE_INTERPRET

    client = _Client(payload)
    gate = RSiteGate(org_id="org_l2_6", client=client, activated=frozenset({FEATURE_BUNDLE}))
    result = gate.consult(
        site=SITE_INTERPRET, cache_key="l2-6-wiring",
        build_prompt=lambda feedback: "propose",
        validate=as_gate_validator(resolve_refs=_RESOLVES_ALL, **kw))
    return result, client


def test_an_accepted_proposal_reaches_the_gate_as_a_run():
    from genios_engine.reason.bundle.sites import OUTCOME_RAN

    result, client = _consult({"type": "deal_stalled"})
    assert result.outcome == OUTCOME_RAN
    assert result.value == {"type": "deal_stalled"}
    assert client.calls == 1


def test_an_unknown_proposal_also_reaches_the_gate_as_a_run():
    """⛔ **THE POINT OF THE FOUR-VALUED OUTCOME, PROVEN THROUGH THE REAL GATE.** UNKNOWN returns
    a value, so the gate records RAN — a real answer, committed. Returned as `None` it would have
    been retried and filed as a failed generation, which is a correct refusal made to look like a
    broken model."""
    from genios_engine.reason.bundle.sites import OUTCOME_RAN

    result, client = _consult({"confidence": None})
    assert result.outcome == OUTCOME_RAN
    assert client.calls == 1, "an UNKNOWN answer was retried, so it was read as a failure"


def test_a_refused_proposal_reaches_the_gate_as_a_failed_validation_with_its_code():
    """⛔ And the code is durable: `record_call` persists `reason_codes` and NOT `trace`."""
    from genios_engine.reason.bundle.sites import OUTCOME_FAILED_VALIDATION

    result, _ = _consult({"evidence": ()})
    assert result.outcome == OUTCOME_FAILED_VALIDATION
    assert "l2_authority:evidence" in result.reason_codes


def test_the_gate_and_not_this_module_owns_the_retry():
    """§0: *"Everything about when a model may be consulted, what it costs and what happens when
    it fails is already solved and property-tested."* A refusal is retried by the GATE, once, and
    this validator has no say in it — which is why there is no second gate."""
    result, client = _consult({"evidence": ()})
    assert client.calls > 1, "the gate stopped retrying, or the validator swallowed the failure"
    assert result.attempts == client.calls
