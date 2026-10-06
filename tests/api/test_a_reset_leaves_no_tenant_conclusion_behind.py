"""Every org-scoped table is either erased by `/reset` or declared as one that survives it.

    pytest tests/api/test_a_reset_leaves_no_tenant_conclusion_behind.py -q

⛔ WHY THIS FILE EXISTS. Two tenants were reset through `_wipe` on 2026-10-03 and then every table
carrying `org_id` was counted for them. The schema has **183** such tables, `_ORG_SCOPED_TABLES`
held **102**, and **twelve** of the remainder still had rows afterwards — about 5,800, led by
`context_correlation_members` (2,703) and `execution_events` (832).

The row count is not the point. Those tables hold CONCLUSIONS — executions already planned,
correlations already drawn, residue already recorded — so a tenant that reset its workspace kept
them while the graph they were drawn from was erased. `context_situations` was added to that list
for exactly this, in its own words: *"the next sweep's findings landed beside conclusions drawn from
facts that no longer exist."* It had happened again in twelve more places.

⛔ AND THE LIST COULD ONLY EVER BE AUDITED BY HAND. `_wipe` iterates names; a table added by a
migration is in no relationship with it, so the only thing that noticed was someone resetting a
tenant and looking. Migrations 0186–0188 shipped three new org-scoped tables in the same week and
none of them reached the list. This test is that audit, run on every build: a new org-scoped table
must be erased or named as a survivor, and the choice has to be made at the migration rather than
discovered on a customer's reset.

READ FROM THE MIGRATIONS, NOT FROM A DATABASE, so it runs in the hermetic suite.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from genios_engine.api.account_routes import _ORG_SCOPED_TABLES

pytestmark = pytest.mark.unit

_MIGRATIONS = pathlib.Path(__file__).resolve().parents[2] / "migrations"

#: ⛔ Org-scoped tables that MUST survive a reset, each with the reason it is not tenant content.
#: `/reset`'s own docstring promises the first group ("keeps the account, connections, tasks"); the
#: rest are billing or the audit trail, and an audit row that dies with the erasure it records
#: cannot prove the erasure happened.
SURVIVES_RESET: dict[str, str] = {
    "connections": "the tool stays connected — the docstring promises it",
    "integration_preferences_legacy": "superseded name kept so a rename cannot silently drop a row",
    "api_keys": "the account's credentials, not its data",
    "auth_sessions": "a reset must not sign the owner out mid-action",
    "auth_refresh_rotations": "the rotation chain behind those sessions",
    "device_auth_codes": "a pairing in flight is not tenant content",
    "devices": "the paired machine survives a workspace reset",
    "capture_policies": "what the admin allowed to be captured — a decision, not a conclusion",
    "seat_capture_settings": "same, per seat",
    "org_seats": "the people; wiping them would lock the tenant out",
    "org_self_identities": "who the tenant IS — its declared addresses and domains (STEP-04, 0193): "
                           "authored, like the seats; a reset that forgot them would make the "
                           "founder's second address an outside person again",
    "org_members": "same",
    "org_invites": "an invite in flight",
    "seat_profiles": "the person's own profile",
    "workspace_accounts": "the account itself",
    "orgs_archive": "the archive OF orgs — erasing it would erase the record of erasure",
    "audit_log": "must outlive the erasure it records, or the erasure cannot be proved",
    "organization_resets": "the ledger of resets — same argument",
    "credit_ledger": "billing",
    "subscriptions": "billing",
    "agent_metering": "billing",
    "llm_costs": "spend already incurred; deleting it would delete money owed",
    "tenant_packs": "retained and REWRITTEN by reset (lvl3_config cleared, authority bumped)",
    "user_tasks": "the docstring promises tasks survive",
    "agent_registry": "the agents the tenant registered, not what they concluded",
    "agent_grants": "an authority grant is a decision",
    "agent_delegations": "same",
    "policy_rules": "tenant policy, authored not derived",
    "domain_requests": "a request to GeniOS staff, not tenant data",
    "source_mappings": "client-supplied structured mappings — authored configuration",
    "org_channels": "where to reach them; a reset must not silence the tenant",
    "delivery_preferences": "their own notification choices",
    "user_models": "authored",
    "user_model_proposals": "authored",
    "l4_r_site_generations": "GeniOS-staff artefact, not tenant content",
}


def _org_scoped_tables() -> set[str]:
    """Every table the migrations give an `org_id`, found in the SQL rather than guessed."""
    tables: set[str] = set()
    created = re.compile(r"create table if not exists\s+([a-z0-9_]+)\s*\((.*?)\n\)\s*;", re.S | re.I)
    altered = re.compile(r"alter table\s+([a-z0-9_]+)\s+add column if not exists\s+org_id\b", re.I)
    for path in _MIGRATIONS.glob("*.sql"):
        sql = path.read_text(encoding="utf-8")
        for match in created.finditer(sql):
            if re.search(r"^\s*org_id\b", match.group(2), re.M):
                tables.add(match.group(1))
        tables.update(m.group(1) for m in altered.finditer(sql))
    return tables


#: ⛔ Defined by a migration, ABSENT from the production schema — real drift, recorded rather than
#: hidden. `l2_extraction_results` is created by `0004_l2_context_graph.sql` and given an org FK by
#: `0033_org_data_cascade.sql`, and it does not exist in production. It is therefore NOT in the
#: erase list: `_wipe` has no try/except by design, so naming an absent table turns every `/reset`
#: into a 500. Fixing the drift is a migration, not a line in this set.
DRIFT_NOT_IN_PRODUCTION: dict[str, str] = {
    "l2_extraction_results": "created by 0004, FK'd by 0033, absent from the production schema",
}


def test_the_migrations_still_describe_org_scoped_tables():
    """A regex that silently matches nothing would make every assertion below vacuous."""
    assert len(_org_scoped_tables()) > 150


def test_every_org_scoped_table_is_erased_or_declared_a_survivor():
    """⛔ THE GATE. A migration that adds an org-scoped table must decide, in the same week it
    ships, whether a reset erases it — not leave it to be found on a customer's workspace."""
    undecided = sorted(_org_scoped_tables() - set(_ORG_SCOPED_TABLES) - set(SURVIVES_RESET)
                       - set(DRIFT_NOT_IN_PRODUCTION))
    assert not undecided, (
        "these tables carry org_id and are neither erased by /reset nor declared survivors — "
        "add them to _ORG_SCOPED_TABLES, or to SURVIVES_RESET with the reason they are not "
        f"tenant content: {undecided}")


