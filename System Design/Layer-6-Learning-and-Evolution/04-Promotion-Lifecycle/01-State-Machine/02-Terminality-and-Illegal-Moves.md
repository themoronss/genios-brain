# Terminality and illegal moves

Rejected, expired and rolled_back objects are terminal. Published objects may only be superseded
or rolled back. Superseded is terminal during ordinary publication, with one narrow exception:
rollback may restore the exact linked predecessor from Superseded to Published after checking its
tenant, target, subject, ACL and current preflight policy.

Same-state transitions are idempotent. Every other illegal edge is rejected by the transition
authority. An identical later-week proposal may only re-evaluate the existing row while it remains
Observed/Candidate; Candidate cannot regress. Validated, Governed, Temporary, HumanReview,
Promoted, Published and terminal duplicates do not re-enter the path. New evidence creates a new
immutable proposal identity, and an API caller cannot manufacture a lifecycle shortcut.
