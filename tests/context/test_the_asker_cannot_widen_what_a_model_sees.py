"""The transport, and the two things it must never do.

`angles/store.py` decides WHEN a model is asked and `angles/contract.py` says WHAT may be asked.
This is the only piece that talks to one, and it is opt-in: `evaluate_angle(..., asker=None)` is
the default and the sweep supplies nothing, which is what makes "a tenant cannot reach a model by
accident" a property rather than a promise.

THE PROMPT IS BUILT FROM THE DECLARATION. `sees` is the evidence list, `returns` the answer list,
`refusal` the honest exit, `question` the question. So the prompt cannot show a field the
declaration did not admit, and reviewing an angle IS reviewing what leaves the tenant — there is no
second place where a prompt could quietly widen.

NOTHING THE MODEL WRITES IS ECHOED. It returns one WORD from a closed set and a number. A word
outside the set becomes the angle's declared refusal, not an error: `evaluate_angle` counts a
raised exception as `failed` and a refusal as `refused`, and a model answering confidently in the
wrong vocabulary is the second. Reporting it as the first sends somebody looking for a bug in the
evaluator.
"""
from typing import Any

import pytest

from genios_engine.context.angles.asker import MAX_TOKENS, build_prompt, model_asker
from genios_engine.context.angles.contract import Angle, CostTier, GateSource

ANGLE = Angle(
    angle_id="probe_angle", version="1.0.0", gate=("g.field",), gate_source=GateSource.FACTS,
    sees=("a.one", "b.two"), returns=("yes", "no", "unknowable"), refusal="unknowable",
    question="Is it so?", confidence_band=(2_000, 8_000), max_per_sweep=10)

SEEN = {"a.one": "alpha", "b.two": {"k": "beta"}}


class _Client:
    supports_prompt_cache = True

    def __init__(self, parsed: Any = None, ok: bool = True):
        self.parsed, self.ok, self.calls = parsed, ok, []

    def call(self, prompt: str, **kw):
        self.calls.append((prompt, kw))
        return type("R", (), {"ok": self.ok, "parsed": self.parsed})()


# ── what the prompt may contain ──────────────────────────────────────────────────────────────

def test_the_prompt_shows_exactly_what_sees_names() -> None:
    prompt, _ = build_prompt(ANGLE, "n_1", {**SEEN, "c.secret": "must not appear"})
    assert "alpha" in prompt and "beta" in prompt
    assert "must not appear" not in prompt and "c.secret" not in prompt


def test_the_subject_ref_is_not_shown() -> None:
    """An internal node id identifies nothing a model can reason about, and putting a tenant's key
    material in a prompt buys nothing."""
    prompt, _ = build_prompt(ANGLE, "node_9f3ab21c", SEEN)
    assert "node_9f3ab21c" not in prompt


def test_the_allowed_answers_and_the_refusal_are_both_named() -> None:
    prompt, _ = build_prompt(ANGLE, "n_1", SEEN)
    for word in ANGLE.returns:
        assert word in prompt
    assert "REFUSAL ANSWER: unknowable" in prompt
    assert "Refusing is a correct result" in prompt


def test_the_prompt_is_byte_identical_for_the_same_slice() -> None:
    """Sorted fields and a fixed instruction block: two runs at one instant produce one prompt
    hash for the audit, and the cache prefix is worth something."""
    a, pa = build_prompt(ANGLE, "n_1", {"b.two": {"k": "beta"}, "a.one": "alpha"})
    b, pb = build_prompt(ANGLE, "n_1", {"a.one": "alpha", "b.two": {"k": "beta"}})
    assert (a, pa) == (b, pb)


def test_the_cacheable_prefix_stops_before_the_evidence() -> None:
    prompt, prefix = build_prompt(ANGLE, "n_1", SEEN)
    assert "alpha" not in prompt[:prefix]
    assert "EVIDENCE" not in prompt[:prefix]


# ── what may come back ───────────────────────────────────────────────────────────────────────

def test_a_good_answer_passes_through_clamped() -> None:
    ask = model_asker(_Client({"verdict": "yes", "confidence_bp": 9_900}))
    assert ask(ANGLE, "n_1", SEEN) == ("yes", 8_000)


@pytest.mark.parametrize("parsed", [
    {"verdict": "maybe", "confidence_bp": 7_000},      # outside the enum
    {"verdict": "", "confidence_bp": 7_000},
    {"confidence_bp": 7_000},                          # no verdict at all
    {},
])
def test_an_answer_outside_the_enum_becomes_the_refusal(parsed) -> None:
    """NOT AN ERROR. `failed` says the machinery broke; `refused` says the question could not be
    answered. A model replying confidently in the wrong vocabulary is the second."""
    ask = model_asker(_Client(parsed))
    assert ask(ANGLE, "n_1", SEEN) == ("unknowable", 2_000)


def test_a_transport_failure_raises_so_it_is_counted_as_failed() -> None:
    """THE BUG THE FIRST LIVE CALL FOUND. `anthropic` was not installed, the client returned
    `ok=False`, and an earlier cut of this returned `unknowable` at floor confidence —
    indistinguishable from a model that read the evidence and honestly could not tell. Running the
    full pass that way would have produced seventy "refusals" and reported them as answers.

    `evaluate_angle` counts a raised exception as `failed` and a returned refusal as `refused`.
    The machinery breaking is the first."""
    from genios_engine.context.angles.asker import AskerUnavailable

    with pytest.raises(AskerUnavailable, match="was not reached"):
        model_asker(_Client(None, ok=False))(ANGLE, "n_1", SEEN)


