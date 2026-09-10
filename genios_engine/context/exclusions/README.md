# Declared impossibilities

One YAML file per pair of situation types that cannot both be true of one subject.
`context/correlation_domain.py` loads every `*.yaml` here in filename order.

**Adding one is authoring, not coding.** Write a file; no Python changes.

```yaml
id: <stable slug, filename-ish>
left:  <domain>:<situation_type>
right: <domain>:<situation_type>
because: >-
  One sentence a reviewer can disagree with. This is the whole justification for
  suppressing a domain's work, so it is required.
arbiter: <fact path>        # optional — the fact that settles it
favours:                    # required when `arbiter` is set
  <fact value>: <the side it favours>
```

## What belongs here, and what does not

Only a genuine **impossibility**. Overlap is normal and is not a finding: on the pilot
`nsrcel.iimb.ac.in` is an investor relationship, a general relationship and a sales
opportunity at once, and all three are true. If two readings can both hold, they are not
an exclusion.

There is deliberately no similarity score and no threshold. A statistical "these two look
like they clash" would fire on the harmless overlaps above and would be undebuggable from a
stored number.

## The arbiter

Prefer a fact **both** readings are derived from. `thread.ball_in_court` qualifies: the two
situations in `whose-turn-is-it.yaml` are two readings of it that drifted apart, so asking it
is asking the shared source rather than inventing a precedence.

A pair with no arbiter is legal and useful — the contradiction is still detected, and both
sides hold. Refusing to declare those would leave the contradiction undetected, which is
strictly worse.

`favours` may only name a side of its own pair; a value pointing at a third type would make
every finding silently unresolved, and `tests/context/test_cross_domain.py` fails on it.
