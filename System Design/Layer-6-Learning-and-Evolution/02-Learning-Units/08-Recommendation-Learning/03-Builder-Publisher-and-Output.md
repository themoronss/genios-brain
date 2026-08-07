# Builder, Publisher and Output

The builder emits unit `recommendation_learning`, target `adaptive`, subject
`recommendation:<capability>:<play>:audience:<acl-hash>` and the parent outcome proposal ID in
metadata. Source refs, independent refs, traces, ACL and seen window remain exact.

After governance/review, the shared publisher creates a versioned Adaptive Brain entry and
supersedes a prior material value under lock. It never edits a playbook or changes Layer 4/5 routing
directly.

**Integration note:** a recommendation selector must explicitly consume these entries, define
fallbacks and enforce visibility. Until that reader is wired, the proposal remains durable and
inspectable but does not silently change runtime choices.
