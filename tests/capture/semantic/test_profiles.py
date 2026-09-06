"""G3 · the extraction profile registry — Wave W3 (doc 04, L1.4.2-U1 and the derived U3).

    pytest tests/capture/semantic/test_profiles.py -q

Doc 04's acceptance line for U1 is three assertions — *5 profiles registered; every profile has
a non-empty template; every emphasis field name exists on ExtractionResult* — and the third is
the one with teeth. An emphasis naming a field the contract cannot store is a prompt asking the
model for an answer that is silently dropped at the boundary: tokens spent, meaning lost, no
error anywhere. So it is asserted against `ExtractionResult.model_fields` itself rather than
against a list copied into this file, which would drift with the contract and keep passing.

That check caught the doc: its own table names `dates` (email, document) and `obligations`
(document), and NEITHER is a field on `ExtractionResult`. The registry corrects them to
`dates_mentioned` and `commitments`, and `SPEC_TABLE` below records both the doc's word and the
correction so the divergence is visible here rather than only in a commit message.

The version half (U3) is asserted the way a cache key will read it: distinct per profile, stable
across calls, and CHANGED by a one-character edit to the template. That last row is the whole
unit. A hand-typed prompt version once let 260 cached extractions survive a prompt fix — the
prompt changed, the key did not, and the fix reached nothing.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

from genios_engine.capture.documents.chunking import NONE, SECTION, SENTENCE
from genios_engine.capture.semantic import profiles as mod
from genios_engine.capture.semantic.profiles import (BLOCK_MARKERS, EMPHASISABLE_FIELDS,
                                                     END_MARKER, NON_EMPHASISABLE_FIELDS,
                                                     PROFILE_IDS, PROFILES, TEMPLATE_PLACEHOLDERS,
                                                     ExtractionProfile, get_profile,
                                                     render_prompt)
from genios_engine.contracts.extraction import ExtractionResult

WAVE = "W3"
GATE = "G3"

#: Doc 04 L1.4.2-U1's table, transcribed — id, emphasis, default tier, max chars, chunking.
#: `doc_said` records the two names the doc used that do not exist on the contract, so the
#: correction is asserted rather than assumed: if someone "fixes" the registry back to the
#: doc's words, the emphasis-existence test below fails and this row explains why.
SPEC_TABLE = (
    # profile_id, emphasis, tier, max_input_chars, chunk_strategy, doc_said
    ("email", ("commitments", "decision_states", "dependencies", "dates_mentioned"),
     "T2", 24_000, SENTENCE, {"dates_mentioned": "dates"}),
    ("chat", ("stance", "questions", "scheduling_proposals"),
     "T1", 4_000, NONE, {}),
    ("transcript", ("commitments", "decision_states", "roles", "dependencies"),
     "T3", 40_000, SECTION, {}),
    ("document", ("amounts", "dates_mentioned", "entity_mentions", "commitments"),
     "T3", 40_000, SECTION, {"dates_mentioned": "dates", "commitments": "obligations"}),
    ("crm_note", ("decision_states", "stance", "entity_mentions"),
     "T1", 4_000, NONE, {}),
)

ROWS = [pytest.param(*row, id=row[0]) for row in SPEC_TABLE]

RENDER_ARGS = {"schema": '{"intent": "<one of INTENT>"}', "vocab": "INTENT: inform | commit",
               "envelope": "direction=inbound; from=rohit@example.com", "content": "hello there"}


def _email_template() -> str:
    return PROFILES["email"].prompt_template


def _profile_with(**overrides) -> ExtractionProfile:
    """Build a profile from the email profile's values with `overrides` applied.

    Constructing through the real dataclass, not a stub: `__post_init__` is the validation under
    test, and a test that built a dict would be asserting against nothing.
    """
    base = {"profile_id": "probe", "prompt_template": _email_template(),
            "emphasis": ("commitments",), "default_tier": "T2", "max_input_chars": 1_000,
            "chunk_strategy": SENTENCE}
    return ExtractionProfile(**{**base, **overrides})


# --------------------------------------------------------------------------------------------
# U1 · the registry
# --------------------------------------------------------------------------------------------

def test_exactly_the_five_declared_profiles_are_registered():
    """Doc 04: five profiles, and the mapping is keyed by the id each one calls itself."""
    assert tuple(PROFILES) == PROFILE_IDS
    assert len(PROFILES) == 5
    assert {key: p.profile_id for key, p in PROFILES.items()} == {k: k for k in PROFILE_IDS}


@pytest.mark.parametrize("profile_id, emphasis, tier, max_chars, strategy, doc_said", ROWS)
def test_registered_values_match_the_doc_04_table(profile_id, emphasis, tier, max_chars,
                                                  strategy, doc_said):
    """Every column of the spec table, per profile — the registry IS the table."""
    profile = PROFILES[profile_id]
    assert profile.emphasis == emphasis
    assert profile.default_tier == tier
    assert profile.max_input_chars == max_chars
    assert profile.chunk_strategy == strategy
    for corrected, doc_word in doc_said.items():
        assert corrected in profile.emphasis
        assert doc_word not in ExtractionResult.model_fields, (
            f"the doc's word {doc_word!r} is now a real field; the correction to {corrected!r} "
            "should be revisited rather than left in place")


@pytest.mark.parametrize("profile_id, emphasis, tier, max_chars, strategy, doc_said", ROWS)
def test_every_emphasis_field_exists_on_extraction_result(profile_id, emphasis, tier, max_chars,
                                                          strategy, doc_said):
    """The acceptance assertion, against the live contract: no unstorable emphasis."""
    unknown = [name for name in PROFILES[profile_id].emphasis
               if name not in ExtractionResult.model_fields]
    assert unknown == [], (f"{profile_id} emphasises fields ExtractionResult cannot store: "
                           f"{unknown}")


@pytest.mark.parametrize("profile_id, emphasis, tier, max_chars, strategy, doc_said", ROWS)
def test_no_profile_emphasises_provenance_or_trust_metadata(profile_id, emphasis, tier,
                                                            max_chars, strategy, doc_said):
    """Emphasis points the model at content. `prompt_version` is not something it can read."""
    assert not set(PROFILES[profile_id].emphasis) & NON_EMPHASISABLE_FIELDS


def test_emphasisable_fields_is_derived_from_the_contract_not_listed():
    """The allowed set is the contract's content fields, exactly — no hand-maintained copy."""
    assert EMPHASISABLE_FIELDS == set(ExtractionResult.model_fields) - NON_EMPHASISABLE_FIELDS
    assert NON_EMPHASISABLE_FIELDS <= set(ExtractionResult.model_fields)
    assert "importance_bp" not in EMPHASISABLE_FIELDS
    assert "commitments" in EMPHASISABLE_FIELDS


