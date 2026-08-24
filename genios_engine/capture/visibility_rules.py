"""Layer 1's answer to "who could see the original?" — derived per source, at capture.

`contracts/visibility.py` was fully implemented, unit-tested, and called by NOTHING on the
capture path — `grep -rn visibility genios_engine/capture/` returned zero matches, and
`source_events` had no column for it. So every captured event was org-scoped from landing, a
fact extracted from a two-person email thread was indistinguishable from one extracted from a
company-wide Notion page, and the passing contract test was itself the hazard: it made the
layer look protected.

The rule (from the contract's own module docstring): **the audience of a derived insight can
never be wider than the audience of the evidence it came from.** Layer 1 is the only layer that
still knows the answer — by Layer 2 the email is a fact and the recipient list is gone — so the
answer is stamped here, once, per source family, and honoured everywhere above.

Every rule returns a NAMED derivation (`derived_from`), so a wrong audience traces to the rule
that mapped it rather than being an unexplained fact. A source no rule covers returns None, and
the gate PARKS the event as `visibility_unknown` rather than publishing — an audience we cannot
name is not an audience we may assume.
"""
from __future__ import annotations

from genios_engine.capture.source_registry import descriptor_of, family_of
from genios_engine.contracts.visibility import ORG, PARTICIPANTS, Visibility


def _people(*groups) -> list[str]:
    """Lowercased, deduped, order-stable union of every address handed in."""
    seen: dict[str, None] = {}
    for group in groups:
        for item in group or ():
            addr = str(item or "").strip().lower()
            if addr and "@" in addr:
                seen.setdefault(addr, None)
    return list(seen)


def derive_visibility(*, source: str, actor_email: str | None,
                      recipients: tuple[str, ...] | list[str] | None,
                      internal_kind: str | None = None,
                      mailbox_owner: str | None = None) -> Visibility | None:
    """The source's own ACL, normalised to the four scopes. None = no rule -> the gate parks.

    Communication (mail, chat, meetings, calendar)
        The ACL IS the participant list: sender + To/Cc (or organizer + attendees), plus the
        mailbox owner — who could see it by definition, it is their mailbox. An empty recipient
        list does NOT make the audience unknown: a BCC-only or self-noted message is visible to
        the sender and the owner, which is a valid (small) participants set, not an absence.

    Deliberate intake (uploads, human notes, internal canon)
        A person in the org handed this to the org's own system on purpose — org scope, and
        `internal_kind` canon doubly so.

    Enterprise systems (CRM, billing, support desk, client DB)
        A system of record any seat can open — org scope by the system's own model.

    Knowledge (Notion, Drive, Confluence)
        Org scope as a NAMED assumption (`connector:workspace_default`), not a fact: the
        connectors do not fetch per-file ACLs yet. When they do, this rule narrows; until then
        the assumption is recorded where an audit can find it instead of being silence.

    Operational / external / intelligence
        Org — work systems and public material carry no personal audience.

    Anything else — a family the registry does not know — returns None. Unknown provenance gets
    parked, never published under a guessed audience.
    """
    family = family_of(source)
    if internal_kind:
        return Visibility(scope=ORG, derived_from=f"internal_kind:{internal_kind}")
    # Deliberate intake beats family: `upload` files under the knowledge family but a person in
    # the org handed it to the org's own system on purpose, which is an org-scope statement in a
    # way a synced workspace page is not.
    descriptor = descriptor_of(source)
    if descriptor is not None and descriptor.deliberate:
        return Visibility(scope=ORG, derived_from=f"deliberate:{source}")
    if family == "communication":
        principals = _people([actor_email], recipients, [mailbox_owner])
        return Visibility(scope=PARTICIPANTS, principals=principals,
                          derived_from=f"connector:{source}:participants")
    if family in ("human_input", "ai_generated", "internal"):
        return Visibility(scope=ORG, derived_from=f"deliberate:{source}")
    if family == "enterprise_system":
        return Visibility(scope=ORG, derived_from=f"system_of_record:{source}")
    if family == "knowledge":
        # A named assumption, deliberately distinguishable from a measured ACL.
        return Visibility(scope=ORG, derived_from="connector:workspace_default")
    if family in ("operational", "external", "live_event", "intelligence"):
        return Visibility(scope=ORG, derived_from=f"family:{family}")
    return None


__all__ = ["derive_visibility"]
