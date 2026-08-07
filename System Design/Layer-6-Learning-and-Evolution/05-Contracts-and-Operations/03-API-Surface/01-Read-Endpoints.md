# Read endpoints

Under `/v1/learning`, APIs expose overview, filtered objects, current/history brains, knowledge
suggestions, active/expired memories and preview. State reads require `learning.read` and are both
organization-scoped and visibility-scoped.

Public/organization rows are visible to an organization member; participant/private rows require
the resolved viewer principal in `visibility.principals`. SQL applies the ACL predicate and Python
revalidates the full visibility shape. Missing/partial/invalid ACL metadata fails closed and preview
removes its internal visibility field after filtering.

Preview runs analysis/policy projection without persisting a weekly run.