@pytest.mark.parametrize("profile_id, emphasis, tier, max_chars, strategy, doc_said", ROWS)
def test_every_template_is_non_empty_and_carries_the_four_placeholders(profile_id, emphasis,
                                                                       tier, max_chars,
                                                                       strategy, doc_said):
    """Doc 04's reverse prompt: {content} {vocab} {envelope} {schema}, and nothing else."""
    template = PROFILES[profile_id].prompt_template
    assert template.strip()
    assert mod._placeholders(template) == TEMPLATE_PLACEHOLDERS


GET_PROFILE_ROWS = (
    # asked, resolves to, warns
    ("email", "email", False),
    ("crm_note", "crm_note", False),
    ("transcript", "transcript", False),
    ("nonsense", "email", True),
    ("", "email", True),
    ("EMAIL", "email", True),            # ids are exact; a case variant is an unknown id
    ("structured", "email", True),       # the L1.3.9 bypass lane runs no prompt at all
)


@pytest.mark.parametrize("asked, resolves_to, warns", GET_PROFILE_ROWS)
def test_get_profile_resolves_or_degrades_but_never_raises(asked, resolves_to, warns, caplog):
    """Unknown id -> the email profile plus a warning. A stuck drain is worse than a thin one."""
    with caplog.at_level(logging.WARNING, logger=mod.__name__):
        profile = get_profile(asked)
    assert profile is PROFILES[resolves_to]
    assert bool(caplog.records) is warns
    if warns:
        assert asked.__repr__() in caplog.text


# --------------------------------------------------------------------------------------------
# U1 · construction refuses a profile that could not work
# --------------------------------------------------------------------------------------------

