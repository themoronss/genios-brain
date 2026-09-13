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
)
#: Native apps that are work by construction (bundle id prefixes).
WORK_BUNDLES: tuple[str, ...] = (
    "com.microsoft.Excel", "com.microsoft.Word", "com.microsoft.Powerpoint",
    "com.microsoft.teams", "com.apple.iWork.", "notion.id", "com.linear",
    "com.figma.", "com.hnc.Discord",
)


def _work_host(host: str | None) -> bool:
    h = (host or "").lower().strip(".")
    return bool(h) and any(h == w or h.endswith("." + w) for w in WORK_HOSTS)


def _work_bundle(bundle_id: str | None) -> bool:
    b = (bundle_id or "").strip()
    return bool(b) and any(b.startswith(w) for w in WORK_BUNDLES)


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


class ScreenDocRelevance:
    """RelevanceClassifier for screen objects. `fallback` is the org's ordinary gate or None."""

    name = "relevance-screen-1"

    def __init__(self, fallback=None) -> None:
        self.fallback = fallback

    def _ask(self, ctx: GateContext, prepared: PreparedContent | None) -> RelevanceVerdict:
        v = self.fallback.classify(ctx, prepared)
        disp = v.disposition or ("keep" if v.relevant else "park")
        if disp == "drop":
            return RelevanceVerdict(False, v.relevance, domains=list(v.domains),
                                    reason=f"screen_no_delete:{v.reason or 'junk'}"[:60],
                                    disposition="park")
        return v

    def classify(self, ctx: GateContext, prepared: PreparedContent | None) -> RelevanceVerdict:
        raw = ctx.raw or {}
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


__all__ = ["ScreenDocRelevance", "WORK_BUNDLES", "WORK_HOSTS", "rule_verdict"]
