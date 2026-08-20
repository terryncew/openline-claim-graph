# ERC-001 — Trivy → LiteLLM revocation propagation

**Status:** retrospective external representation test; **zero Cohort 001 credit**.

This pack tests the frozen OpenLine Claim Graph `0.6.1.dev0` Decision Recall semantics against a real 2026 supply-chain incident. It does not modify Decision Recall, Cohort 001, or the vendored package.

The question is narrow:

> When Trivy's distribution integrity lost standing, can the frozen Decision Recall representation identify the downstream LiteLLM state that should be reopened — and does it do better than flat search?

The case deliberately forbids hindsight repair. A dependency may enter the reconstructed pre-trigger manifest only when it is explicit in the pre-trigger public record. Post-trigger evidence may adjudicate gold, but may not add missing pre-trigger edges.

## Result

Run `python -I scripts/verify_erc001.py`.

The frozen fixture currently yields **REPRESENTATION_GAP_FLAT_SEARCH_PARITY**:

- Full History surfaces all 3 reconstructed accepted states and misses no warranted reopening at the triage stage.
- Flat Search surfaces the direct Trivy-dependent CI state, but misses the PyPI credential standing that later proved exposed through the Trivy chain.
- Decision Recall produces the same review set as Flat Search: it correctly reopens the direct Trivy-dependent CI state, but it also misses the PyPI credential standing because the intermediate authority/dependency path was not represented prospectively.
- The source-controlled GitHub release lineage remains a negative control and survives.

So ERC-001 does **not** earn a new mechanism. It demonstrates a bounded representation gap: direct-basis recall is not multi-hop authority/dependency propagation.

## Claim boundary

This is a retrospective historical reconstruction after the outcome was known. It does not establish prospective capture quality, annual economics, market demand, incident-prevention effectiveness, or causal proof beyond the cited first-party incident record. It does not justify retroactively adding a Trivy edge to the PyPI credential manifest.
