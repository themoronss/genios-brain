"""Business Situation -> domain situations -> capability plan."""

from __future__ import annotations

from collections.abc import Mapping

from genios_engine.contracts.domain_expertise import (
    BusinessSituationObject,
    SituationContextSlice,
)

from .authoring import ExpertBrainCatalog
from .context_adapter import ContextAdapter, PredicateState
from .errors import (
    AuthoringIntegrityError,
    NoExpertiseRoute,
    SituationContextIncomplete,
    UnsupportedCoverage,
)
from .models import RoutePlan

#: Corpus domain folder names that differ from the Layer 2 domain id for the same thing.
#:
#: `context/domain_spec.py` registers `support`; the authored corpus folder is "Customer Support
#: Expertise" and declares `customer_support`. Both name one domain, and the mismatch alone sent
#: 56 of one tenant's 73 situations to NoExpertiseRoute before any situation type was compared.
#: Aliasing at the boundary keeps each side free to use its own natural name — the corpus is
#: written by humans and reads better as `customer_support`, while L2's id is a registry key.
DOMAIN_ALIASES: dict[str, str] = {
    "support": "customer_support",
    # Fundraising is authored inside the Sales corpus, in its own `investor_relations`
    # subdomain. Not because an investor is a customer — the capability exists precisely to
    # refuse that reading — but because a compiled signal can only carry authority in a pack
    # lane the tenant actually holds (`_tenant_pack`: the config snapshot's `pack_id` must
    # equal the capability's domain). Splitting fundraising into its own corpus domain would
    # have produced a capability that compiles, reasons, and can never become a card.
    "fundraising": "sales",
    # `investor` is the SAME domain under the model's own word for it — `_RELATIONSHIP_NATURES`
    # in the L2 pipeline offers `investor`, the registry calls it `fundraising`, and the two never
    # met. `context.domain_spec._ALIASES` now canonicalises the name where a hint becomes THE
    # domain, so nothing new is stored as `investor`; this entry exists because situations already
    # stored under the old name are real and re-typing history silently would be worse than
    # reading it. Deliberately duplicated rather than imported: L2 and L3 share no module today,
    # and one import to save one line of data is not worth the edge.
    "investor": "sales",
}

#: Layer 2 domain ids that are NOT a domain — they mean "no domain was identified".
#:
#: `context/correlation.py` falls back to `general` whenever its keyword hints produce nothing,
#: which is 53 of one tenant's 73 situations. Treating that as a domain NAME sends the lookup
#: hunting for a "general" corpus that does not and should not exist; treating it as an absent
#: hint lets the resolver do what it already does for an unhinted situation — consider every
#: domain and let the `when` predicates decide. Unclassified must mean "look everywhere",
#: never "look nowhere".
UNCLASSIFIED_DOMAINS: frozenset[str] = frozenset({"general", "unknown", ""})


def _plain(value):
    """Deep copy an authored fragment into ordinary dicts/lists.

    Catalog documents are frozen (`freeze_mapping`), so a nested block lifted straight off one
    arrives as a `mappingproxy`. The canonical encoder happens to accept that today; the plan is
    a value object crossing into two more layers and a JSONB column, and it should not depend on
    that.
    """
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _load_set(manifest: dict) -> tuple[set[str], set[str]]:
    required: set[str] = set()
    optional: set[str] = set()
    for bucket in ("core", "scoped"):
        block = manifest.get(bucket) or {}
        required.update(block.get("required") or ())
        optional.update(block.get("optional") or ())
    optional -= required
    return required, optional



#: Keys a capability file carries that are a LABEL rather than expertise. A file with nothing
#: outside this set has a name, a sentence and a question.
_LABEL_KEYS = frozenset({"identity", "description", "question", "metadata", "admission"})


