"""The S2 gate slot for screen objects (P2 §4 row "relevance", main plan §10.7).

The generic reader reads EVERY app, so most `screen_doc` objects are not work: a news site, a
settings pane, a shopping cart. Rules decide first — they are free and explainable:

  * `alias_hits > 0`     the page names someone or something already in this org's graph;
  * kv + table blocks ≥ 3 a record-shaped page (a CRM deal, an invoice list, an ERP screen);
  * a work host / app    a CRM, doc suite, tracker or accounting tool.

Anything else goes to the org's ordinary junk gate (`make_relevance_classifier`), and a `drop`
from it is downgraded to `park`: screen text is never deleted on a model's judgment (store-don't-
delete) — a park keeps the payload and can be re-adjudicated. With no model configured, an
unmatched doc parks too (recoverable) instead of spending extraction on an unknown page.

FIRST, for any screen object (P8 C9, P9 K3): when the screen-insight model judged this thread in
the last 24 h (`screen_thread_verdicts`), its verdict routes it with NO gate call — memory:true
keeps it; work:false parks it (`insight_personal`); memory:false parks it (`insight_no_memory`).
A P8 verdict with no memory answer keeps work as before.

ONE AI CALL PER SCREEN OBJECT (P9 K3). A screen object used to buy two model calls: this S2 gate
(`relevance_gate`) and S4's business-relevance page (`l1_relevance`, esqe/relevance.py), which
pushed pages PRIME before the gate runs — so even an object the gate then parked, or one a
verdict had already decided, paid for S4's call. `ScreenRelevancePage` wraps S4's page for
screen wirings only: no pre-gate priming, and an object whose keep came from a model (the gate's
call, or the insight model's verdict) is not asked again — S4's deterministic rules still run
first. An object the gate kept by RULE (alias hit, record shape, work host) still gets S4's one
model call. Email and tool doors never see this wrapper.

Chat and email screen objects are conversations the seat is actively reading in a dedicated
reader; they go to the same fallback gate (the email junk gate's "is a human writing?" test is
exactly right for them), with the same drop → park downgrade, and route when no gate exists.
"""
from __future__ import annotations

from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.gate.relevance import RelevanceVerdict
from genios_engine.contracts.prepared_content import PreparedContent

DOC_OBJECT_TYPE = "screen_doc"
STRUCTURED_BLOCKS_MIN = 3

#: Host suffixes of work systems. A suffix match (`x.hubspot.com` ⊂ `hubspot.com`).
WORK_HOSTS: tuple[str, ...] = (
    "salesforce.com", "force.com", "hubspot.com", "pipedrive.com", "zoho.com", "zoho.in",
    "freshworks.com", "freshdesk.com", "freshsales.io", "zendesk.com", "intercom.com",
    "attio.com", "close.com", "apollo.io", "outreach.io", "gong.io", "copper.com",
    "notion.so", "notion.site", "docs.google.com", "drive.google.com", "coda.io",
    "airtable.com", "monday.com", "asana.com", "clickup.com", "linear.app", "atlassian.net",
    "trello.com", "basecamp.com", "github.com", "gitlab.com", "figma.com", "miro.com",
    "quickbooks.intuit.com", "xero.com", "tallysolutions.com", "chargebee.com",
    "docusign.net", "docusign.com", "pandadoc.com", "calendly.com", "office.com",
    "sharepoint.com", "live.com", "dropbox.com", "box.com",
    # Admin domain (SCREEN_INTELLIGENCE_HOW_IT_WORKS §9a). Login/payment pages of these stay
    # blocked by the sensitive path markers; HR tools stay blocked (decision 12 not taken).
    # meetings
    "zoom.us", "meet.google.com", "teams.microsoft.com",
    # contracts & procurement
    "adobesign.com", "echosign.com", "spotdraft.com", "leegality.com", "ariba.com",
    "coupahost.com", "netsuite.com",
    # finance admin & expenses
    "concursolutions.com", "fylehq.com", "expensify.com", "happay.com", "happay.in",
    # requests & service desks
    "freshservice.com", "service-now.com",
    # compliance & governance
    "mca.gov.in", "gst.gov.in", "epfindia.gov.in", "diligent.com",
    # travel (business portals only)
    "mybiz.makemytrip.com", "navan.com", "travelperk.com",
    # facilities & assets
    "snipe-it.io", "assetpanda.com", "typeform.com",
)
#: Native apps that are work by construction (bundle id prefixes).
WORK_BUNDLES: tuple[str, ...] = (
    "com.microsoft.Excel", "com.microsoft.Word", "com.microsoft.Powerpoint",
    "com.microsoft.teams", "com.apple.iWork.", "notion.id", "com.linear",
    "com.figma.", "com.hnc.Discord",
)
#: Windows: the bundle id is the executable name, matched case-insensitively.
WORK_EXES: frozenset[str] = frozenset({
    "excel.exe", "winword.exe", "powerpnt.exe", "ms-teams.exe", "teams.exe", "notion.exe",
    "figma.exe", "linear.exe", "discord.exe", "tally.exe", "tallyprime.exe",
})


