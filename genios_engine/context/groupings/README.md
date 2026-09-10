# Groupings — "for my business, these people are one party"

One file per grouping. Adding one is a file and a review, not a Python edit and a deploy.

The shape is proven next door: `context/exclusions/` uses the same sorted-glob loader, the same
per-file validation, and the same rule that a malformed file names itself in the error.

## Shape

```yaml
grouping_id: department        # unique; the key a reading names
edge_type: works_in            # the graph edge that joins a member to its group
member_node_type: person       # what is being grouped
group_node_type: department    # what they are grouped INTO
min_members: 3                 # below this, the per-member card already says everything
why: >
  One sentence a reviewer can argue with.
```

## Why this is not a threshold in Python

`find_organizations` hardcoded `works_at` / `person` / `company`. That is one business's version
of a true statement. A hospital groups clinicians by **department**, a school groups guardians by
**household**, a broker groups traders by **desk**, a consultancy groups people by the
**engagement** they are staffed on rather than by who employs them. Every one of those is the
same reading — *more than one person on the other side has gone quiet* — over a different edge.

## What a grouping may NOT do

Membership is not applicability. Two people sharing a group node means they are the same
counterparty **for the purpose of chasing a reply**. It says nothing about whether an agreement
with one binds the other, whether a parent's terms reach a subsidiary, or whether anything signed
by one is answerable by the other. `organization-gone-quiet.yaml` states that limit on the card,
and it holds for every grouping declared here.

Nor can it invent a relationship label. `organization.relationship` is written only when every
member carries a role and the roles AGREE, and is absent otherwise — three-valued, because "we do
not know what they are to us" is not "they are one thing to us". That rule is in the reading and
no grouping file can turn it off.
