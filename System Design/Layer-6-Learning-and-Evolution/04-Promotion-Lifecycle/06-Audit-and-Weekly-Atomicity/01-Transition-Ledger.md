# Transition ledger

Every state edge records transition id, tenant, LearningObject, before/after state, reason, actor,
detail and explicit time in `learning_transitions`. Current state is updated only through the
guarded transition function.

The current row also projects `governance_verdict` and `promotion_state`; the immutable proposal
payload remains untouched. Rehydration verifies tenant, content-derived ID and semantic hash before
any state mutation.

`learning_object_evaluations` complements transition history. It appends one row for each object
actually evaluated in a claimed run, including a held Observed/Candidate duplicate whose state does
not change. The row records run, policy key/revision, evaluation time, prior/result state, closed
reason and whether the immutable object was newly inserted. Reason is the terminal sink outcome
returned by `apply_path_result`, not just the last planned policy edge: publication success,
no-material-change and metric-identity conflict are therefore replayable exactly. Its composite
run-policy-time foreign key prevents attributing a decision to authority other than the policy and
clock pinned by that run.

Review/published/later/terminal duplicates are skipped before evaluation, so they neither reopen nor
manufacture a misleading re-evaluation row. Full tenant erasure may cascade retained audit data;
normal lifecycle processing only inserts evaluation rows.

Malformed lower-layer inputs and preflight refusals use `learning_input_rejections`. That ledger
stores stable hashes, closed reason codes and minimal lineage/ACL metadata, never the rejected raw
value. It answers why input did not become a LearningObject without violating the policy that
forbade retention.
