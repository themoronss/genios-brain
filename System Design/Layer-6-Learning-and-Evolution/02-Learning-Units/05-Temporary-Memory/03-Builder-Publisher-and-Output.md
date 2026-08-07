# Builder, Publisher and Output

The builder emits unit `temporary_memory`, target `runtime`, subject `memory:<pattern_key>`, exact
value, source/trace/independence lineage, actor subject principal, private ACL, expiry and
`metadata.explicit=true`.

Publication inserts idempotently by learning ID into `temporary_memories` as soon as governance
returns `temporary`; there is no review-queue branch. When the lease is due, tenant-scoped
retention locks memory/object, stamps
`expired_at` and appends the only legal transition to `expired`. API reads exclude expired/due
memories by default and repeat ACL filtering.

**Integration note:** a cache is optional and cannot be the retention authority. A lower-runtime
reader is still required to apply active memory in reasoning/execution; it must enforce the stored
ACL and expiry on every read.
