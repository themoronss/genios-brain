"""P4 team intelligence — deterministic post-passes after the L2→L4→cards chain (SCREEN_INTEL_P4 §3.1).

  postpass.py   run_post_passes — the one hook the chain calls (api/routes.py `_run_l2_chain`)
  emit.py       emit_situation — card + moment + team_situations row in one transaction (A owns, B calls)
  passes.py     the team pass registered with the hook: away/deadline (P-09/P-10) + readiness (P-12)
  away.py       P-09/P-10 · cover.py P-11 · readiness.py P-12

NEVER CREDIT-CHARGED: nothing here touches billing.
"""
