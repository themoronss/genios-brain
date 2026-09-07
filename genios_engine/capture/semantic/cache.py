"""L1.4.9 · THE EXTRACTION CACHE — the model runs once per document version, ever.

Two things depend on this module and neither of them is speed.

**Cost.** L1.4 is the heaviest LLM site in the product. A tenant's mailbox is re-read by every
backfill, every rebuild, every replay of a decision somebody questioned; without a cache each
of those re-reads is a second bill for an answer already paid for. The cache is what makes
heavy L1 extraction affordable at all, which is why `cached_extraction` — not the extractor —
owns the decision to call a model.

**Replay.** A signal published in March must be explainable in September, and the explanation
has to be the extraction that actually produced it, not a fresh reading by a successor model
that behaves differently. A stored, keyed extraction is the only thing that makes a
non-deterministic pipeline auditable.

Those two purposes pull in opposite directions, and the tension is the whole design problem:
a cache that answers too eagerly is indistinguishable from a pipeline that ignores its own
fixes. This codebase has already paid for that. **260 cached extractions survived a prompt fix**
— the fix shipped, the numbers did not move, and the conclusion drawn was that the fix had not
worked. Nothing was broken except the key.

TWO UNITS
---------
**U1 `cache_key`** — the key formula, and the refusals that keep it honest. Every component
that changes what the model was ASKED is inside the digest:

* `org_id` — tenant isolation at the key level. Two tenants receive the same newsletter; one
  tenant's extraction of it must never be served to the other, and org-scoping the KEY (rather
  than only the WHERE clause) means a future caller cannot omit its way into a cross-tenant read.
* `prompt_version` — content-addressed by `profiles.render_prompt`, so a template edit changes
  it and nobody has to remember to bump a literal. The 260-row incident was a hand-typed version.
* `schema_version` — the SHAPE the pipeline reads back out. A reader that now looks for `roles`
  would otherwise be served a cached payload that never had them, silently, for exactly the
  messages that already matter most. A parameter rather than a module constant: L1.4.5-U2's
  promotion procedure hands the human a version bump to make, and this module must key on the
  value the extractor actually ran under, not on whatever this file imported at boot.
* `model_snapshot` — the exact dated model id. "claude-3-5-haiku" is a family; a family is not
  reproducible.
* `profile_id` — new in v2, and the reason the key needed touching at all. The same text read
  under the `document` profile is a DIFFERENT extraction from the same text read under `email`:
  different prompt, different emphasis, different tier. Without it, whichever profile ran first
  answers for every profile that follows.
* `vocab_fingerprint` — `vocabulary.vocabulary_fingerprint()`. Promoting a tenant onto a
  vocabulary that adds an observation kind changes what the model is asked to look for; without
  the fingerprint the new kind is never extracted for any message the tenant has already seen,
  which is most of them.
* `envelope_hash` — **not in the doc-04 formula, and its absence is a defect this unit refuses
  to inherit.** The envelope (direction, parties, thread position) is prompt input: doc 04 says
  in as many words that without it "an outbound offer reads as an inbound request — a bug that
  already occurred and was fixed once". A key over content alone gives two byte-identical bodies
  with different senders the same digest, so the second one is answered with the first one's
  direction and the fixed bug comes back through the cache. `context/pipeline.py` keys over
  content alone today and has this collision; see `test_extraction_cache.py`.
* `content_hash` — the text itself, digested rather than carried so the key stays a key.

`cache_key` REFUSES an empty component instead of hashing one in. A component that collapses
to `""` does not fail — it silently merges two different extractions into one cache slot, which
is the same accident as the 260 rows with a different first cause.

**U2 `cached_extraction`** — the read-through path, and the unit that makes "zero LLM calls on a
hit" a mechanical property rather than a convention. The model call is passed in as a callable
that this function invokes ONLY on a miss, so a hit cannot reach a model even by mistake: there
is no model to reach. Doc 04 gives L1.4.9 two units and specifies only the first; this is the
second, because a key with no read-through is a formula nothing enforces, and the enforcement is
the point.

Its other job is the guard nothing else can do: `CacheEntry` refuses to be built when the
result's own provenance disagrees with the key it is being filed under. Storing an extraction
produced by prompt A under a key that says prompt B is precisely how a stale row outlives the
prompt that produced it — the 260-row bug, re-created by hand, one row at a time.

WHAT THIS MODULE DOES NOT DO
----------------------------
It does not call a model, choose a profile, choose a tier or render a prompt. It takes those as
values already decided (L1.4.1, L1.4.10, L1.4.2) and it takes the call itself as a thunk. It
reads no clock — `created_at` is the database's default, so a replayed insert cannot be dated by
whichever machine replayed it. It holds no scores: nothing here is basis points, because nothing
here is a judgement.

STORAGE — `l1_extraction_results` (migration 0080, renamed from `l2_extraction_results`). The
rows are the money already spent, so the migration renames rather than re-creates.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import text

from genios_engine.capture.semantic.profiles import TIERS
from genios_engine.capture.semantic.vocabulary import EXTRACTION_PROFILE
from genios_engine.contracts.extraction import ExtractionResult
from genios_engine.platform.db import get_engine

log = logging.getLogger(__name__)

#: The table. Named once, here, so the next rename is one edit plus its callers rather than a
#: grep that misses the erasure loop — which is exactly what migration 0080's header describes.
CACHE_TABLE = "l1_extraction_results"

#: The key components, in the order they are digested. Order is fixed and part of the format:
#: changing it changes every key, which orphans every stored row. Present as a tuple so a test
#: can assert the formula's shape without re-typing it, and so `_material` cannot disagree with
#: the record's field names.
KEY_COMPONENTS = (
    "org_id", "prompt_version", "schema_version", "model_snapshot",
    "profile_id", "vocab_fingerprint", "envelope_hash", "content_hash",
)

#: Full sha256, not a prefix. A truncated digest saves nothing here — the key is a primary key
#: in a database, never something a human types — and a collision between two tenants' cache
#: rows is a cross-tenant data leak, which is not a risk worth 32 characters of log width.
KEY_DIGEST_CHARS = 64

#: The digest of the empty envelope. An uploaded document genuinely has no sender, and
#: `profiles.render_prompt` accepts an empty envelope for that reason; the caller must not have
#: to fabricate a header to get a key. Hashed like any other value so the empty case is a value
#: in the format rather than a hole in it.
EMPTY_ENVELOPE = ""


def _sha256(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def content_digest(content: str) -> str:
    """The `content_hash` component of a cache key, as a value anything may compute.

    `qualified_signals.content_hash` (migration 0115) stores this digest for the prepared text a
    signal's claims were read out of, so a published signal and a cached extraction can be
    compared without re-reading either — and that comparison only holds while both sides hash the
    same way. This is the seam that keeps them the same way: the publisher calls it instead of
    spelling `hashlib.sha256` a second time, and a change to the digest changes both at once.
    """
    return _sha256(content)


def _framed(*fields: str) -> str:
    """Length-prefixed join — `7:acme_co|4:b3-4|...` — never a bare `:` join.

    With a plain separator, components `("a:b", "c")` and `("a", "b:c")` produce byte-identical
    material and therefore one cache slot for two different extractions. Two of these components
    are free text a human types (`model_snapshot`, `prompt_version`) and one is a tenant id, so
    "no component will ever contain a colon" is an assumption with no enforcement behind it.
    Framing by length removes the assumption instead of documenting it.
    """
    return "|".join(f"{len(field)}:{field}" for field in fields)


@dataclass(frozen=True)
class ExtractionCacheKey:
    """A cache key with its components still legible, not just their digest.

    The components are kept beside the digest because a stale-cache diagnosis starts by asking
    *which* component failed to change, and a bare hash cannot answer that. They are also what
    `CacheEntry` checks a result's provenance against.
    """

    org_id: str
    prompt_version: str
    schema_version: str
    model_snapshot: str
    profile_id: str
    vocab_fingerprint: str
    envelope_hash: str
    content_hash: str
    #: sha256 over the framed components, in `KEY_COMPONENTS` order. The `processing_key`
    #: column.
    digest: str

    @property
    def processing_key(self) -> str:
        """The primary-key value. Named for the column so a reader of the SQL and a reader of
        this type are looking at the same thing."""
        return self.digest

    def describe(self) -> str:
        """One line, for the log that a stale-cache investigation actually starts from."""
        return " ".join(f"{name}={getattr(self, name)}" for name in KEY_COMPONENTS)


def cache_key(*, org_id: str, content: str, profile_id: str, prompt_version: str,
              schema_version: str, model_snapshot: str, vocab_fingerprint: str,
              envelope: str = EMPTY_ENVELOPE) -> ExtractionCacheKey:
    """L1.4.9-U1 · build the extraction cache key. Pure: no clock, no I/O, no model.

    Takes `content` and `envelope` as TEXT rather than as pre-computed hashes on purpose. A
    caller that hands over a hash is a caller that can hand over the hash of something else —
    yesterday's text, the unmasked text, the whole document instead of the chunk — and the
    resulting key is well-formed, wrong, and undetectable. Hashing here means the key is a
    function of the bytes the model will actually be shown.

    Refuses, loudly:

    * **any blank component.** An empty `model_snapshot` or `vocab_fingerprint` does not raise
      on its own; it hashes to a stable value and merges every extraction that was missing it
      into a single slot shared across models. The failure surfaces months later as "the new
      model changed nothing".
    * **empty content.** There is nothing to extract, so there is nothing to key, and a model
      asked to extract from nothing invents.
    * **an unregistered `profile_id`.** `profiles.get_profile` deliberately falls back to the
      email profile for an unknown id, because a connector nobody has seen must not kill a sync
      at 3am. That fallback must not reach the key: keying an unknown id would file a document
      extraction under a profile that never ran, and the fallback's own warning would be the
      only trace. The closed set is the vocabulary's, so a profile promoted into the vocabulary
      is keyable the day it lands.

    `envelope` defaults to empty for the document lane, which has no sender to describe.
    """
    profile = profile_id.strip()
    if profile not in EXTRACTION_PROFILE:
        raise ValueError(
            f"unknown extraction profile {profile_id!r}: the cache key may only carry a profile "
            f"from the closed set {sorted(EXTRACTION_PROFILE)}. get_profile() falls back to "
            "'email' for an unknown id so a sync survives it; a cache key must not, or the "
            "fallback is stored as though it were the profile that ran")
    if not content.strip():
        raise ValueError(
            "content is empty: there is nothing to extract, so there is nothing to key")

    values = {
        "org_id": org_id.strip(),
        "prompt_version": prompt_version.strip(),
        "schema_version": schema_version.strip(),
        "model_snapshot": model_snapshot.strip(),
        "profile_id": profile,
        "vocab_fingerprint": vocab_fingerprint.strip(),
        # Hashed, not stripped: leading whitespace in an envelope is part of the prompt text.
        "envelope_hash": _sha256(envelope),
        "content_hash": content_digest(content),
    }
    for name in KEY_COMPONENTS:
        if not values[name]:
            raise ValueError(
                f"cache key component {name!r} is empty: a blank component does not fail, it "
                "merges two different extractions into one cache slot — which is how a stale "
                "extraction outlives the prompt that produced it")

    material = _framed(*(values[name] for name in KEY_COMPONENTS))
    return ExtractionCacheKey(digest=_sha256(material)[:KEY_DIGEST_CHARS], **values)


@dataclass(frozen=True)
class CacheEntry:
    """One stored extraction: the key it is filed under, the result, and where it came from.

    Construction is the enforcement point for the invariant the whole module exists to protect —
    **a result may only be filed under a key that describes it.** Four of the key's components
    are also provenance fields on `ExtractionResult`, written by the extractor about the call it
    actually made. If they disagree, the key is a lie about the row, and the row will be served
    to a reader who believes the key. That is the 260-row incident with a different first cause,
    so it raises here rather than being repaired, logged or stored anyway: a mismatch means the
    caller keyed before routing, or routed again after keying, and both are bugs at the call
    site that a silent repair would hide.

    `input_tokens` / `output_tokens` are read from the result rather than stored beside it —
    one source of truth for what the call cost, so the cost columns cannot drift from the
    extraction they belong to.
    """

    key: ExtractionCacheKey
    event_id: str
    #: T1 | T2 | T3 (L1.4.10). Recorded, never keyed: the tier chooses the model and
    #: `model_snapshot` already pins the model. Keying the tier as well would make a budget
    #: demotion that landed on the same model miss a cache it should have hit — and pay for it.
    tier: str
    result: ExtractionResult

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("cache entry requires an event_id: a stored extraction with no "
                             "event cannot be traced back to the message it read")
        if self.tier not in TIERS:
            raise ValueError(f"unknown model tier {self.tier!r}: expected one of {list(TIERS)}")
        mismatched = [
            (name, key_value, result_value)
            for name, key_value, result_value in (
                ("prompt_version", self.key.prompt_version, self.result.prompt_version),
                ("schema_version", self.key.schema_version, self.result.schema_version),
                ("model_snapshot", self.key.model_snapshot, self.result.model_snapshot),
                ("profile_id", self.key.profile_id, self.result.extraction_profile),
            )
            if key_value != result_value
        ]
        if mismatched:
            detail = "; ".join(f"key {name}={k!r} but extraction says {r!r}"
                               for name, k, r in mismatched)
            raise ValueError(
                f"extraction provenance does not match its cache key ({detail}). Filing it "
                "anyway would serve this result to every later reader of that key as though it "
                "had been produced under those settings — which is exactly how a prompt fix "
                "gets hidden by the cache it should have invalidated")

    @property
    def input_tokens(self) -> int:
        return self.result.input_tokens

    @property
    def output_tokens(self) -> int:
        return self.result.output_tokens


@dataclass(frozen=True)
class CacheOutcome:
    """What `cached_extraction` did, in terms a cost report can add up."""

    entry: CacheEntry
    #: True when the result came from the store and NO model was called.
    hit: bool
    #: True when this call wrote the row. False on a hit, and false on a miss that lost a race
    #: to a concurrent writer — the same content extracted twice at once, which costs money once
    #: more but must not raise.
    stored: bool

    @property
    def result(self) -> ExtractionResult:
        return self.entry.result

    @property
    def llm_calls(self) -> int:
        """0 on a hit, 1 on a miss. The number the cost governor (L1.4.8) meters, and the
        number the acceptance test asserts."""
        return 0 if self.hit else 1


class ExtractionCacheStore(Protocol):
    """The storage seam. Two methods, because a cache is two operations and no more."""

    def get(self, key: ExtractionCacheKey) -> CacheEntry | None: ...

    def put(self, entry: CacheEntry) -> bool:
        """True when this call wrote the row; False when it was already there."""
        ...


def cached_extraction(store: ExtractionCacheStore, key: ExtractionCacheKey, *, event_id: str,
                      tier: str, extract: Callable[[], ExtractionResult]) -> CacheOutcome:
    """L1.4.9-U2 · read through the cache, calling the model only on a miss.

    `extract` is a thunk — the prepared, fenced, assembled model call, not yet made. That is
    what makes "a hit costs zero LLM calls" structural instead of aspirational: on a hit this
    function returns before the thunk is ever invoked, so there is no path from a hit to a
    model. The test injects a client that raises when called, and a cache hit still returns.

    A miss stores what it extracted. `put` returning False means a concurrent worker stored the
    same key first — reported as `stored=False`, never raised: two workers extracting the same
    content at the same moment is a race that wasted one call, not a fault, and failing the
    second one would throw away an extraction that has already been paid for.
    """
    found = store.get(key)
    if found is not None:
        return CacheOutcome(entry=found, hit=True, stored=False)

    result = extract()
    if not isinstance(result, ExtractionResult):
        raise TypeError(
            f"extract() returned {type(result).__name__}, not an ExtractionResult: the cache "
            "stores the contract type, because everything downstream replays from this row")
    entry = CacheEntry(key=key, event_id=event_id, tier=tier, result=result)
    return CacheOutcome(entry=entry, hit=False, stored=store.put(entry))


class InMemoryExtractionCache:
    """A dict, for tests and for a dry run that must not write. Same refusals as the real one,
    because a store that accepts what PostgreSQL would reject is a store that hides the bug
    until deploy."""

    def __init__(self) -> None:
        self._rows: dict[str, CacheEntry] = {}

    def get(self, key: ExtractionCacheKey) -> CacheEntry | None:
        found = self._rows.get(key.processing_key)
        # The org check is redundant with the key (org_id is inside the digest) and is here for
        # the same reason the SQL has it: two locks on the tenant door, so a future change to
        # the key formula cannot quietly open it.
        if found is None or found.key.org_id != key.org_id:
            return None
        return found

    def put(self, entry: CacheEntry) -> bool:
        if entry.key.processing_key in self._rows:
            return False
        self._rows[entry.key.processing_key] = entry
        return True

    def __len__(self) -> int:
        return len(self._rows)


class PostgresExtractionCache:
    """The real cache. Inserts are `on conflict do nothing` against a content-addressed primary
    key, so a replay is a no-op rather than a second row or a raised duplicate."""

    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def get(self, key: ExtractionCacheKey) -> CacheEntry | None:
        """A miss and an unreadable row are the same answer: `None`, i.e. re-extract.

        A cache is not a place to fail. A row whose stored JSON no longer validates against the
        contract — written by a build whose shape has since changed, or corrupted — must cost one
        model call, not an exception on the ingestion path for every replay of that message. It
        is logged at WARNING because it should be impossible: `schema_version` is in the key, so
        a shape change already makes old rows unreachable.
        """
        with self._engine.connect() as conn:
            row = conn.execute(text(
                f"select event_id, tier, output from {CACHE_TABLE} "
                "where processing_key=:k and org_id=:o"),
                {"k": key.processing_key, "o": key.org_id}).first()
        if row is None:
            return None
        payload = row.output if isinstance(row.output, dict) else json.loads(row.output)
        try:
            result = ExtractionResult.model_validate(payload)
            return CacheEntry(key=key, event_id=row.event_id, tier=row.tier, result=result)
        except (ValueError, TypeError) as exc:      # pydantic ValidationError is a ValueError
            log.warning("unreadable extraction cache row, re-extracting: %s (%s)",
                        key.describe(), exc)
            return None

    def put(self, entry: CacheEntry) -> bool:
        with self._engine.begin() as conn:
            written = conn.execute(text(
                f"insert into {CACHE_TABLE} (processing_key, org_id, event_id, output, "
                "input_tokens, output_tokens, model_snapshot, profile_id, tier) "
                "values (:k, :o, :e, cast(:out as jsonb), :it, :ot, :m, :p, :t) "
                "on conflict (processing_key) do nothing"),
                {"k": entry.key.processing_key, "o": entry.key.org_id, "e": entry.event_id,
                 "out": json.dumps(entry.result.model_dump(mode="json"), default=str),
                 "it": entry.input_tokens, "ot": entry.output_tokens,
                 "m": entry.key.model_snapshot, "p": entry.key.profile_id,
                 "t": entry.tier}).rowcount
        return bool(written)


__all__ = ["CACHE_TABLE", "EMPTY_ENVELOPE", "KEY_COMPONENTS", "KEY_DIGEST_CHARS", "CacheEntry",
           "CacheOutcome", "ExtractionCacheKey", "ExtractionCacheStore",
           "InMemoryExtractionCache", "PostgresExtractionCache", "cache_key",
           "cached_extraction", "content_digest"]
