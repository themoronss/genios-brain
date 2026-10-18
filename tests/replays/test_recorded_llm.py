"""STEP-01 · the recorded model answers what was recorded, and nothing else.

    pytest tests/replays/test_recorded_llm.py -q

A golden case is replayed through the real chain with the model's answers recorded, so it runs
without a key, costs nothing, and gives the same answer every time. Three properties make that
honest:

  * the KEY is the prompt's own hash (`LLMClient.content_hash`), after removing only what the
    engine mints at random per call — the injection fence's nonce. Change one character of what
    the model reads and the recording no longer answers;
  * a MISS raises, naming the site and the key, and is also kept in `.misses`. It never comes back
    as `ok=False`: every model site in the chain treats a failed call as "park and retry", so a
    soft miss would park the case forever (B18's shape) and be judged as the engine's silence;
  * the miss is a `BaseException`. Production wraps each model call in `except Exception` so one
    failure never stops a sweep; that is right in production and would swallow a miss here.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from genios_engine.capture.semantic.injection import fence
from tests.replays.harness import (CassetteMiss, CassetteRecorder, RecordedLLM, SITE_MARKERS,
                                   cassette_key, identify_site, normalise_prompt)

ENGINE = Path(__file__).resolve().parents[2] / "genios_engine"


def _prompt(body: str, nonce: str) -> str:
    return ("You are classifying messages for a company's business-intelligence system.\n\n"
            "ITEMS:\nitem 1:\n" + fence(body, nonce=nonce).text + "\n")


def test_a_recorded_prompt_returns_its_answer():
    prompt = _prompt("Could you send the deck?", "0123456789abcdef")
    llm = RecordedLLM({cassette_key(prompt): {
        "site": "relevance", "parsed": {"verdicts": [{"item": 1, "business": True}]},
        "input_tokens": 410, "output_tokens": 38, "model": "claude-haiku-4-5-20251001"}})
    res = llm.call(prompt, max_tokens=1024)
    assert res.ok and res.parsed == {"verdicts": [{"item": 1, "business": True}]}
    assert json.loads(res.raw) == res.parsed
    assert (res.input_tokens, res.output_tokens) == (410, 38)
    assert res.model == "claude-haiku-4-5-20251001"
    assert llm.calls == [("relevance", cassette_key(prompt))] and llm.misses == []


def test_the_fence_nonce_is_the_only_thing_the_key_forgives():
    """Production mints 64 fresh bits per prompt; two runs of one case differ by exactly that."""
    a = _prompt("Could you send the deck?", "0123456789abcdef")
    b = _prompt("Could you send the deck?", "fedcba9876543210")
    c = _prompt("Could you send the deck!", "0123456789abcdef")
    assert a != b and cassette_key(a) == cassette_key(b)
    assert cassette_key(a) != cassette_key(c), "a changed character must change the key"
    assert "0123456789abcdef" not in normalise_prompt(a)


def test_a_minted_id_is_renumbered_never_erased():
    """A fresh tenant mints a fresh `sit_…` for the same situation; two situations stay two."""
    a1, a2, b1 = ("sit_" + c * 24 for c in "abc")
    one = f"SITUATION SUBJECT: situation {a1}\n- situation: {a1}\n"
    same = f"SITUATION SUBJECT: situation {a2}\n- situation: {a2}\n"
    two = f"SITUATION SUBJECT: situation {a1}\n- situation: {b1}\n"
    assert cassette_key(one) == cassette_key(same)
    assert cassette_key(one) != cassette_key(two)
    assert normalise_prompt(two).endswith("situation: sit_#2\n")


def test_the_key_is_the_engines_own_hash_of_the_normalised_prompt():
    from genios_engine.context.llm.client import LLMClient
    prompt = _prompt("x", "0123456789abcdef")
    assert cassette_key(prompt) == LLMClient.content_hash(normalise_prompt(prompt))


def test_a_miss_raises_naming_the_site_and_the_key_and_is_kept():
    llm = RecordedLLM({})
    prompt = _prompt("never recorded", "0123456789abcdef")
    with pytest.raises(CassetteMiss) as miss:
        llm.call(prompt)
    assert miss.value.site == "relevance" and miss.value.key == cassette_key(prompt)
    assert "relevance" in str(miss.value) and cassette_key(prompt)[:12] in str(miss.value)
    assert llm.misses == [("relevance", cassette_key(prompt))]


def test_production_cannot_swallow_a_miss():
    """`except Exception` — the shape around every model call in the chain — lets it through."""
    llm = RecordedLLM({})

    def a_model_site_in_production():
        try:
            return llm.call(_prompt("never recorded", "0123456789abcdef"))
        except Exception:      # noqa: BLE001 — exactly what production does
            return None

    assert not issubclass(CassetteMiss, Exception)
    with pytest.raises(CassetteMiss):
        a_model_site_in_production()


def test_it_is_safe_under_the_chains_thread_pools():
    prompts = [_prompt(f"message {i}", "0123456789abcdef") for i in range(40)]
    llm = RecordedLLM({cassette_key(p): {"site": "relevance", "parsed": {"i": i}}
                       for i, p in enumerate(prompts)})
    answers: list[int] = []
    lock = threading.Lock()

    def worker():
        for i, p in enumerate(prompts):
            got = llm.call(p).parsed["i"]
            with lock:
                answers.append(got - i)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(llm.calls) == 8 * 40 and set(answers) == {0}


def test_the_recorder_writes_what_the_recorded_model_replays():
    class Inner:
        model = "claude-haiku-4-5-20251001"

        def call(self, prompt, *, max_tokens=4096, **_kw):
            from genios_engine.context.llm.client import LLMResult
            return LLMResult(parsed={"echo": len(prompt)}, raw="{}", input_tokens=7,
                             output_tokens=3, model=self.model)

    recorder = CassetteRecorder(Inner())
    first = _prompt("one", "0123456789abcdef")
    recorder.call(first)
    cassette = recorder.cassette
    assert set(cassette) == {cassette_key(first)}
    assert cassette[cassette_key(first)]["site"] == "relevance"
    again = RecordedLLM(cassette).call(_prompt("one", "aaaaaaaaaaaaaaaa"))
    assert again.parsed == {"echo": len(first)} and again.input_tokens == 7


def test_the_recorder_refuses_a_failed_answer():
    """A cassette holds answers. A failed call recorded as one would replay the failure as the
    model's verdict — the soft miss, written down."""
    class Failing:
        model = "m"

        def call(self, prompt, **_kw):
            from genios_engine.context.llm.client import LLMResult
            return LLMResult(parsed={}, raw="", ok=False, error="overloaded", model="m")

    with pytest.raises(RuntimeError, match="overloaded"):
        CassetteRecorder(Failing()).call(_prompt("x", "0123456789abcdef"))


