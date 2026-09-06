"""G2 · ALG-11 (L1.5.4) — the entity canonicalizer.

Doc 05 lists L1.5.4 in its component map and then never writes its units, so these tests are
written against the four things that DO constrain the unit — doc 00 §4 MAP B row 1 (no
embeddings; deterministic alias + domain matching), doc 08 C-04, ``contracts/extraction.py``'s
comment on ``canonical_hint``, and ALG-22's use of the hint inside ``subject_key``. Five
properties, and each one is something a layer above silently assumes:

* **Aliases and domains fold.** "AWS" (a vendor, in Slack) and "Amazon Web Services" (an
  organization, in the contract) reach the same hint, and so does the address at
  ``aws.amazon.com``. That is the unit's entire stated reason to exist.
* **Normalisation is the only fuzziness.** Case, punctuation, whitespace and legal-form tokens
  are folded when a key is DERIVED; keys are then compared with ``==``. "Acme, Inc." and
  "Acme Inc" therefore converge, and no threshold exists anywhere that could be nudged until
  "Apex Legal" and "Apex Logistics" do.
* **It never asserts identity.** A contested alias key produces NO hint and both claimants;
  a proposal has no id field to put an identity in; ``apply_to`` writes one field and leaves
  the surface form — the testimony — byte-identical.
* **It is idempotent.** Feeding a hint back in returns that hint. An ``ExtractionResult`` is
  cached and replayed, and ALG-22 derives ``subject_key`` from the hint; a hint that moved on
  second application would split one subject into two between runs.
* **It is symmetric and order-free.** Sameness is a property of the pair, not of which one was
  canonicalized first, so nothing may carry between calls.
"""

from __future__ import annotations

import dataclasses

import pytest

from genios_engine.capture.validate.canonical import (CONSUMER_EMAIL_DOMAINS,
                                                      DEFAULT_ALIAS_ENTRIES,
                                                      DEFAULT_ALIAS_TABLE, HINTED_BASES,
                                                      AliasEntry, AliasTable,
                                                      CanonicalProposal, EntityFamily,
                                                      EntityKey, HintBasis, KeyKind,
                                                      derive_key, fill_canonical_hints,
                                                      propose_canonical)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import EntityMention

WAVE = "W2"
GATE = "G2"


def _span(quote: str = "AWS") -> EvidenceSpan:
    return EvidenceSpan(source_ref="prepared_content:evt_1", quote=quote,
                        start_offset=0, end_offset=len(quote))


def _mention(surface_form: str, entity_type: str = "organization", *,
             confidence_bp: int = 8_000, hint: str | None = None) -> EntityMention:
    return EntityMention(surface_form=surface_form, entity_type=entity_type,
                         canonical_hint=hint, evidence=[_span()],
                         confidence_bp=confidence_bp)


def _hint(surface_form: str, entity_type: str = "organization", *,
          table: AliasTable = DEFAULT_ALIAS_TABLE) -> str | None:
    return propose_canonical(_mention(surface_form, entity_type), table=table).hint


# ======================================================================================
# L1.5.4-U1 · key derivation
# ======================================================================================

