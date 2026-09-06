"""L2.7.7 · speaker authority — *who says a thing is finished decides how much that is worth.*

Doc 07's table has four rows and only three of them are weights:

    the obligation's OWNER          full weight        10000 bp
    org-internal, not the owner     0.8                 8000 bp
    EXTERNAL COUNTERPARTY           0.6                 6000 bp   — a claim, not a fact
    automated / service account     IGNORED ENTIRELY    (never weighed; refused at the gate)

THE MACHINE TEST RUNS FIRST AND NOTHING OVERRIDES IT. `no-reply@ourcompany.com` is
same-domain, so a cascade that asked "is this us?" before "is this a robot?" would hand an
autoresponder INTERNAL authority — 8000 bp — and doc 12 case 7 is precisely a bot closing a real
situation with *"Your ticket has been resolved"*. `capture/esqe/source_analyzer` had to lift the
same rung above the same two domain tests for the same reason; this module states the order
explicitly rather than relying on it falling out of an `if` chain.

THE ROBOT TABLE IS IMPORTED, NOT REWRITTEN. `capture/gate/rules.is_automated_sender` is the ONE
machine-sender table in this codebase, and its own docstring says why: three regexes drift into
three different answers about `notify@stripe.com`. Doc 12's cross-cutting rule 5 says the same
thing about ALG-08. A second table here would be a second answer.

AUTHORITY IS PER OBLIGATION, AND A MIXED SCOPE TAKES THE WEAKEST. A message that claims to
finish two things can be the owner of one and a bystander to the other; scoring it at the
stronger of the two would let ownership of a trivial obligation carry a close of the one that
matters. `role_for_scope` therefore returns the weakest role the speaker holds across everything
the claim names — the same direction every other threshold in this unit leans.

NO CLOCK, NO MODEL, NO DATABASE. Authority does not age and it is not a reading of the prose:
the model's own guess at the speaker's role is recorded on the description and never consulted
here. It is derived from an address we hold and a set of addresses the drain already computed.
"""
from __future__ import annotations

from collections.abc import Iterable

from genios_engine.capture.gate.rules import is_automated_sender
from genios_engine.context.lifecycle.contract import (
    AUTHORITY_BP,
    ROLE_EXTERNAL,
    ROLE_INTERNAL,
    ROLE_MACHINE,
    ROLE_OWNER,
    Obligation,
)

__all__ = ["authority_bp", "is_ignored_speaker", "normalize_email", "role_for_obligation",
           "role_for_scope"]


def normalize_email(value: str | None) -> str:
    """Lower-cased and stripped, or empty. The one normalisation every comparison here uses —
    `Rohit@Acme.com` and `rohit@acme.com` are the same person and a set membership test that
    said otherwise would silently demote an owner to a counterparty."""
    return str(value or "").strip().lower()


def role_for_obligation(sender_email: str | None, obligation: Obligation | None, *,
                        internal_emails: Iterable[str] = ()) -> str | None:
    """The speaker's standing on ONE obligation, or None when we cannot say who spoke.

    `None` is not a fifth role and it is not `EXTERNAL`: an unattributable statement is one we
    have no basis to weigh at all, and the caller refuses it rather than assigning it the
    weakest weight — 6000 bp of authority for "we do not know who wrote this" is an invention.
    """
    sender = normalize_email(sender_email)
    if not sender:
        return None
    # FIRST, and not overridable. See the module docstring.
    if is_automated_sender(sender):
        return ROLE_MACHINE
    if obligation is not None and normalize_email(obligation.owner_email) == sender:
        return ROLE_OWNER
    if sender in {normalize_email(e) for e in internal_emails}:
        return ROLE_INTERNAL
    return ROLE_EXTERNAL


def role_for_scope(sender_email: str | None, obligations: Iterable[Obligation], *,
                   internal_emails: Iterable[str] = ()) -> str | None:
    """The WEAKEST standing the speaker holds across every obligation the claim names.

    An empty scope means the claim is about the situation as a whole (a deal, a renewal — a
    subject with no per-obligation owner recorded), and then the speaker is weighed as owner of
    nothing: internal or external, never OWNER. That is the honest reading — nobody was recorded
    as owning the thing — and it is also the safe one, because OWNER is the only rank that can
    close on its own.
    """
    scoped = list(obligations)
    if not scoped:
        role = role_for_obligation(sender_email, None, internal_emails=internal_emails)
        return role
    roles = [role_for_obligation(sender_email, ob, internal_emails=internal_emails)
             for ob in scoped]
    if any(r is None for r in roles):
        return None
    if ROLE_MACHINE in roles:
        return ROLE_MACHINE
    return min(roles, key=lambda r: AUTHORITY_BP[r])


def is_ignored_speaker(role: str | None) -> bool:
    """Whether this speaker is ignored ENTIRELY — doc 07's fourth row, and the unknown sender.

    Both are refused BEFORE the model call, not after it: doc 12 case 7 says service accounts are
    *"ignored at the gate, before any call"*, which is a cost control as much as a correctness one.
    """
    return role is None or role == ROLE_MACHINE


def authority_bp(role: str) -> int:
    """The weight, in basis points. Raises on a role that has none, because the alternative — a
    default — is how `machine` would quietly acquire one."""
    try:
        return AUTHORITY_BP[role]
    except KeyError:                                  # noqa: TRY003 — the message IS the contract
        raise ValueError(
            f"{role!r} carries no authority weight; `is_ignored_speaker` decides that case "
            "before anything asks for a number") from None