@pytest.mark.parametrize(("site", "module", "marker"), [
    (site, module, marker) for site, module, marker in SITE_MARKERS])
def test_every_site_marker_is_still_in_its_prompt(site, module, marker):
    """A site is recognised by a phrase its prompt opens with. Reword the prompt and this fails,
    so the marker moves with it instead of every call silently becoming `unknown`."""
    source = (ENGINE / module).read_text(encoding="utf-8")
    assert marker in source.replace("\\\n", ""), (
        f"the {site} marker {marker!r} is no longer in {module}")


def test_the_real_prompts_are_identified():
    from genios_engine.capture.domain.proposer import build_prompt as domain_prompt
    from genios_engine.capture.gate import relevance as gate
    from genios_engine.capture.esqe.relevance import _PROMPT_HEAD

    assert identify_site(gate._GATE_PROMPT.format(source="gmail", content="hi")) == "junk_gate"
    assert identify_site(gate._GATE_BATCH_PROMPT.format(n=2, last=1, emails="[0] a\n[1] b")) \
        == "junk_gate_batch"
    assert identify_site(_PROMPT_HEAD + "item 1:\n") == "relevance"
    assert identify_site(domain_prompt("hello", registered=frozenset({"admin"}))) == "domains"
    assert identify_site("nothing anyone wrote") == "unknown"
