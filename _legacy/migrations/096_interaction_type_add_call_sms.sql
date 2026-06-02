-- Phase 1, Item #6 pre-requisite: extend the interactions.interaction_type
-- CHECK constraint so Inkbox-synced voice calls and SMS preserve their
-- channel identity instead of collapsing into 'other'. Without this, the
-- channel recommendation feature can never surface "call" as a viable
-- channel even when the contact actually engaged via phone.

ALTER TABLE interactions DROP CONSTRAINT IF EXISTS interactions_interaction_type_check;
ALTER TABLE interactions ADD CONSTRAINT interactions_interaction_type_check
    CHECK (interaction_type IN (
        'email_reply', 'email_one_way', 'commitment', 'meeting', 'other',
        'cc', 'slack_dm', 'slack_mention', 'jira_issue', 'file_shared', 'doc_shared',
        'call', 'sms'
    ));