#: (surface_form, entity_type, expected kind, expected key, expected host, why)
DERIVE_ROWS: tuple[tuple[str, str, KeyKind, str | None, str | None, str], ...] = (
    ("Acme, Inc.", "organization", KeyKind.NAME, "acme", None,
     "punctuation folds and a legal-form token is dropped"),
    ("Acme Inc", "organization", KeyKind.NAME, "acme", None,
     "the same name without the comma must derive the same key"),
    ("  ACME   Technologies  Pvt  Ltd ", "organization", KeyKind.NAME, "acme technologies",
     None, "case folds, runs of whitespace collapse, two legal tokens drop"),
    ("Co", "organization", KeyKind.NAME, "co", None,
     "never trim a name to nothing: a one-word legal token stays"),
    ("acme.io", "vendor", KeyKind.HOST, "acme", "acme.io",
     "a bare host is read as a host and reduced to its label"),
    ("https://www.acme.co.uk/pricing?q=1", "vendor", KeyKind.HOST, "acme", "acme.co.uk",
     "scheme, www, path and query are stripped; a compound TLD keeps the label"),
    ("Node.js", "product", KeyKind.NAME, "node js",
     None, "an unlisted final label is a name, not a host — a product is not a domain"),
    ("billing@aws.amazon.com", "vendor", KeyKind.EMAIL, "amazon", "aws.amazon.com",
     "an address yields its host; the '@' needs no TLD allowlist"),
    ("Priya <priya+cal@acme.io>", "person", KeyKind.EMAIL, "priya@acme.io", "acme.io",
     "a display form unwraps and a +tag is stripped — the person key, not the company"),
    ("mailto:Priya@Acme.io", "person", KeyKind.EMAIL, "priya@acme.io", "acme.io",
     "a mailto: prefix is not part of the address"),
    ("Rohit  S.", "person", KeyKind.NAME, "rohit s", None,
     "a person name folds punctuation and whitespace but keeps both words"),
    ("acme.io", "person", KeyKind.NAME, "acme io", None,
     "a host typed as a person is a weird name, never promoted to the company"),
    ("Priya @ Acme", "person", KeyKind.NAME, "priya acme", None,
     "an '@' that is not an address does not make an address"),
    ("", "organization", KeyKind.NONE, None, None, "nothing in, nothing out"),
    ("  ,,, --- ", "organization", KeyKind.NONE, None, None,
     "punctuation only normalises to nothing, and that is None rather than a guess"),
    ("Acme, Inc.", "robot", KeyKind.NAME, "acme", None,
     "an entity_type outside doc 04's set still derives a key — totality, never a crash"),
)


@pytest.mark.parametrize("surface_form,entity_type,kind,key,host,why", DERIVE_ROWS,
                         ids=[row[5] for row in DERIVE_ROWS])
def test_derive_key_normalises(surface_form: str, entity_type: str, kind: KeyKind,
                               key: str | None, host: str | None, why: str) -> None:
    assert derive_key(surface_form, entity_type=entity_type) == EntityKey(
        family=derive_key(surface_form, entity_type=entity_type).family,
        kind=kind, key=key, host=host), why


#: (entity_type, expected family, why)
FAMILY_ROWS: tuple[tuple[str, EntityFamily, str], ...] = (
    ("person", EntityFamily.PERSON, "doc 04's person"),
    ("organization", EntityFamily.ORG, "organization and vendor share ONE namespace..."),
    ("vendor", EntityFamily.ORG, "...because one company arrives typed both ways"),
    ("product", EntityFamily.PRODUCT, "a product keeps its own namespace"),
    ("project", EntityFamily.PROJECT, "a project called Acme is not the customer Acme"),
    ("document", EntityFamily.DOCUMENT, "a document keeps its own namespace"),
    ("  VENDOR ", EntityFamily.ORG, "the type is matched case- and whitespace-insensitively"),
    ("robot", EntityFamily.OTHER, "an unknown type lands in a namespace nothing populates"),
    ("", EntityFamily.OTHER, "an empty type is unknown, not a crash"),
)


@pytest.mark.parametrize("entity_type,family,why", FAMILY_ROWS,
                         ids=[row[2] for row in FAMILY_ROWS])
def test_entity_type_family(entity_type: str, family: EntityFamily, why: str) -> None:
    assert derive_key("Acme", entity_type=entity_type).family is family, why


# ======================================================================================
# L1.5.4-U2 · alias match, domain match, normalisation match
# ======================================================================================

