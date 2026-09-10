# Anchor tiers — what a situation is allowed to be ABOUT

One file per node type. Adding a kind of thing a situation can be about is a file and a review,
not a Python edit and a deploy.

## Why this is data

`_anchor_priority()` returned a Python tuple, and its own comment records what that cost:

> subscription / product_account are system-of-record business objects (like a deal) … Without
> them here, `choose_anchors` returns [] for every Stripe/client-DB structured event → it reaches
> NO situation, and admin/account situations report their fields missing forever — the "built,
> green, does nothing" dead-end.

That is the whole argument. A business object the tuple has not heard of does not merely rank
low — it anchors NOTHING, and every situation about it is invisible with no error anywhere. A
clinic's `episode`, a firm's `matter`, an exporter's `shipment` and a school's `enrolment` are
each one line of YAML away from working and were each a deploy away before.

## Shape

```yaml
node_type: matter        # the graph node type this tier is about
rank: 15                 # lower anchors first; see the ranking note below
why: >
  A legal matter is the business object a firm's work is about — the client outlives it and
  the people rotate through it.
```

`rank` is an integer rather than list position for the reason `capture/domain/hints.py` states
about the same change: an ordering carried by the insertion order of a Python literal is
invisible to an author and lost by any reordering.

## Ranking

Lower anchors first. The shipped ranks:

| rank | node type | why it sits there |
|---:|---|---|
| 10 | `deal` | the business object itself |
| 20 | canon anchoring kinds (`project`, …) | named work in flight — more specific than the company it belongs to |
| 30 | `subscription`, `product_account` | systems of record, like a deal |
| 40 | `company` | outlives its people |
| 50 | `person` | the last resort |

An authored tier competes on its number. Ties break on node type name, so two files that pick
the same rank order deterministically rather than by whichever the filesystem listed first.

## What a tier may NOT do

It cannot make a node type anchor a situation that has no evidence — `choose_anchors` still
requires the node to exist and to carry the event. Declaring `matter` does not conjure matters;
it stops one being ignored when it is there.
