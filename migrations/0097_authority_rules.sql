-- L2.1.4-U1 · `authority_rules` — *"Arjun approves contracts > $50K"* as DATA, not as an `if`.
--
-- WHY A TABLE AND NOT A CONSTANT. A grep of `context/` for approval thresholds returns nothing,
-- and two Layer 4 units cannot fire without them: the Policy unit ("which organisational rules
-- bind") has no rules to read, and the Constraint unit ("what cannot happen") has no thresholds
-- to check. Globe's Founder Bottleneck surface — the one it rates highest for "I can't unsee
-- this" value — is one query against this table and nothing else: *this person is the only
-- approver for N classes, with no delegate.*
--
-- `valid_from` IS PART OF THE PRIMARY KEY, and that is the whole design. "Who could approve this
-- in March?" has to be answerable, because a decision made in March was correct against March's
-- rules; re-judging it against today's is how a review turns into an accusation. A rule is never
-- updated in place — it is CLOSED (`valid_until`) and a successor row is inserted with a later
-- `valid_from`, so the March answer survives the September edit. The half-open window
-- `[valid_from, valid_until)` is enforced by `contracts/authority.AuthorityRule.applies_at`; the
-- check constraint here is the same law at the column level, because a row that ends before it
-- starts matches no instant and the rule then silently stops existing while still being listed.
--
-- `source` RANKS, AND ONE OF THE THREE MAY NEVER BIND. admin_declared (a human set it) beats
-- discovered (read out of an uploaded policy document) beats inferred (observed behaviour: this
-- person approved N of N requests in this class over 90 days). The weights live in
-- `context/authority_view.SOURCE_AUTHORITY_BP`; what the schema carries is the part that is not
-- tunable — an INFERRED rule is a SUGGESTION. Inferring an approval threshold from behaviour and
-- then enforcing it would let the system invent governance. It proposes; a human confirms, which
-- is an insert of an `admin_declared` row, not an edit of the inferred one.
--
-- `threshold_minor_units` IS BIGINT AND ITS CURRENCY IS REQUIRED WITH IT. A threshold is money,
-- and money here is integer minor units for the reason `contracts/units.Money` gives: a float
-- rounds, and this particular rounding decides who has to sign. A 5-crore threshold in paise
-- overflows a 32-bit int at a value a tenant would actually type. A NULL threshold is a real and
-- common case (a hiring approval has no amount) and means "applies at any value" — which is why
-- it is nullable rather than defaulted to zero, and why the check constraint pairs it with the
-- currency in both directions.
--
-- ABSENCE IS NOT PERMISSION. There is deliberately no "default approver" row and no wildcard
-- subject_type. An unmatched class returns `no_authority_rule` from the view, which is a
-- different fact from "anyone may approve" and renders differently on every card that asks.
--
-- ORG CASCADE. `tests/test_account_erasure.py` replays every migration and fails any table
-- carrying an `org_id` that cannot be erased with its tenant. The rule names an approver by
-- graph node id and often quotes the policy document it came from, so this is a record about the
-- tenant's own people. The table is also named in `api/account_routes._ORG_SCOPED_TABLES`, which
-- is what makes /reset erase it as well as account deletion; that loop runs with no try/except,
-- so a name missing from it leaks silently.
--
-- NO FK ON `approver_node_id` / `delegate_node_id`: `graph_nodes` is versioned and its primary
-- key is `(node_id, version)`, so there is no single column to reference — the same reason
-- migration 0094 gives for `metric_history.subject_node_id`.

create table if not exists authority_rules (
    org_id                text        not null references orgs (id) on delete cascade,
    rule_id               text        not null,
    subject_type          text        not null,   -- contract | expense | hiring | legal | discount
    threshold_minor_units bigint,                 -- null = applies at any value
    currency              text,                   -- required whenever a threshold is set
    approver_node_id      text        not null,   -- a graph node id, so the bottleneck query groups on it
    delegate_node_id      text,                   -- who may act in their absence; usually null, and that is the finding
    source                text        not null,   -- admin_declared | discovered | inferred
    evidence_ref          text,                   -- the document or setting it came from
    valid_from            timestamptz not null,
    valid_until           timestamptz,
    created_at            timestamptz not null default now(),
    primary key (org_id, rule_id, valid_from),
    constraint authority_rules_window check (valid_until is null or valid_until > valid_from),
    constraint authority_rules_threshold_currency check (
        (threshold_minor_units is null and currency is null)
        or (threshold_minor_units is not null and currency is not null)),
    constraint authority_rules_source check (source in ('admin_declared', 'discovered', 'inferred'))
);

-- The view's only two reads: "every rule for this class in force at T" and, for the bottleneck,
-- "every rule in force at T". `subject_type` leads because the resolve path always names one and
-- the bottleneck path scans an org that has tens of rules, not millions.
create index if not exists authority_rules_by_class
    on authority_rules (org_id, subject_type, valid_from desc);
create index if not exists authority_rules_by_approver
    on authority_rules (org_id, approver_node_id);
