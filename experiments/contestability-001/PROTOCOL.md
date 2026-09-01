# CONTESTABILITY-001 protocol

Base repository: `terryncew/openline-claim-graph`

Frozen base: `15b405580a5f8fe261dcca38cbcb11f169e671d0`

## Hypothesis

A receiver can treat foreign contestability material as evidence rather than authority. The foreign object may establish binding, discoverability, authenticated filing, executor acceptance, and a claimed foreign application. None of those facts may directly mutate receiver standing.

A receiver-owned policy must produce a distinct standing decision. A receiver-owned application step may then selectively reopen only consequences downstream of the affected authorization.

## Foreign / local boundary

Foreign stages are preserved independently:

- `issuer_declared_effect`
- `executor_acceptance`
- `authenticated_filing_trigger`
- `foreign_application_claim`

OpenLine stages are separate:

- `receiver_acceptance`
- `local_application`

The adapter is profile-driven. Draft-specific field locations live in `adapter-profile.json`, not in `contestability.py`.

## Graph

The fixture contains two authorization lineages.

`auth-A → action-A → consequence-A-settlement → consequence-A-notice`

`auth-B → action-B → consequence-B-benefit`

Actions are historical execution records and are not reopenable. Consequences are reopenable. If receiver policy changes `auth-A` standing from `VALID` to `CONTESTED`, the application step must reopen the two `A` consequences while preserving `action-A == EXECUTED` and the entire `B` lineage.

## Arms

1. **FILED_ONLY** — normalize an authenticated filing and stop. Expected local state delta: zero.
2. **DECLARED_EFFECT_WITHOUT_TRIGGER** — foreign declared effect and executor acceptance are present, but no authenticated filing. Expected local standing change: none.
3. **FOREIGN_APPLIED_BUT_LOCALLY_REJECTED** — the foreign result claims application, but the receiver does not accept the forum. Expected local state delta: zero.
4. **VALID_LOCAL_ACCEPT_APPLY** — all receiver conditions pass, the receiver explicitly changes standing, then the local application step runs. Expected reopen set: exactly two dependent consequences.
5. **ALTERNATE_PROFILE** — the same semantic facts arrive in a different foreign object layout. Only the data profile changes. Expected normalized event and local consequence result: equivalent.

## Claim boundary

This is a deterministic integration/conformance experiment. It does not prove legal standing, forum independence, the legitimacy of the authorization, or correctness of a foreign cryptographic verifier. It specifically tests whether OpenLine can keep foreign evidence separate from receiver-owned standing and consequence application.
