"""P2 cost · prompt caching of the fixed extraction instructions, and compact screen output.

Caching must change only the PRICE: the model sees the identical text, the cost ledger sees
cost-equivalent input tokens (cache writes 1.25x, reads 0.1x), and a client that cannot cache
(every test fake) is called exactly as before.
"""

from __future__ import annotations

from types import SimpleNamespace

from genios_engine.capture.semantic import extractor as X
from genios_engine.capture.semantic.profiles import ENVELOPE_MARKER, PROFILES
from genios_engine.context.llm.client import LLMClient


class _Messages:
    def __init__(self, usage) -> None:
        self.usage = usage
        self.kw: dict = {}

    def create(self, **kw):
        self.kw = kw
        return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"a": 1}')],
                               usage=self.usage)


def _client(**usage):
    c = LLMClient(api_key="x", model="m")
    m = _Messages(SimpleNamespace(**usage))
    c._client = SimpleNamespace(messages=m)
    return c, m


def test_the_prefix_is_marked_cacheable_and_the_text_is_unchanged():
    c, m = _client(input_tokens=100, output_tokens=10, cache_creation_input_tokens=0,
                   cache_read_input_tokens=4000)
    r = c.call("FIXEDtail", cache_prefix_chars=5)

    blocks = m.kw["messages"][0]["content"]
    assert blocks[0] == {"type": "text", "text": "FIXED", "cache_control": {"type": "ephemeral"}}
    assert blocks[1] == {"type": "text", "text": "tail"}
    assert "".join(b["text"] for b in blocks) == "FIXEDtail"
    assert r.ok and r.cache_read_tokens == 4000
    assert r.input_tokens == 100 + 400, "a cache read is priced at 0.1x"


def test_a_cache_write_is_priced_at_one_and_a_quarter():
    c, _ = _client(input_tokens=100, output_tokens=10, cache_creation_input_tokens=4000,
                   cache_read_input_tokens=0)
    assert c.call("FIXEDtail", cache_prefix_chars=5).input_tokens == 100 + 5000


def test_without_a_prefix_the_prompt_is_sent_as_before():
    c, m = _client(input_tokens=100, output_tokens=10)
    r = c.call("hello")
    assert m.kw["messages"][0]["content"] == "hello"
    assert r.input_tokens == 100 and r.cache_read_tokens == 0


def test_the_extractor_caches_everything_before_the_envelope():
    seen: dict = {}

    class Caching:
        supports_prompt_cache = True
        model = "m"

        def call(self, prompt, *, max_tokens=4096, cache_prefix_chars=0):
            seen.update(prompt=prompt, n=cache_prefix_chars)
            return "answer"

    prompt = "FIXED" + ENVELOPE_MARKER + "per-message"
    assert X._call_model(Caching(), prompt, 100) == "answer"
    assert seen == {"prompt": prompt, "n": 5}


def test_a_client_that_cannot_cache_is_called_exactly_as_before():
    class Plain:
        model = "m"

        def call(self, prompt, *, max_tokens=4096):
            return "ok"

    assert X._call_model(Plain(), "a" + ENVELOPE_MARKER + "b", 10) == "ok"


def test_the_compact_rule_is_on_the_screen_profiles_only():
    from genios_engine.capture.semantic.profiles import _SCREEN_COMPACT_RULE

    assert _SCREEN_COMPACT_RULE in PROFILES["screen_session"].prompt_template
    assert _SCREEN_COMPACT_RULE in PROFILES["screen_generic"].prompt_template
    for pid in ("email", "chat", "transcript", "document", "crm_note"):
        assert _SCREEN_COMPACT_RULE not in PROFILES[pid].prompt_template