#: (surface_form, entity_type, expected hint, expected basis, why)
ALIAS_ROWS: tuple[tuple[str, str, str, HintBasis, str], ...] = (
    ("AWS", "vendor", "amazon web services", HintBasis.ALIAS_TABLE,
     "the headline case: the three-letter alias reaches the full name"),
    ("Amazon Web Services", "organization", "amazon web services", HintBasis.ALIAS_TABLE,
     "and so does the full name typed as an organization — one hint, two entity_types"),
    ("Amazon Web Services, Inc.", "vendor", "amazon web services", HintBasis.ALIAS_TABLE,
     "the legal name normalises onto the same alias key"),
    ("aws", "vendor", "amazon web services", HintBasis.ALIAS_TABLE, "case is irrelevant"),
    ("GCP", "vendor", "google cloud platform", HintBasis.ALIAS_TABLE, "a second alias group"),
    ("Salesforce.com", "vendor", "salesforce", HintBasis.DOMAIN_TABLE,
     "a written name that is also a registered host resolves through the domain index"),
    ("billing@aws.amazon.com", "vendor", "amazon web services", HintBasis.DOMAIN_TABLE,
     "domain matching: an address at a registered host"),
    ("https://eu.aws.amazon.com/pricing", "organization", "amazon web services",
     HintBasis.DOMAIN_TABLE,
     "a subdomain resolves to the longest registered suffix"),
    ("acme.io", "organization", "acme", HintBasis.DOMAIN_LABEL,
     "an unregistered host falls to its label rather than to nothing"),
    ("priya@acme.io", "organization", "acme", HintBasis.DOMAIN_LABEL,
     "and an address at that host reaches the same label — this is the domain match"),
    ("Acme, Inc.", "organization", "acme", HintBasis.NORMALISED_FORM,
     "which is the same hint the written name reaches, with no table entry at all"),
    ("Priya <priya+cal@acme.io>", "person", "priya@acme.io", HintBasis.EMAIL_IDENTITY,
     "a person is their address, +tag stripped — never their employer"),
    ("Rohit S.", "person", "rohit s", HintBasis.NORMALISED_FORM,
     "a person with no address is their folded name"),
    ("rohit@gmail.com", "person", "rohit@gmail.com", HintBasis.EMAIL_IDENTITY,
     "a consumer address is still the strongest key a person has"),
    ("AWS", "project", "aws", HintBasis.NORMALISED_FORM,
     "a PROJECT called AWS is not the vendor: namespaces do not leak"),
    ("AWS", "robot", "aws", HintBasis.NORMALISED_FORM,
     "nor does an unrecognised entity_type pick up somebody else's canonical"),
)


@pytest.mark.parametrize("surface_form,entity_type,hint,basis,why", ALIAS_ROWS,
                         ids=[row[4] for row in ALIAS_ROWS])
def test_cascade(surface_form: str, entity_type: str, hint: str, basis: HintBasis,
                 why: str) -> None:
    proposal = propose_canonical(_mention(surface_form, entity_type))
    assert (proposal.hint, proposal.basis) == (hint, basis), why


#: Pairs that MUST converge. Each is a real spelling of one thing.
SAME_ROWS: tuple[tuple[tuple[str, str], tuple[str, str], str], ...] = (
    (("AWS", "vendor"), ("Amazon Web Services", "organization"),
     "the alias table folds vendor and organization into one hint"),
    (("Acme, Inc.", "organization"), ("Acme Inc", "organization"),
     "punctuation is not identity"),
    (("Acme, Inc.", "organization"), ("ACME", "vendor"),
     "case and a legal suffix are not identity"),
    (("Acme Technologies Pvt Ltd", "organization"), ("Acme  Technologies", "vendor"),
     "legal-form tokens and doubled whitespace drop out"),
    (("acme.io", "organization"), ("Acme, Inc.", "vendor"),
     "domain match meets name match on the same label"),
    (("billing@aws.amazon.com", "vendor"), ("AWS", "organization"),
     "domain match and alias match agree"),
    (("priya+cal@acme.io", "person"), ("Priya <PRIYA@Acme.io>", "person"),
     "a +tag and a display form are one person"),
)


@pytest.mark.parametrize("left,right,why", SAME_ROWS, ids=[row[2] for row in SAME_ROWS])
def test_converges(left: tuple[str, str], right: tuple[str, str], why: str) -> None:
    left_hint, right_hint = _hint(*left), _hint(*right)
    assert left_hint is not None and left_hint == right_hint, why


