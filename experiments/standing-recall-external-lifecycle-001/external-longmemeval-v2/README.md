# SRE-001 — External LongMemEval-V2 adaptation

This directory is the first external-source lane for **Standing Recall Test — External Lifecycle**.

It binds the frozen SRE-001 decision pattern to two structural state anchors from each of five pinned public LongMemEval-V2 trajectory excerpts, then injects a later `EXPIRE`, `REVOKE`, `SUPERSEDE`, or `CORRECT` event only after every decision has validly finalized.

The lane compares:

- a DGRR paper-contract node-support adaptation;
- a deliberately strong MemoRepair barrier-first adaptation with exact property-aware validation; and
- the already-frozen OpenLine standing mechanism.

The discriminating result is **not** whether OpenLine alone can identify the right reopened decision. MemoRepair is intentionally given enough validation semantics to match that if its published repair contract permits it. The sharper test is whether barrier-first repair must withdraw/reconsider more valid state than standing recomputation.

The 40 lifecycle episodes are repeated interventions over 10 state anchors from 5 external trajectories, not 40 independent trajectories.

At installation this lane is **unrun**. GitHub Actions performs the first repository-visible run against the pinned external bytes and publishes only workflow artifacts. Nothing in this directory upgrades the parent SRE-001 claim before that run independently verifies.

See `ADAPTATION_PROTOCOL.md`, `SOURCE_PINS.json`, and `ADAPTER_POLICY.json`.
