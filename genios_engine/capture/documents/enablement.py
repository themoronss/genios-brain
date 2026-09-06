"""L1.3.4-U2 · OCR enablement — *disabled must be a decision somebody can read back.*

Doc-03's second fix for U2 is one clause long — **"Enable per-tenant, not globally"** — and the
reason it matters is the deploy fact stated in the same paragraph: the Tesseract binary is not
in the image. That produces two failures that a single global boolean cannot tell apart.

* `enable_ocr=false` — the flag is off. 369 scanned documents park, and the operator side of
  the story is one INFO line at import that says nothing about which tenant lost what.
* `enable_ocr=true`, binary absent — strictly worse. Every scanned attachment now takes the
  OCR branch, `pytesseract` raises `TesseractNotFoundError` on the first one, and the flag that
  was supposed to turn the feature on has turned an empty document into a failed sync.

So availability is resolved from **three** inputs, not one, and the answer carries the reason
it reached: whether the org opted in, whether the fleet default is on, and whether the engine
is actually present on this host. The output is a word an operator can act on — turn it on for
this tenant, turn it on globally, or install the binary — rather than a `None` they have to
read `wiring.py` to interpret.

**Per-tenant without a migration.** The tenant switch is an allowlist of org ids
(`GENIOS_OCR_ENABLED_ORGS`) rather than a settings column, because OCR is a cost and latency
decision about a *deployment* — you turn it on for the design partner whose inbox is full of
scanned POs, and you do it without shipping a schema change to do it. `parse_org_allowlist`
is here, beside the rule that consumes it, so the parsing of that env var is defined once.

PURE — no settings object, no filesystem probe, no engine import. The host probe and the
`Settings` read both happen in `platform/wiring.py` and arrive here as two booleans.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OcrAvailability(str, Enum):
    """Why OCR is on or off for one org, in the words an operator would use to change it."""

    #: On: an engine exists and this org is allowed to use it.
    ENABLED = "enabled"
    #: Off: the fleet default is off and this org is not on the allowlist.
    DISABLED_GLOBALLY = "disabled_globally"
    #: Off: the fleet default is on, and this org was deliberately excluded.
    DISABLED_FOR_TENANT = "disabled_for_tenant"
    #: Off, and NOT by choice: somebody asked for OCR on a host with no engine. This is the
    #: state that used to present itself as a crash mid-sync.
    ENGINE_MISSING = "engine_missing"


@dataclass(frozen=True)
class OcrDecision:
    """Whether to wire an engine, and the sentence explaining it."""

    enabled: bool
    availability: str
    detail: str


def parse_org_allowlist(raw: str | None) -> frozenset[str]:
    """`"org_a, org_b ,"` → `{"org_a", "org_b"}`. Blank entries and whitespace are dropped, so a
    trailing comma in an env var never creates an org id of `""` that matches nothing and looks
    like it should match something."""
    return frozenset(part.strip() for part in (raw or "").split(",") if part.strip())


def resolve_ocr_availability(*, org_id: str | None, global_enabled: bool,
                             allowlist: frozenset[str] = frozenset(),
                             denylist: frozenset[str] = frozenset(),
                             engine_present: bool) -> OcrDecision:
    """Decide whether this org gets an OCR engine, and say why either way.

    Precedence, highest first:

    1. **no engine on the host → `engine_missing`**, whatever the flags say. Asking for a read
       nothing can perform is not enablement, and pretending otherwise is what turns a config
       mistake into a raised exception on the first scanned attachment.
    2. **the org is on the denylist → `disabled_for_tenant`**, even when the fleet default is
       on. A tenant opt-OUT has to beat the fleet default or it is not an opt-out.
    3. **the org is on the allowlist → `enabled`**, even when the fleet default is off. This is
       the per-tenant rollout the doc asks for: one org at a time, no global flip.
    4. otherwise the fleet default decides.
    """
    if not engine_present:
        return OcrDecision(enabled=False, availability=OcrAvailability.ENGINE_MISSING.value,
                           detail="no OCR engine is installed on this host; scanned documents "
                                  "will park as ocr_unavailable until one is")
    if org_id and org_id in denylist:
        return OcrDecision(enabled=False,
                           availability=OcrAvailability.DISABLED_FOR_TENANT.value,
                           detail=f"OCR is disabled for org {org_id} by tenant policy")
    if org_id and org_id in allowlist:
        return OcrDecision(enabled=True, availability=OcrAvailability.ENABLED.value,
                           detail=f"OCR enabled for org {org_id} by allowlist")
    if global_enabled:
        return OcrDecision(enabled=True, availability=OcrAvailability.ENABLED.value,
                           detail="OCR enabled by the fleet default")
    return OcrDecision(enabled=False, availability=OcrAvailability.DISABLED_GLOBALLY.value,
                       detail="OCR is off by the fleet default and this org is not on the "
                              "allowlist; scanned documents will park as ocr_unavailable")
