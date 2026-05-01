# 04 — OAuth token refresh failing

## Trigger
- Gmail/Calendar/Slack sync tasks erroring with `invalid_grant` / `invalid_token`
- Users report "my inbox stopped syncing"
- `user_mailboxes.sync_error` populated for many users

## Diagnosis
1. Which providers affected: `SELECT provider, COUNT(*) FROM user_mailboxes WHERE sync_error IS NOT NULL AND last_sync_at > NOW()-INTERVAL '24 hours' GROUP BY provider;`
2. Which tenants: add `, org_id` to GROUP BY.
3. Is it fleet-wide (our OAuth app revoked?) or per-user (expired refresh tokens)?
4. Check Google Cloud Console / Slack app dashboard for any status changes or policy violations.

## Mitigation
- Per-user: user has revoked access or password changed → ask them to reconnect in dashboard
- Fleet-wide on one provider: check if our OAuth client secret rotated silently; if so, hot-swap env var and restart
- If Google's 7-day refresh-token expiry was hit (unverified app): this is the 6-month review limit — escalate to app verification
- Disable the failing provider's Celery sync task temporarily to stop error spam

## Follow-up
- Proactively refresh tokens before expiry (Celery beat already does it — see `task_renew_watches`)
- Add alert on `user_mailboxes.sync_error IS NOT NULL COUNT` > threshold
- Automate the user-facing reconnect prompt in dashboard