#: Pairs that MUST NOT be forced together. Every one of them shares a token, a substring or a
#: domain root with its partner — which is exactly what a similarity model would merge.
DIFFERENT_ROWS: tuple[tuple[tuple[str, str], tuple[str, str], str], ...] = (
    (("Apex Legal", "organization"), ("Apex Logistics", "organization"),
     "a shared first word is not a shared company"),
    (("Amazon", "organization"), ("Amazon Web Services", "vendor"),
     "the retailer is not the cloud vendor, however long the shared prefix"),
    (("orders@amazon.com", "vendor"), ("billing@aws.amazon.com", "vendor"),
     "a registered subdomain does not drag its parent domain along"),
    (("Delta Air Lines", "organization"), ("Delta Dental", "organization"),
     "a shared brand word across two industries"),
    (("AWS", "vendor"), ("AWS", "project"),
     "the vendor and an internal project of the same name stay in different namespaces"),
    (("rohit@gmail.com", "person"), ("priya@gmail.com", "person"),
     "two people on one consumer host are two people"),
    (("Node.js", "product"), ("node.io", "product"),
     "a dotted product name is not the host it resembles"),
)


@pytest.mark.parametrize("left,right,why", DIFFERENT_ROWS,
                         ids=[row[2] for row in DIFFERENT_ROWS])
def test_does_not_force_together(left: tuple[str, str], right: tuple[str, str],
                                 why: str) -> None:
    left_proposal = propose_canonical(_mention(*left))
    right_proposal = propose_canonical(_mention(*right))
    assert (left_proposal.hint, left_proposal.family) != (right_proposal.hint,
                                                          right_proposal.family), why


# ======================================================================================
# The refusals — where the unit answers "I don't know" instead of guessing
# ======================================================================================

#: (surface_form, entity_type, why)
NO_BASIS_ROWS: tuple[tuple[str, str, str], ...] = (
    ("rohit@gmail.com", "organization",
     "a free mail host names no company — 'gmail' would be a fabricated vendor"),
    ("info@mail.yahoo.co.uk", "vendor",
     "the check looks at the registrable domain too, not just the exact host"),
    (" ,,, ", "organization", "punctuation only leaves nothing to propose"),
    (" -- ", "person", "and the same for a person"),
)


@pytest.mark.parametrize("surface_form,entity_type,why", NO_BASIS_ROWS,
                         ids=[row[2] for row in NO_BASIS_ROWS])
def test_refuses_without_a_basis(surface_form: str, entity_type: str, why: str) -> None:
    proposal = propose_canonical(_mention(surface_form, entity_type))
    assert (proposal.hint, proposal.basis) == (None, HintBasis.NO_BASIS), why


CONTESTED_TABLE = AliasTable.build((
    AliasEntry(canonical="acme technologies", entity_type="organization",
               aliases=("Acme", "Acme Inc"), domains=("acme.io",)),
    AliasEntry(canonical="acme foods", entity_type="vendor",
               aliases=("ACME",), domains=("acme.io",)),
    AliasEntry(canonical="unrelated holdings", entity_type="organization",
               aliases=("Unrelated",)),
))


def test_a_contested_alias_produces_no_hint() -> None:
    """AMBIGUITY IS NOT A MATCH — L2's law, one layer down. Picking the first row here is the
    invisible merge the contract's comment on ``canonical_hint`` exists to forbid."""
    proposal = propose_canonical(_mention("Acme", "organization"), table=CONTESTED_TABLE)
    assert proposal.hint is None
    assert proposal.basis is HintBasis.AMBIGUOUS
    assert proposal.alternatives == ("acme foods", "acme technologies")


def test_a_contested_domain_produces_no_hint() -> None:
    proposal = propose_canonical(_mention("sales@acme.io", "vendor"), table=CONTESTED_TABLE)
    assert (proposal.hint, proposal.basis) == (None, HintBasis.AMBIGUOUS)
    assert proposal.alternatives == ("acme foods", "acme technologies")


def test_a_collision_does_not_poison_the_rest_of_the_table() -> None:
    """One contested key is refused; every other key in the same table still answers."""
    assert CONTESTED_TABLE.conflicts == ("domain:org:acme.io", "name:org:acme")
    assert _hint("Unrelated", "organization", table=CONTESTED_TABLE) == "unrelated holdings"
    assert _hint("Acme Technologies", "organization",
                 table=CONTESTED_TABLE) == "acme technologies"


