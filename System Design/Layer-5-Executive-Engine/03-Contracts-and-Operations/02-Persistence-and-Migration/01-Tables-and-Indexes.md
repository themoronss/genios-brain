# Tables and indexes

Migration 0041 creates the execution commitment, action, escalation, event and outcome structures
and adds reporting-line support on organization seats. Indexes cover due commitments, open
actions, due escalation rungs, event lookup and learning cohorts.

A partial unique rule prevents more than one open commitment for the same organization/decision.
Organization foreign keys cascade through account erasure.
