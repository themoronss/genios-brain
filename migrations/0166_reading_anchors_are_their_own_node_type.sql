-- L2 · a reading's own anchor stops sharing a node type with the graph's real subjects.
--
-- WHAT WAS WRONG. `refresh_state_situations` mints one node per finding and passed the ANCHOR NAME
-- straight through as `graph_nodes.node_type`. For four of the six anchors that is harmless —
-- nothing else in the system mints an `outreach` or a `cohort`. For two it made one string mean two
-- different things, and both failed, in opposite directions.
--
--   `commitment` FAILED CLOSED. `_WAITING_ROWS` excludes this node type so a reading cannot read
--   back the facts it projected onto its own anchor — without it one real promise became fifteen
--   identical cards and kept doubling every sweep. But the PIPELINE mints a genuine promise under
--   the same type, so the exclusion took those with it. `_COMMITMENT_OWNERS` joins on a commitment
--   node id, `_WAITING_ROWS` could never return one, and `_owner_name` / `_owner_key` were
--   therefore ALWAYS NULL — the owner filter in `read_overdue_commitments`, written for "six of
--   fifteen cards were somebody else's promise rendered as the founder's", never fired once. The
--   card still appeared, through the weaker path only: the extractor may emit `commitment.due_at`
--   as a plain fact candidate on a PERSON node, and those do reach the reading — with no owner, no
--   status and no normalised action.
--
--   `meeting` FAILED OPEN — the same defect pointing the other way. The meeting reading's anchors
--   are not excluded at all, and nothing goes wrong today only because `_WAITING_ROWS` filters on
--   a field allow-list that happens to contain no `meeting.*` name. That is precisely the accident
--   the query's own comment says `outreach` escaped by, and it holds until somebody adds a field.
--
-- WHY A MIGRATION IS REQUIRED AND NOT OPTIONAL. `GraphStore.find_or_create_node` resolves an
-- existing node by `(org_id, canonical_key)` ALONE and never rewrites `node_type`. So changing the
-- minting site affects nodes that do not exist yet and NOTHING already in the table: every anchor a
-- tenant already carries would keep `node_type = 'commitment'`, and the relaxed exclusion would
-- then let those back into the reading — reviving the doubling bug on exactly the rows a fresh
-- test database does not have. The failure would be invisible in CI and total in production.
--
-- HOW THE TWO ARE TOLD APART. Their canonical keys have different shapes and always have:
--
--   reading anchor   'commitment:' || <node id>   and a node id is `new_id("node")` -> node_<24 hex>
--   pipeline promise 'commitment:' || <sha1[:20]> -- no prefix, 20 hex characters
--
-- so the `node\_` infix is the discriminator, and it is a property of the writers rather than a
-- convention either side could drift from. `meeting` is the same shape ('meeting:' || <node id>)
-- against a calendar event whose canonical key is the provider's own event id.
--
-- REVERSIBLE BY INSPECTION: every row this touches is identifiable afterwards by the same
-- predicate with the prefix attached, and no other column is written.

update graph_nodes
   set node_type = 'reading:commitment'
 where node_type = 'commitment'
   and canonical_key like 'commitment:node!_%' escape '!';

update graph_nodes
   set node_type = 'reading:meeting'
 where node_type = 'meeting'
   and canonical_key like 'meeting:node!_%' escape '!';

-- The reading resolves its anchors by canonical_key on every sweep, so no index on the new type is
-- needed. `graph_nodes_by_org (org_id, node_type)` already exists for readers that scan by type.