# ======================================================================================
# Table integrity — the constant is data, and malformed data fails loudly at build
# ======================================================================================


def test_shipped_table_has_no_collisions() -> None:
    assert DEFAULT_ALIAS_TABLE.conflicts == ()


@pytest.mark.parametrize("entry", DEFAULT_ALIAS_ENTRIES,
                         ids=[entry.canonical for entry in DEFAULT_ALIAS_ENTRIES])
def test_every_shipped_canonical_is_its_own_key(entry: AliasEntry) -> None:
    """Closure starts here: a canonical that renormalises would make its own hint unstable."""
    assert derive_key(entry.canonical, entity_type=entry.entity_type).key == entry.canonical


#: (entry, fragment of the expected message, why)
BAD_ENTRY_ROWS: tuple[tuple[AliasEntry, str, str], ...] = (
    (AliasEntry(canonical="Acme, Inc.", entity_type="organization"), "own derived key",
     "a canonical carrying punctuation would resolve to something else on the next pass"),
    (AliasEntry(canonical="", entity_type="organization"), "no canonical name",
     "an entry with no canonical names nothing"),
    (AliasEntry(canonical="acme", entity_type="robot"), "ENTITY_TYPE",
     "an entry cannot be filed under a family the vocabulary does not have"),
    (AliasEntry(canonical="acme", entity_type="organization", aliases=(" ,, ",)),
     "normalises to nothing", "an alias that folds away claims every empty key"),
    (AliasEntry(canonical="acme", entity_type="organization", domains=("acme",)),
     "is not a host", "a domain with no dot is a typo, not a domain"),
)


@pytest.mark.parametrize("entry,fragment,why", BAD_ENTRY_ROWS,
                         ids=[row[2] for row in BAD_ENTRY_ROWS])
def test_build_rejects_a_malformed_entry(entry: AliasEntry, fragment: str, why: str) -> None:
    with pytest.raises(ValueError, match=fragment):
        AliasTable.build((entry,))
    assert why


def test_consumer_domains_are_data_not_a_lookup() -> None:
    """The guard list is a frozen constant, so the same address canonicalizes the same way on
    every machine and in every replay."""
    assert isinstance(CONSUMER_EMAIL_DOMAINS, frozenset)
    assert "gmail.com" in CONSUMER_EMAIL_DOMAINS


# ======================================================================================
# The properties: idempotent, symmetric, order-free
# ======================================================================================

CORPUS: tuple[tuple[str, str], ...] = tuple(
    [(row[0], row[1]) for row in ALIAS_ROWS]
    + [(row[0], row[1]) for row in NO_BASIS_ROWS]
    + [pair for row in SAME_ROWS for pair in (row[0], row[1])]
    + [pair for row in DIFFERENT_ROWS for pair in (row[0], row[1])]
)


@pytest.mark.parametrize("surface_form,entity_type", CORPUS,
                         ids=[f"{form}|{kind}" for form, kind in CORPUS])
def test_hint_is_idempotent(surface_form: str, entity_type: str) -> None:
    """Proposing on a hint returns that hint. ALG-22 builds ``subject_key`` from it and an
    ``ExtractionResult`` is replayed from cache, so a value that moved on the second pass
    would split one subject into two between runs."""
    first = propose_canonical(_mention(surface_form, entity_type))
    assert propose_canonical(_mention(surface_form, entity_type)) == first, "deterministic"
    if first.hint is None:
        # A refusal is idempotent too: there is nothing to feed back, and the refusal itself
        # must not drift into an answer on a second pass.
        assert first.basis in (HintBasis.AMBIGUOUS, HintBasis.NO_BASIS)
        return
    second = propose_canonical(_mention(first.hint, entity_type))
    assert second.hint == first.hint
    assert propose_canonical(_mention(second.hint or "", entity_type)).hint == first.hint


@pytest.mark.parametrize("surface_form,entity_type", CORPUS,
                         ids=[f"{form}|{kind}" for form, kind in CORPUS])
