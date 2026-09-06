from __future__ import annotations

from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.source_registry import descriptor_of

# L1.2.5-U1 · webhook → RawObject dispatch, and NOTHING else.
#
# THE DEFECT THIS FILE CARRIED. It parsed gmail, gcal, notion and gdrive from a hand-written
# if-chain and returned None for everything else. HubSpot is `buildable=True` in the source
# registry and advertises the `crm` capability the sales pack REQUIRES — and every HubSpot
# trigger this endpoint ever received came back "unmapped payload". One whole source's real-time
# lane dropped its traffic silently, with the poll path reading the same deals fine next to it.
#
# TWO STRUCTURAL CHANGES SO IT CANNOT HAPPEN AGAIN.
#
# 1. The alias table is gone. `descriptor_of` (the source registry — the single source of truth)
#    canonicalises "calendar"/"google_calendar"/"drive"/… and says whether a source is buildable
#    at all. A hand-maintained second list of source ids is exactly how gmail/gcal/notion/gdrive
#    got written down here and hubspot did not.
#
# 2. The payload mapping lives in the CONNECTOR, not here — `webhook_objects` on each connector,
#    funnelling into the same `_to_objects` / `_to_raw` the poll path uses. Parity is then
#    structural rather than a promise two code paths make separately: one parser per source, both
#    doors calling it. `tests/capture/test_webhook_parity.py` fails if a buildable Composio source
#    has no parser, and compares the rows the two doors produce field for field.
#
# No intelligence lives here (L1.2's group law): this routes, it never interprets.


@runtime_checkable
class WebhookParser(Protocol):
    """A connector that can map one pushed payload to the objects the poll path would emit."""

    def webhook_objects(self, payload: Mapping[str, Any]) -> tuple[RawObject, ...]: ...


#: source → the connector class that owns its webhook payload mapping. Lazy imports keep this
#: module free of every provider SDK; the class, not a branch written here, is what maps.
_PARSER_IMPORTS: dict[str, tuple[str, str]] = {
    "gmail": ("genios_engine.capture.connectors.composio", "ComposioGmailConnector"),
    "gcal": ("genios_engine.capture.connectors.calendar", "ComposioCalendarConnector"),
    "hubspot": ("genios_engine.capture.connectors.hubspot", "ComposioHubspotConnector"),
    "notion": ("genios_engine.capture.connectors.notion", "ComposioNotionConnector"),
    "gdrive": ("genios_engine.capture.connectors.drive", "ComposioDriveConnector"),
}

#: Sources whose trigger payload is SELF-CONTAINED — mappable with no tenant credentials, so a
#: caller that supplies no `connector_factory` still gets rows. The rest (a Notion page body, a
#: Drive file's bytes, a HubSpot id-only property-change push) must FETCH, and without a factory
#: the honest answer is nothing at all, never a hollow fabricated object.
_CREDENTIAL_FREE: frozenset[str] = frozenset({"gmail", "gcal", "hubspot"})


def _parser_class(source: str) -> type | None:
    entry = _PARSER_IMPORTS.get(source)
    if entry is None:
        return None
    from importlib import import_module
    return getattr(import_module(entry[0]), entry[1])


def _credential_free_parser(source: str) -> WebhookParser | None:
    """A parser built with EMPTY credentials, for the payloads that need none."""
    if source not in _CREDENTIAL_FREE:
        return None
    cls = _parser_class(source)
    return cls(api_key="", user_id="") if cls is not None else None


def canonical_source(source_type: str) -> str | None:
    """The registry's canonical id for a source_type or alias, or None when no connector can be
    built for it — an unbuildable source has no parser by definition."""
    descriptor = descriptor_of((source_type or "").strip().lower())
    if descriptor is None or not descriptor.buildable:
        return None
    return descriptor.source


def can_dispatch(source_type: str) -> bool:
    """Whether a pushed payload for this source can be mapped at all. The webhook route answers
    `unmapped payload` on False, so this predicate decides whether a source has a real-time lane."""
    source = canonical_source(source_type)
    if source is None:
        return False
    cls = _parser_class(source)
    return cls is not None and callable(getattr(cls, "webhook_objects", None))


def webhook_to_raw_objects(source_type: str, payload: Any, *,
                           connector_factory: Callable[[], Any] | None = None,
                           ) -> tuple[RawObject, ...]:
    """Map one pushed trigger payload → the SAME objects a poll of that object would produce.

    Plural because one payload is not one row: a Gmail message with an attachment is an
    `email_message` AND an `email_attachment` on the poll path, and a webhook lane returning only
    the first silently lost every document that arrived in real time.

    Returns () — never a fabricated object — when the source is unknown or unbuildable, the
    payload is not an object, or the record cannot be resolved without credentials the caller did
    not supply.
    """
    source = canonical_source(source_type)
    if source is None or not isinstance(payload, Mapping):
        return ()
    connector = (connector_factory() if connector_factory is not None
                 else _credential_free_parser(source))
    if connector is None:
        return ()
    parse = getattr(connector, "webhook_objects", None)
    if not callable(parse):
        return ()
    return tuple(o for o in parse(payload) if isinstance(o, RawObject))


def webhook_to_raw(source_type: str, data: Any, *,
                   connector_factory: Callable[[], Any] | None = None) -> RawObject | None:
    """The PRIMARY object of a pushed payload (the message/event/record itself), or None.

    A CONVENIENCE over `webhook_to_raw_objects` for a caller that genuinely wants one object —
    an inspection tool, a probe, a test asserting on the message itself. It is NOT the ingest
    form and no ingest path may use it: it drops a message's attachments, and an attachment is
    usually the half carrying the contract. `/webhooks/composio` called this, which is exactly
    how the real-time lane lost every document it was ever pushed (L1.2.5-U1); it now takes the
    plural form, and `tests/capture/test_webhook_parity.py` compares the rows the two doors land.
    """
    objects = webhook_to_raw_objects(source_type, data, connector_factory=connector_factory)
    return objects[0] if objects else None