def _work_host(host: str | None) -> bool:
    h = (host or "").lower().strip(".")
    return bool(h) and any(h == w or h.endswith("." + w) for w in WORK_HOSTS)


def _work_bundle(bundle_id: str | None) -> bool:
    b = (bundle_id or "").strip()
    if b.lower().endswith(".exe"):
        return b.lower() in WORK_EXES
    return bool(b) and any(b.startswith(w) for w in WORK_BUNDLES)


def _verdict_parts(v) -> tuple[bool | None, bool | None]:
    """A lookup answer → (work, memory). A bare bool is a P8-style work-only verdict."""
    if isinstance(v, bool):
        return v, None
    if isinstance(v, dict):
        w, m = v.get("work"), v.get("memory")
        return (w if isinstance(w, bool) else None), (m if isinstance(m, bool) else None)
    return None, None


def thread_verdict(raw: dict, lookup) -> RelevanceVerdict | None:
    """P8 C9 + P9 K3: the screen-insight model's judgement of this thread in the last 24 h —
    work:false → park `insight_personal`; memory:false → park `insight_no_memory`; memory:true →
    keep `insight_memory`; work with no memory answer (P8 row) → keep `insight_work`. Parked is
    kept and recoverable, never dropped. None → no verdict: the usual gate (one call at most).

    This replaced the P3 rule "WhatsApp + nobody known → park": whether a chat is work is MEANING,
    so the model judges it; rules only remove waste."""
    if lookup is None:
        return None
    work, memory = _verdict_parts(lookup(str(raw.get("thread_key") or "") or None))
    if work is False:
        return RelevanceVerdict(False, 0.30, disposition="park", reason="insight_personal")
    if work is True and memory is False:
        return RelevanceVerdict(False, 0.35, disposition="park", reason="insight_no_memory")
    if work is True and memory is True:
        return RelevanceVerdict(True, 0.85, disposition="keep", reason="insight_memory")
    if work is True:
        return RelevanceVerdict(True, 0.85, disposition="keep", reason="insight_work")
    return None


def rule_verdict(raw: dict) -> RelevanceVerdict | None:
    """The deterministic half, for a `screen_doc`: a keep verdict or None (undecided)."""
    if int(raw.get("alias_hits") or 0) > 0:
        return RelevanceVerdict(True, 0.90, disposition="keep", reason="alias_hit")
    stats = raw.get("block_stats") or {}
    if int(stats.get("kv") or 0) + int(stats.get("table") or 0) >= STRUCTURED_BLOCKS_MIN:
        return RelevanceVerdict(True, 0.80, disposition="keep", reason="record_shaped")
    if _work_host(raw.get("host")) or _work_bundle(raw.get("bundle_id")):
        return RelevanceVerdict(True, 0.75, disposition="keep", reason="work_host")
    return None


#: Fallback-gate reasons that mean NO model judged the object (the gate's own shortcuts and its
#: fail-open). S4 may still spend its one call on those.
_NOT_MODEL_JUDGED = frozenset({"known_sender", "empty_pass", "gate_llm_unavailable"})


