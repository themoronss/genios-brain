# Transition ledger

Every state edge records transition id, tenant, LearningObject, before/after state, reason, actor,
detail and explicit time in `learning_transitions`. Current state is updated only through the
guarded transition function.

The ledger answers why an object waited, was rejected, required review, published or was reversed.