def test_a_drifted_table_is_never_in_the_erase_list():
    """⛔ Naming a table that does not exist turns every /reset into a 500, because `_wipe` has no
    try/except by design. The drift set exists to record the fact, never to license the crash."""
    for table in DRIFT_NOT_IN_PRODUCTION:
        assert table not in _ORG_SCOPED_TABLES, (
            f"{table} is absent from production; deleting from it would 500 every reset")


def test_the_survivor_list_does_not_overlap_the_erase_list():
    """One table cannot both survive and be erased; an overlap means one of the two reasons is a
    leftover somebody will later read as current."""
    both = sorted(set(_ORG_SCOPED_TABLES) & set(SURVIVES_RESET))
    assert not both, both


def test_every_survivor_carries_a_reason():
    for table, reason in SURVIVES_RESET.items():
        assert reason.strip(), f"{table} survives a reset and nothing says why"


def test_the_twelve_that_were_found_are_erased_now():
    """⛔ THE MUTATION THIS FILE EXISTS TO REJECT — the regression, named. Each of these held rows
    after a real reset on 2026-10-03."""
    for table in ("execution_events", "execution_actions", "execution_escalations",
                  "execution_outcomes", "executions", "context_correlation_members",
                  "context_correlations", "context_node_lifecycle", "context_residue",
                  "graph_health", "evidence_needs", "knowledge_suggestions"):
        assert table in _ORG_SCOPED_TABLES, f"{table} survives a reset again"


def test_children_are_erased_before_their_parents():
    """The loop runs with no try/except by design, so a name in the wrong order fails loudly.
    `executions` and `context_correlations` are the two parents in this wave."""
    order = {name: i for i, name in enumerate(_ORG_SCOPED_TABLES)}
    for child, parent in (("execution_events", "executions"),
                          ("execution_actions", "executions"),
                          ("execution_escalations", "executions"),
                          ("execution_outcomes", "executions"),
                          ("context_correlation_members", "context_correlations")):
        assert order[child] < order[parent], f"{child} must be deleted before {parent}"