class ScreenDocRelevance:
    """RelevanceClassifier for screen objects. `fallback` is the org's ordinary gate or None;
    `verdicts` is `thread_key -> {"work", "memory"} | bool | None` (followups.verdict_lookup) or
    None. `model_judged` collects the source object ids a MODEL kept (a verdict, or the fallback's
    LLM call) — `ScreenRelevancePage` reads it so S4 does not ask a model a second time."""

    name = "relevance-screen-1"

    def __init__(self, fallback=None, verdicts=None) -> None:
        self.fallback = fallback
        self.verdicts = verdicts
        self.model_judged: set[str] = set()

    def _judged(self, ctx: GateContext) -> None:
        oid = getattr(getattr(ctx, "event", None), "source_object_id", None)
        if oid:
            self.model_judged.add(str(oid))

    def _ask(self, ctx: GateContext, prepared: PreparedContent | None) -> RelevanceVerdict:
        v = self.fallback.classify(ctx, prepared)
        if getattr(self.fallback, "name", "") == "relevance-llm-1" and \
                (v.reason or "") not in _NOT_MODEL_JUDGED:
            self._judged(ctx)
        disp = v.disposition or ("keep" if v.relevant else "park")
        if disp == "drop":
            return RelevanceVerdict(False, v.relevance, domains=list(v.domains),
                                    reason=f"screen_no_delete:{v.reason or 'junk'}"[:60],
                                    disposition="park")
        return v

    def classify(self, ctx: GateContext, prepared: PreparedContent | None) -> RelevanceVerdict:
        raw = ctx.raw or {}
        judged = thread_verdict(raw, self.verdicts)
        if judged is not None:
            self._judged(ctx)
            return judged
        if ctx.event.object_type == DOC_OBJECT_TYPE:
            ruled = rule_verdict(raw)
            if ruled is not None:
                return ruled
            if self.fallback is None:
                return RelevanceVerdict(False, 0.40, disposition="park",
                                        reason="no_work_signal")
            return self._ask(ctx, prepared)
        if self.fallback is None:
            return RelevanceVerdict(True, 0.60, disposition="keep", reason="screen_thread")
        return self._ask(ctx, prepared)


class ScreenRelevancePage:
    """S4's relevance page (`esqe.relevance.RelevancePage`) for a SCREEN wiring (K3).

    `prime` does nothing: pushed pages are primed BEFORE the S2 gate, so priming would buy a model
    call for objects the gate then parks or a verdict already decided. `decide` runs S4's own
    deterministic rules first (unchanged); for the ambiguous remainder, an object a model already
    kept at S2 (`gate.model_judged`) is business-relevant by that model's answer — no second call;
    anything else goes to the real page, which may make its one call."""

    def __init__(self, inner, gate: ScreenDocRelevance) -> None:
        self.inner = inner
        self.gate = gate
        self.trusted = 0

    def prime(self, candidates, *, claims_unknown: bool = True):
        return self.inner.stats

    def decide(self, candidate):
        from genios_engine.capture.esqe import relevance as E
        key = getattr(candidate, "page_key", None)
        if key and key in self.gate.model_judged:
            ruled = E._rule_verdict(candidate)
            if ruled is not None:
                return E._decide(candidate.event_id, ruled[0], ruled[1], E.DECIDED_BY_RULES)
            self.trusted += 1
            return E._decide(candidate.event_id, True, E.RULE_LLM_BUSINESS, E.DECIDED_BY_LLM,
                             "kept by the screen gate's one model call (verdict or gate)")
        return self.inner.decide(candidate)

    @property
    def stats(self):
        return self.inner.stats

    def __getattr__(self, name):
        return getattr(self.inner, name)


def screen_semantic_lane(semantic, gate: ScreenDocRelevance):
    """The org's semantic lane with its S4 page wrapped for screen objects (None stays None)."""
    page = getattr(semantic, "relevance_page", None)
    if semantic is None or page is None:
        return semantic
    from dataclasses import replace
    return replace(semantic, relevance_page=ScreenRelevancePage(page, gate))


__all__ = ["ScreenDocRelevance", "ScreenRelevancePage", "WORK_BUNDLES", "WORK_EXES", "WORK_HOSTS",
           "rule_verdict", "screen_semantic_lane", "thread_verdict"]
