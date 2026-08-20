# ERC-001 Protocol

## Frozen question

Can OpenLine Claim Graph `0.6.1.dev0` selectively reopen downstream accepted state after a real upstream supply-chain basis loses standing, without hindsight-invented dependency edges?

## Source-time split

**Pre-trigger surface:** public repository state at LiteLLM tag `v1.82.6.dev1`. Only dependencies explicit in that surface may enter the reconstructed manifests.

**Trigger:** public loss of standing for Trivy distribution integrity after the March 19–20, 2026 compromise became known.

**Post-trigger adjudication:** the Trivy advisory and LiteLLM incident record may determine which reconstructed accepted states warranted reopening. They may not alter the pre-trigger manifests.

## Systems

1. `FULL_HISTORY_REVIEW` — review every reconstructed accepted state.
2. `FLAT_LOG_SEARCH` — surface records directly indexed to the revoked Trivy basis.
3. `DECISION_RECALL` — frozen `0.6.1.dev0` disposition logic over the reconstructed dependency manifests.

## Admitted accepted-state projections

This is not a claim that these were explicit human decisions. They are retrospective projections of operational accepted state from public configuration artifacts:

- `ci-security-scan-trust`: the unpinned Trivy installation used as a security control remains trustworthy.
- `pypi-publish-credential-standing`: the PyPI publishing credential remains confidential and valid.
- `github-release-source-lineage`: the source-controlled GitHub release lineage remains legitimate.

## Anti-hindsight rule

The PyPI publishing workflow contains the publish secret but does not itself document a dependency on Trivy. Therefore `trivy-distribution-latest` is **not** admitted into that manifest, even though later evidence documents the Trivy → credential-compromise chain. Adding that edge after the incident would make the benchmark easier by writing the answer into the manifest.

## Verdict rule

- `SUPPORTED_SELECTIVITY`: Decision Recall has zero additional warranted-reopening misses versus Full History and materially reduces review load.
- `FLAT_SEARCH_ENOUGH`: Decision Recall has no safety or review advantage over Flat Search.
- `REPRESENTATION_GAP`: Decision Recall misses a warranted reopening because the needed dependency/authority path is not representable in the frozen accepted state.
- `REPRESENTATION_GAP_FLAT_SEARCH_PARITY`: both of the previous conditions hold.

No result from this pack may promote Decision Recall or change Cohort 001.
