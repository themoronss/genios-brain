"""Who was allowed to see the original — carried forward from the source.

The architecture makes this Layer 1's job: *"carries source-level ACLs forward so a
signal can never surface to someone who could not see the original."* Until this module
existed nothing in the engine recorded it, so a fact extracted from a two-person email
thread was indistinguishable from one extracted from a company-wide Notion page, and
every layer above was free to deliver either to anyone in the org.

The rule this encodes: **the audience of a derived insight can never be wider than the
audience of the evidence it came from.** Layer 1 is the only layer that still knows the
answer — by Layer 2 the email is a fact and the recipient list is gone — so the answer is
stamped here, once, and honoured everywhere above.

Deliberately NOT a permission system. It records what the source said, in four scopes;
enforcement (who is a member of an org, who is an admin) belongs to `platform/auth.py`.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

# Ordered widest → narrowest. `narrowest()` relies on this order.
SCOPES: tuple[str, ...] = ("public", "org", "participants", "private")

PUBLIC = "public"              # the open world saw it (a published page, a filing)
ORG = "org"                    # anyone in the tenant could have opened it
PARTICIPANTS = "participants"  # only the named people (an email thread, a meeting)
PRIVATE = "private"            # one owner, nobody else


class Visibility(BaseModel):
    """The source's own answer to "who could see this?", normalised to four scopes.

    `principals` is a list of lowercased email addresses and is meaningful only for
    `participants` / `private`. `derived_from` records HOW we knew, so a wrong audience
    is traceable to the connector that mapped it rather than being an unexplained fact.

    `excluded_subjects` is orthogonal to `scope`/`principals`: it is a hard denylist for people
    the insight is ABOUT, not a narrower audience. Scope answers "how wide may this go";
    exclusion answers "regardless of that, who must never see it" — needed when the correct
    audience is neither wider nor narrower than the evidence's participants but *disjoint* from
    them (e.g. an internal analyst reviewing a pattern derived from three people's own work: the
    analyst should see it, none of the three ever should, even though normal `participants` scope
    would otherwise qualify them). A person can be excluded from a `public` or `org` scoped
    insight just as much as a `participants` one.
    """

    scope: str = ORG
    principals: list[str] = Field(default_factory=list)
    derived_from: str = "default:org"
    excluded_subjects: list[str] = Field(default_factory=list)

    def model_post_init(self, _ctx: object) -> None:
        if self.scope not in SCOPES:
            raise ValueError(f"unknown visibility scope {self.scope!r}; expected {SCOPES}")

    def can_view(self, viewer_email: str | None, *, org_member: bool = True) -> bool:
        """Is this viewer allowed to see anything derived from this evidence?

        `org_member` is the caller's assertion that the viewer belongs to the tenant —
        the tenant boundary itself is enforced upstream by `org_id`, never here. Exclusion is
        checked first and overrides every scope, including `public`.
        """
        if viewer_email and viewer_email.strip().lower() in self._excluded_set():
            return False
        if self.scope == PUBLIC:
            return True
        if self.scope == ORG:
            return org_member
        if not viewer_email:
            return False
        return viewer_email.strip().lower() in self.principals

    def _excluded_set(self) -> set[str]:
        return {e.strip().lower() for e in self.excluded_subjects}


def narrowest(*visibilities: Visibility | None) -> Visibility:
    """Combine the visibility of several pieces of evidence into one.

    A situation built from a company-wide page AND a private thread is as sensitive as
    the private thread — so the result takes the NARROWEST scope, and its principals are
    the INTERSECTION of the constrained ones. Widening here would be the leak this whole
    module exists to prevent, so the merge can only ever narrow.

    `excluded_subjects` merges the OTHER way — by UNION, never intersection. If evidence A says
    "never show this to X" and evidence B carries no exclusion at all, the merged insight still
    must never reach X: a merge cannot launder away an exclusion any easier than it can widen a
    scope.
    """
    present = [v for v in visibilities if v is not None]
    if not present:
        return Visibility()
    excluded: set[str] = set()
    for v in present:
        excluded |= v._excluded_set()  # noqa: SLF001 — same-module helper, not a public API
    scope = max(present, key=lambda v: SCOPES.index(v.scope)).scope
    if scope in (PUBLIC, ORG):
        return Visibility(scope=scope, derived_from="merged", excluded_subjects=sorted(excluded))
    constrained = [set(v.principals) for v in present if v.scope in (PARTICIPANTS, PRIVATE)]
    common: set[str] = set.intersection(*constrained) if constrained else set()
    return Visibility(scope=scope, principals=sorted(common), derived_from="merged",
                      excluded_subjects=sorted(excluded))
