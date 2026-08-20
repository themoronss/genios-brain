-- GeniOS Engine · Layer 6 — k-anonymity promotion floor for cross-entity patterns.
--
-- unit_pattern_learning could previously promote a "pattern" backed by any N observations, even
-- 10 emails from the SAME one company — nothing checked whether the evidence spanned distinct
-- entities. A generalized pattern derived from too few distinct companies/people effectively
-- names them. min_distinct_entities is the floor; validate_learning enforces it for
-- LearningTarget.ORGANIZATION proposals only (the target unit_pattern_learning emits).
alter table learning_policies
    add column if not exists min_distinct_entities int not null default 3;