def _hollow(capability) -> bool:
    """Admitted, hash-pinned, and saying nothing.

    The ceremony asks whether a named human approved these exact bytes. It never asked whether
    there were any bytes worth approving, so 136 of the corpus's capabilities are `stable`,
    `approved` and hash-pinned over a file whose own notes read "Phase 1 stub — identity, purpose
    and object load-set only". Three of them were reached by every routed situation on the design
    partner's org, which is a large part of why eighteen compiled cards read alike.

    RECORDED, NOT SKIPPED. A hollow capability still routes: refusing it today would un-route
    `account_admin` entirely — all three Admin capabilities behind it are hollow — and take live
    coverage backwards. It lands in `admission_gaps`, which flows to the package's
    `review_state`/`admission_gaps` metadata, so a compile can be asked "how much of this answer
    came from placeholders?" and give a number instead of a shrug.
    """
    return not (set(capability.content) - _LABEL_KEYS)


def _admission_reason(capability) -> str | None:
    """None = admitted. Else the named reason this capability may not carry authority."""
    content = capability.content
    identity = content.get("identity") or {}
    metadata = content.get("metadata") or {}
    admission = content.get("admission") or {}
    if identity.get("stub"):
        return "stub"
    if str(identity.get("status") or "") != "stable":
        return f"identity_status_{identity.get('status') or 'absent'}"
    if str(metadata.get("review_status") or "") != "approved":
        return "review_not_approved"
    if not str(metadata.get("reviewed_by") or "").strip():
        return "no_named_reviewer"
    accepted_hash = str(admission.get("accepted_content_hash") or "")
    if not accepted_hash:
        return "no_accepted_hash"
    # Hash of the content MINUS the admission block: the reviewer accepted the capability, and
    # the acceptance record is not part of what they reviewed — hashing it in would make
    # self-consistent acceptance impossible (the record would have to contain its own hash).
    from genios_engine.platform.canonical import semantic_hash
    reviewed = {k: v for k, v in content.items() if k != "admission"}
    if accepted_hash != semantic_hash(reviewed):
        return "content_changed_since_acceptance"
    return None