BAD_PROFILES = (
    # label, overrides, message fragment
    ("unknown tier", {"default_tier": "T4"}, "unknown tier"),
    ("lowercase tier", {"default_tier": "t2"}, "unknown tier"),
    ("unknown chunk strategy", {"chunk_strategy": "paragraph"}, "unknown chunk strategy"),
    ("zero max chars", {"max_input_chars": 0}, "must be positive"),
    ("negative max chars", {"max_input_chars": -1}, "must be positive"),
    ("blank id", {"profile_id": "  "}, "profile_id is required"),
    ("empty emphasis", {"emphasis": ()}, "emphasis is empty"),
    ("repeated emphasis", {"emphasis": ("commitments", "commitments")}, "repeats"),
    # The two names doc 04's own table used. Both must be refused, or the registry silently
    # ships a prompt asking for a field the contract drops.
    ("doc's `dates`", {"emphasis": ("dates",)}, "not a field on ExtractionResult"),
    ("doc's `obligations`", {"emphasis": ("obligations",)}, "not a field on ExtractionResult"),
    ("forbidden score", {"emphasis": ("importance_bp",)}, "not a field on ExtractionResult"),
    ("provenance field", {"emphasis": ("prompt_version",)}, "provenance or trust metadata"),
    ("trust field", {"emphasis": ("field_confidence",)}, "provenance or trust metadata"),
    ("empty template", {"prompt_template": "   "}, "prompt_template is empty"),
)


@pytest.mark.parametrize("label, overrides, fragment",
                         [pytest.param(*row, id=row[0]) for row in BAD_PROFILES])
def test_a_profile_that_could_not_work_is_refused_at_construction(label, overrides, fragment):
    with pytest.raises(ValueError, match=fragment):
        _profile_with(**overrides)


def test_a_well_formed_profile_still_constructs():
    """The negative table above is only meaningful if the positive case passes."""
    assert _profile_with().profile_id == "probe"


BAD_TEMPLATES = (
    ("missing block 6", lambda t: t.replace(BLOCK_MARKERS[5], ""), "missing"),
    ("missing block 1", lambda t: t.replace(BLOCK_MARKERS[0], ""), "missing"),
    ("blocks 5 and 6 swapped",
     lambda t: t.replace(BLOCK_MARKERS[4], "\x00").replace(BLOCK_MARKERS[5], BLOCK_MARKERS[4])
                .replace("\x00", BLOCK_MARKERS[5]), "out of order"),
    ("duplicated block 2", lambda t: t + f"\n{BLOCK_MARKERS[1]}\nagain\n", "more than once"),
    ("missing end marker", lambda t: t.replace(END_MARKER, ""), "missing \\[END BLOCKS\\]"),
    ("empty block body",
     lambda t: t.replace(mod.SAFETY_BLOCK, ""), "has an empty body"),
    ("missing placeholder", lambda t: t.replace("{schema}", "the usual shape"),
     "placeholders must be exactly"),
    ("extra placeholder", lambda t: t.replace("{content}", "{content}\n{tone}"),
     "placeholders must be exactly"),
    ("positional placeholder", lambda t: t.replace("{content}", "{0}"), "positional field"),
    ("automatic placeholder", lambda t: t.replace("{content}", "{}"), "automatic field"),
)


@pytest.mark.parametrize("label, mutate, fragment",
                         [pytest.param(*row, id=row[0]) for row in BAD_TEMPLATES])
def test_a_malformed_template_is_refused_at_construction(label, mutate, fragment):
    """Every way a template can be wrong fails at import, not at the customer's message."""
    with pytest.raises(ValueError, match=fragment):
        _profile_with(prompt_template=mutate(_email_template()))


# --------------------------------------------------------------------------------------------
# U3 · the version travels with the prompt
# --------------------------------------------------------------------------------------------

def test_prompt_versions_are_distinct_per_profile_and_shaped_for_a_cache_key():
    versions = {p.profile_id: p.prompt_version for p in PROFILES.values()}
    assert len(set(versions.values())) == 5
    for profile_id, version in versions.items():
        family, named, digest = version.split(":")
        assert family == mod.PROMPT_FAMILY
        assert named == profile_id
        assert len(digest) == mod.VERSION_DIGEST_CHARS
        assert set(digest) <= set("0123456789abcdef")


def test_prompt_version_is_stable_for_the_same_template_and_changes_with_it():
    """The unit's reason to exist: an edited prompt cannot keep its old cache key."""
    template = _email_template()
    assert _profile_with(prompt_template=template).prompt_version == \
        _profile_with(prompt_template=template).prompt_version

    edited = template.replace("You DESCRIBE what the text says.",
                              "You DESCRIBE what the text says!")
    assert edited != template
    assert _profile_with(prompt_template=edited).prompt_version != \
        _profile_with(prompt_template=template).prompt_version


def test_changing_what_a_profile_emphasises_changes_its_version():
    """Emphasis is written into the template, so it is inside the digest — one fact, one edit."""
    a = mod._build_template(mod._EMAIL_ROLE, ("commitments", "questions"))
    b = mod._build_template(mod._EMAIL_ROLE, ("questions", "commitments"))
    assert _profile_with(prompt_template=a).prompt_version != \
        _profile_with(prompt_template=b).prompt_version


