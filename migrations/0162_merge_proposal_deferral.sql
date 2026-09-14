-- L2 · `merge_proposals.deferred_until` — "ask me again later" becomes a fact instead of a reply.
--
-- THE QUEUE WAS UNWORKABLE, IN THREE WAYS THAT COMPOUND. `identity` proposes and a human decides;
-- that is the design and it is right. But the surface a human decides through had no way to get
-- through a backlog:
--
--   1. `POST /v1/merge/{org}/queue/{id}/defer` DID NOTHING AND REPORTED SUCCESS. Its own comment
--      said so — "No deferred state in the identity model — the proposal simply stays open for
--      later" — it loaded the row, wrote nothing, and returned `{"status": "deferred"}`. A
--      reviewer deferred the ambiguous ones, reloaded, and got the identical list back.
--
--   2. `open_proposals` ordered `created_at DESC` — NEWEST FIRST — and the route's default limit
--      is 20. On the pilot's 80 open proposals the sixty oldest were unreachable through the UI
--      at all, and the twenty visible were the twenty most recently created, which are the least
--      likely to be stuck.
--
--   3. Nothing ranked by how strong the collision was, though the ledger has always known: a
--      shared email, domain or LinkedIn url IS a duplicate (`identity._STRONG`), while a shared
--      company name is a coincidence of spelling. A real duplicate sat behind sixty coincidences.
--
-- Together those explain "eighty proposals accumulated" far better than anybody's inattention.
--
-- WHAT DEFERRAL IS NOT. It does not resolve the doubt, so a deferred proposal still counts in
-- `situations.merge_pressure` and still costs the situation its identity confidence. Choosing not
-- to decide today is not deciding — the only two decisions are `merged` and `rejected`, and both
-- already exist. This column says "not in this pass", nothing more.
--
-- NULL MEANS NEVER DEFERRED, and the column is read as `deferred_until > now()`, so a lapsed
-- deferral returns to the queue by itself. No sweep, no cleanup job, no second state to keep
-- consistent with the first.

alter table merge_proposals add column if not exists deferred_until timestamptz;

-- The queue read asks for one org's undeferred open proposals, oldest first within strength.
-- Partial on `open` because decided proposals are the majority of the table on any tenant that
-- has ever worked the queue, and they can never appear in it again.
create index if not exists merge_proposals_queue
    on merge_proposals (org_id, created_at)
    where status = 'open';