def test_derived_key_is_idempotent(surface_form: str, entity_type: str) -> None:
    once = derive_key(surface_form, entity_type=entity_type)
    if once.key is None:
        assert once.kind is KeyKind.NONE, "no key means the form yielded nothing at all"
        return
    assert derive_key(once.key, entity_type=entity_type).key == once.key


@pytest.mark.parametrize("left,right,why", SAME_ROWS + DIFFERENT_ROWS,
                         ids=[row[2] for row in SAME_ROWS + DIFFERENT_ROWS])
def test_sameness_is_symmetric(left: tuple[str, str], right: tuple[str, str],
                               why: str) -> None:
    """Whether two mentions agree cannot depend on which one was asked about first, so the
    unit may hold no state between calls."""
    forward = (_hint(*left), _hint(*right))
    backward = (_hint(*right), _hint(*left))
    assert forward == backward[::-1], why


def test_batch_order_does_not_change_any_hint() -> None:
    """The same corpus canonicalized forwards and backwards yields the same mapping — the
    property that makes a batch of mentions safe to process in any order."""
    forward = {pair: propose_canonical(_mention(*pair)) for pair in CORPUS}
    backward = {pair: propose_canonical(_mention(*pair)) for pair in reversed(CORPUS)}
    assert forward == backward


@pytest.mark.parametrize("surface_form,entity_type", CORPUS,
                         ids=[f"{form}|{kind}" for form, kind in CORPUS])
def test_hint_present_exactly_when_a_rule_fired(surface_form: str, entity_type: str) -> None:
    proposal = propose_canonical(_mention(surface_form, entity_type))
    assert (proposal.hint is not None) is (proposal.basis in HINTED_BASES)
    assert (proposal.alternatives != ()) is (proposal.basis is HintBasis.AMBIGUOUS)


# ======================================================================================
# The boundary: a hint is a hint
# ======================================================================================


def test_a_proposal_cannot_express_an_identity() -> None:
    """The type has no id, no node reference and no 'resolved' flag, so no call site can read
    one out of it. L2 owns identity; this unit only hands it a better-shaped question."""
    assert {f.name for f in dataclasses.fields(CanonicalProposal)} == {
        "hint", "basis", "family", "key", "alternatives"}


def test_apply_to_writes_one_field_and_leaves_the_testimony_alone() -> None:
    mention = _mention("Amazon Web Services, Inc.", "vendor", confidence_bp=7_431)
    filled = propose_canonical(mention).apply_to(mention)
    assert filled.canonical_hint == "amazon web services"
    assert filled.surface_form == "Amazon Web Services, Inc."
    assert filled.entity_type == "vendor"
    assert filled.confidence_bp == 7_431
    assert filled.evidence == mention.evidence
    assert mention.canonical_hint is None, "the input mention must not be mutated"


def test_a_hint_does_not_move_confidence() -> None:
    """Canonicalization is not evidence. A mention does not become more credible because a
    table recognised its name, and ALG-13 is the only unit allowed to move this number."""
    for surface_form, entity_type in CORPUS:
        mention = _mention(surface_form, entity_type, confidence_bp=5_000)
        assert fill_canonical_hints([mention])[0].confidence_bp == 5_000


def test_fill_preserves_a_hint_it_did_not_write() -> None:
    mention = _mention("AWS", "vendor", hint="amazon-web-services-us-east")
    assert fill_canonical_hints([mention])[0].canonical_hint == "amazon-web-services-us-east"
    assert fill_canonical_hints([mention], overwrite=True)[0].canonical_hint == (
        "amazon web services")


def test_fill_leaves_a_mention_with_no_basis_untouched() -> None:
    mention = _mention("rohit@gmail.com", "organization")
    assert fill_canonical_hints([mention])[0].canonical_hint is None


def test_fill_is_a_pure_mapping_over_the_sequence() -> None:
    mentions = [_mention("AWS", "vendor"), _mention("Acme, Inc."), _mention(" ,, ")]
    filled = fill_canonical_hints(mentions)
    assert [m.canonical_hint for m in filled] == ["amazon web services", "acme", None]
    assert [m.canonical_hint for m in mentions] == [None, None, None]
    assert fill_canonical_hints([]) == ()