def test_version_ignores_cost_only_fields():
    """A tier or a size cap changes what a call COSTS, not what it says. Re-extracting every
    stored message because a budget moved would be a bill with no new meaning at the end."""
    assert _profile_with(default_tier="T3", max_input_chars=9_999).prompt_version == \
        _profile_with(default_tier="T1", max_input_chars=10).prompt_version


@pytest.mark.parametrize("profile_id", PROFILE_IDS)
def test_prompt_version_is_storable_on_an_extraction_result(profile_id):
    """The version must survive the trip into the contract field that replays read it from."""
    profile = PROFILES[profile_id]
    result = ExtractionResult(intent="inform", stance="neutral", model_snapshot="fake-model-1",
                              prompt_version=profile.prompt_version, schema_version="1",
                              extraction_profile=profile.profile_id, input_tokens=1,
                              output_tokens=1)
    assert result.prompt_version == profile.prompt_version
    assert result.extraction_profile == profile_id


# --------------------------------------------------------------------------------------------
# U3 · rendering
# --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("profile_id", PROFILE_IDS)
def test_render_substitutes_all_four_blocks_and_leaves_no_placeholder(profile_id):
    rendered = render_prompt(profile_id, **RENDER_ARGS)
    assert rendered.profile_id == profile_id
    assert rendered.prompt_version == PROFILES[profile_id].prompt_version
    assert rendered.content_chars == len(RENDER_ARGS["content"])
    for value in RENDER_ARGS.values():
        assert value in rendered.text
    for name in TEMPLATE_PLACEHOLDERS:
        assert "{" + name + "}" not in rendered.text


def test_render_under_an_unknown_profile_reports_the_profile_that_actually_ran():
    """A row saying `crm_note` that was extracted under the email prompt is not a replay."""
    rendered = render_prompt("nonsense", **RENDER_ARGS)
    assert rendered.profile_id == "email"
    assert rendered.prompt_version == PROFILES["email"].prompt_version


def test_render_accepts_content_at_the_cap_and_refuses_one_character_more():
    """The boundary, both sides — an off-by-one here silently truncates or needlessly chunks."""
    cap = PROFILES["chat"].max_input_chars
    at_cap = "x" * cap
    assert render_prompt("chat", **{**RENDER_ARGS, "content": at_cap}).content_chars == cap
    assert PROFILES["chat"].fits(at_cap)
    assert not PROFILES["chat"].fits(at_cap + "x")
    with pytest.raises(ValueError, match="will not truncate"):
        render_prompt("chat", **{**RENDER_ARGS, "content": at_cap + "x"})


BAD_RENDERS = (
    ("empty content", {"content": "   "}, "content is empty"),
    ("empty schema", {"schema": ""}, "schema block is empty"),
    ("empty vocab", {"vocab": "\n"}, "vocabulary block is empty"),
)


@pytest.mark.parametrize("label, override, fragment",
                         [pytest.param(*row, id=row[0]) for row in BAD_RENDERS])
def test_render_refuses_an_assembly_that_would_invent(label, override, fragment):
    with pytest.raises(ValueError, match=fragment):
        render_prompt("email", **{**RENDER_ARGS, **override})


def test_render_allows_an_empty_envelope():
    """An uploaded document has no sender; demanding one would force a fabricated header."""
    rendered = render_prompt("document", **{**RENDER_ARGS, "envelope": ""})
    assert RENDER_ARGS["content"] in rendered.text


# --------------------------------------------------------------------------------------------
# purity
# --------------------------------------------------------------------------------------------

FORBIDDEN_IMPORT_PREFIXES = ("genios_engine.packs", "genios_engine.reason", "genios_engine.api",
                             "genios_engine.platform.db", "genios_engine.context", "anthropic",
                             "psycopg", "requests", "httpx")


def test_the_registry_imports_nothing_that_could_do_io():
    """A registry is data plus lookups. Asserted over the source tree with `ast`, so no import
    is executed and no ordering can make it pass by accident."""
    source = Path(mod.__file__).read_text(encoding="utf-8")
    imported: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.append(node.module)
    offenders = [name for name in imported
                 if any(name == p or name.startswith(p + ".") for p in FORBIDDEN_IMPORT_PREFIXES)]
    assert offenders == [], f"profiles.py must stay pure; it imports {offenders}"