def test_a_usable_verdict_with_an_unusable_number_is_kept() -> None:
    """`Angle.clamp` would raise on a non-integer and lose the answer with it. The band's floor is
    the honest reading of "it answered but told us nothing about how sure it was"."""
    ask = model_asker(_Client({"verdict": "no", "confidence_bp": "very"}))
    assert ask(ANGLE, "n_1", SEEN) == ("no", 2_000)


def test_every_verdict_it_returns_is_one_the_contract_accepts() -> None:
    """The guarantee the store depends on: `AngleVerdict.of` refuses anything else at
    construction, so an asker that could return a stray word would surface as `failed`."""
    from genios_engine.context.angles.contract import AngleVerdict

    for parsed in ({"verdict": "yes", "confidence_bp": 5_000}, {"verdict": "nope"},
                   {"unexpected": 1}):
        word, conf = model_asker(_Client(parsed))(ANGLE, "n_1", SEEN)
        AngleVerdict.of(ANGLE, subject_ref="n_1", verdict=word, confidence_bp=conf)


# ── cost ─────────────────────────────────────────────────────────────────────────────────────

def test_the_tier_chooses_the_client() -> None:
    cheap, capable = _Client({"verdict": "yes", "confidence_bp": 5_000}), \
                     _Client({"verdict": "no", "confidence_bp": 5_000})
    ask = model_asker(cheap, capable)
    ask(ANGLE, "n_1", SEEN)
    assert len(cheap.calls) == 1 and not capable.calls

    import dataclasses
    heavy = dataclasses.replace(ANGLE, cost_tier=CostTier.CAPABLE)
    ask(heavy, "n_1", SEEN)
    assert len(capable.calls) == 1


def test_one_client_serves_both_tiers() -> None:
    """The correct default for a tenant who has not chosen a second model."""
    import dataclasses

    only = _Client({"verdict": "yes", "confidence_bp": 5_000})
    model_asker(only)(dataclasses.replace(ANGLE, cost_tier=CostTier.CAPABLE), "n_1", SEEN)
    assert len(only.calls) == 1


def test_the_answer_budget_is_small_because_the_answer_is_two_fields() -> None:
    assert MAX_TOKENS <= 512
    ask = model_asker(_Client({"verdict": "yes", "confidence_bp": 5_000}))
    client = _Client({"verdict": "yes", "confidence_bp": 5_000})
    model_asker(client)(ANGLE, "n_1", SEEN)
    assert client.calls[0][1]["max_tokens"] == MAX_TOKENS
    assert client.calls[0][1]["cache_prefix_chars"] > 0


# ── the receipt ──────────────────────────────────────────────────────────────────────────────

def test_the_asker_reports_what_the_call_cost() -> None:
    """THE DEFECT THE LIVE RUN EXPOSED, and it cost every audit row on the first real pass.

    `model_audit.record_model_run` reads `model`, `input_tokens`, `output_tokens`, `ok` and
    `error` OFF the object it is handed. `store._record` was handing it the verdict STRING, so
    every one took its default — `model="unknown"`, zero tokens, `success=False` — and the
    `max_tokens=0` it passed alongside violated `l2_model_runs_max_tokens_check`, so the row was
    rejected outright. The angle layer could not say what it had spent.

    The asker is the only thing that holds these facts. It exposes them as `.last`, with the
    attribute names the audit reads.
    """
    class _Rich:
        supports_prompt_cache = False
        model = "claude-haiku-4-5-20251001"

        def call(self, prompt, **kw):
            return type("R", (), {"ok": True, "parsed": {"verdict": "yes", "confidence_bp": 6000},
                                  "raw": '{"verdict":"yes"}', "model": self.model,
                                  "input_tokens": 812, "output_tokens": 17})()

    ask = model_asker(_Rich())
    assert ask(ANGLE, "n_1", SEEN) == ("yes", 6_000)

    last = ask.last
    assert last.model == "claude-haiku-4-5-20251001"
    assert (last.input_tokens, last.output_tokens) == (812, 17)
    assert last.ok is True
    assert last.max_tokens == MAX_TOKENS > 0, "a zero here is rejected by the audit table"


def test_the_usage_object_carries_the_names_the_audit_reads() -> None:
    """Checked by name, because the coupling is duck-typed: `record_model_run` uses `getattr` and
    a renamed attribute would silently take a default again rather than fail."""
    from genios_engine.context.angles.asker import Usage

    for name in ("model", "input_tokens", "output_tokens", "ok", "error", "raw", "parsed"):
        assert hasattr(Usage(), name), name


def test_the_store_passes_the_usage_and_never_a_bare_word() -> None:
    import ast
    import inspect

    from genios_engine.context.angles import store

    # CHECKED AS CODE, NOT AS PROSE. An earlier cut grepped for the string "max_tokens=0" and
    # failed on the comment explaining why that value is wrong — the same trap
    # `test_m9_never_fires_inside_a_sweep` sets for itself by scanning comments, and the third
    # time it has caught a test in this branch. What must be absent is a literal zero ARGUMENT.
    tree = ast.parse(inspect.getsource(store._record).lstrip())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "record_model_run"]
    assert calls, "the audit call moved"

    kw = {k.arg: k.value for k in calls[0].keywords}
    assert "result" in kw and "max_tokens" in kw

    budget = kw["max_tokens"]
    assert not (isinstance(budget, ast.Constant) and budget.value == 0), (
        "a literal zero max_tokens is rejected by l2_model_runs_max_tokens_check")
    assert not (isinstance(kw["result"], ast.Name) and kw["result"].id == "word"), (
        "handing the audit the verdict string makes every usage field take its default")