class CapabilityResolver:
    """Uses the generated reverse index, then narrows it with authored situation predicates."""

    def __init__(self, catalog: ExpertBrainCatalog, *, max_capabilities: int = 64,
                 max_objects: int = 128, require_admission: bool = True) -> None:
        self.catalog = catalog
        self.max_capabilities = max_capabilities
        self.max_objects = max_objects
        #: Fail-closed default. False is for MEASUREMENT compiles only (the shadow pass, the
        #: corpus tests): unadmitted content may flow, but the plan says so (`admitted=False` +
        #: per-capability gaps), and the delivery layer's abstention gate keeps anything built
        #: from it non-prescriptive. What False must never do is silently grant authority —
        #: which is why it is a constructor argument, not a per-call escape hatch.
        self.require_admission = require_admission

    def resolve(self, situation: BusinessSituationObject,
                context: SituationContextSlice | None = None) -> RoutePlan:
        hints = {DOMAIN_ALIASES.get(h, h) for h in situation.domain_hints
                 if h not in UNCLASSIFIED_DOMAINS}
        unknown_hints = hints - set(self.catalog.domains)
        if unknown_hints:
            raise NoExpertiseRoute(
                f"situation {situation.id!r} names unknown domains {sorted(unknown_hints)}")
        domain_ids = sorted(hints or self.catalog.domains.keys())
        adapter = ContextAdapter(situation, context)
        selected_domains: set[str] = set()
        situation_ids: set[str] = set()
        capability_ids: set[str] = set()
        required: set[str] = set()
        optional: set[str] = set()
        never: set[str] = set()
        unresolved: set[str] = set()
        skipped_capabilities: set[str] = set()
        skipped_reasons: dict[str, str] = {}
        admission_gaps: list[str] = []
        hollow_capabilities: set[str] = set()
        render: dict | None = None
        render_situation_id: str | None = None
        render_rank: tuple[int, str] | None = None
        priority_bp: int | None = None
        priority_situation_id: str | None = None
        priority_rank: tuple[int, str] | None = None
        saw_index_route = False

        for domain_id in domain_ids:
            domain = self.catalog.domain(domain_id)
            route = domain.routes.get(situation.type)
            if not isinstance(route, Mapping):
                continue
            saw_index_route = True
            selected_here: list[str] = []
            for situation_id in route.get("situations") or ():
                source = domain.situations.get(situation_id)
                if source is None:
                    raise AuthoringIntegrityError(
                        f"registry route references missing situation {situation_id!r}")
                matches = source.content.get("matches") or {}
                conditions = matches.get("when") or ()
                verdict = adapter.matches(conditions)
                if verdict.state is PredicateState.TRUE:
                    selected_here.append(situation_id)
                elif verdict.state is PredicateState.UNKNOWN:
                    unresolved.update(f"{situation_id}:{item}" for item in verdict.missing)

            if not selected_here:
                continue
            selected_domains.add(domain_id)
            situation_ids.update(selected_here)
            local_capabilities: set[str] = set()
            for situation_id in selected_here:
                authored = domain.situations[situation_id].content
                # THE CARD COPY IS PART OF THE EXPERTISE, so it is collected here with the rest
                # of what the situation declares. Without it the delivery layer looked the copy
                # up in the TENANT PACK by reason_code — and a compiled signal's reason_code is
                # its situation type, which no pack authors. Every compiled card therefore
                # rendered against an empty template: no guidance in the prompt, and a fallback
                # of "{entity}" / "{stage}" that shipped the literal word "open" as a situation
                # line on ten of the design partner's eighteen live cards.
                # THE AUTHORED PRIORITY IS EXPERTISE TOO, and it used to be read here, used to
                # sort, and then dropped on the floor. Ranked over EVERY selected situation
                # rather than only those carrying card copy: a situation can rank a route without
                # authoring its words, and reading priority off the copy-winner would let a
                # rendering decision quietly decide the ranking.
                authored_priority = authored.get("priority_bp")
                if authored_priority is not None:
                    p_rank = (-int(authored_priority), situation_id)
                    if priority_rank is None or p_rank < priority_rank:
                        priority_rank = p_rank
                        priority_bp = int(authored_priority)
                        priority_situation_id = situation_id

                render_block = authored.get("render")
                if isinstance(render_block, Mapping) and render_block:
                    # A type can match several situations. Rank by the priority the AUTHOR
                    # declared, not by iteration or alphabetical accident, and break ties on id
                    # so the choice is reproducible byte-for-byte across compiles.
                    rank = (-int((authored.get("priority_bp") or 0)), situation_id)
                    if render_rank is None or rank < render_rank:
                        render_rank = rank
                        render = _plain(render_block)
                        render_situation_id = situation_id
                owner = (authored.get("identity") or {}).get("owner_capability")
                serving = ([owner] if owner else []) + list(authored.get("also_serves") or ())
                local_capabilities.update(value for value in serving if value)
                objects = authored.get("objects") or {}
                required.update(objects.get("load") or ())
                optional.update(objects.get("optional") or ())
                never.update(objects.get("never_load") or ())

            for capability_id in tuple(local_capabilities):
                capability = domain.capabilities.get(capability_id)
                if capability is None:
                    raise AuthoringIntegrityError(
                        f"routed capability {capability_id!r} is not authored")
                # ADMISSION, not just non-stubness. `identity.stub` was the entire production-
                # admission ceremony: an author flipping `stub: true → false` in a text editor
                # granted production authority, and the first content to gain customer authority
                # on activation would have been 12 machine-written unreviewed drafts
                # (`metadata.created_by: ai`). A capability routes only when a named human
                # ACCEPTED the exact bytes being routed:
                #   identity.status == 'stable'
                #   metadata.review_status == 'approved' with a non-empty reviewed_by
                #   admission.accepted_content_hash == the catalog's computed content hash
                # The hash pin is the difference between accepting a FILE and accepting its
                # CONTENT — an edit after review silently un-accepts, which is the point.
                if _hollow(capability):
                    # Its OWN field, deliberately not `admission_gaps`. That list drives
                    # `plan.admitted`, which drives the package's `review_state`, which decides
                    # whether a card may instruct — folding a content observation into it would
                    # silently make "thin" mean "unauthorised" and prevent any package containing
                    # a single placeholder from EVER being accepted. Two different questions.
                    hollow_capabilities.add(capability_id)
                verdict_reason = _admission_reason(capability)
                if verdict_reason is not None:
                    admission_gaps.append(f"{capability_id}:{verdict_reason}")
                    if self.require_admission or verdict_reason == "stub":
                        # A stub is skipped in EVERY mode — there is nothing to measure. Other
                        # admission gaps route in measurement mode, flagged, never silently.
                        local_capabilities.remove(capability_id)
                        skipped_capabilities.add(capability_id)
                        skipped_reasons[capability_id] = verdict_reason
                        continue
                manifest = domain.object_manifests[capability_id].content
                manifest_required, manifest_optional = _load_set(dict(manifest))
                required.update(manifest_required)
                optional.update(manifest_optional)
                never.update(manifest.get("never_load") or ())

            capability_ids.update(local_capabilities)

            generated_caps = set(route.get("capabilities") or ())
            if not local_capabilities <= generated_caps:
                stale = sorted(local_capabilities - generated_caps)
                raise AuthoringIntegrityError(
                    f"generated registry is stale for {domain_id}:{situation.type}; "
                    f"missing capabilities {stale}")

        if not selected_domains:
            if unresolved:
                raise SituationContextIncomplete(
                    f"situation {situation.id!r} cannot resolve authored routes; missing "
                    f"{sorted(unresolved)}")
            if saw_index_route:
                raise NoExpertiseRoute(
                    f"situation {situation.id!r} matched the type index but no authored "
                    "situation predicate")
            scope = f" in domains {domain_ids}" if hints else ""
            raise NoExpertiseRoute(
                f"no expertise route for situation type {situation.type!r}{scope}")

        required -= never
        optional -= never | required
        if not required:
            raise AuthoringIntegrityError("an expertise route resolved no required objects")
        if not capability_ids:
            # Abstention, not an authoring defect — see UnsupportedCoverage's docstring. The
            # sibling raises below (no required objects, over the capability/object limit) stay
            # AuthoringIntegrityError: those ARE something wrong with the route.
            reasons = sorted(set(skipped_reasons.values()))
            raise UnsupportedCoverage(
                "unreviewed" if reasons and all(r != "stub" for r in reasons) else "all_stub",
                f"no routed capability is admitted: { {c: skipped_reasons.get(c, 'stub') for c in sorted(skipped_capabilities)} }")
        if len(capability_ids) > self.max_capabilities:
            raise AuthoringIntegrityError(
                f"route expands to {len(capability_ids)} capabilities; limit is "
                f"{self.max_capabilities}")
        if len(required | optional) > self.max_objects:
            raise AuthoringIntegrityError(
                f"route expands to {len(required | optional)} objects; limit is "
                f"{self.max_objects}")

        return RoutePlan(
            domain_ids=tuple(sorted(selected_domains)),
            situation_ids=tuple(sorted(situation_ids)),
            capability_ids=tuple(sorted(capability_ids)),
            required_object_ids=tuple(sorted(required)),
            optional_object_ids=tuple(sorted(optional)),
            never_object_ids=tuple(sorted(never)),
            unresolved_predicates=tuple(sorted(unresolved)),
            skipped_capability_ids=tuple(sorted(skipped_capabilities)),
            admitted=not admission_gaps,
            admission_gaps=tuple(sorted(admission_gaps)),
            hollow_capability_ids=tuple(sorted(hollow_capabilities)),
            render=render,
            render_situation_id=render_situation_id,
            priority_bp=priority_bp,
            priority_situation_id=priority_situation_id,
        )


__all__ = ["CapabilityResolver"]
