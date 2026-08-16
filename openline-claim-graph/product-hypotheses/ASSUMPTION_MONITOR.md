# DRAFT_PRODUCT_HYPOTHESIS: Assumption Monitor

Status: `DRAFT_PRODUCT_HYPOTHESIS`

Receiver surface: `TBD_BY_HUMAN_PILOT`

Build authority: `NONE`

This note stores a product hypothesis. It does not settle it and authorizes no monitor, service, new repository, or materiality score.

## Hypothesis

Do not tell a receiver everything that happened. Tell them which declared assumption their current decision depends on may have changed, disclose the searched boundary, and show the source-anchored proposed delta.

A receiver begins with a finite accepted state:

- one decision or thesis;
- a short receiver-declared assumption set;
- declared uncertainties;
- an evidence-accepted-through date;
- a source and retrieval boundary.

New material can propose a state transition only when it touches that declared set. The system does not invent a universal importance or coherence score. The receiver supplies the boundary and decides whether to accept, quarantine, or reject the proposed transition.

Silence also needs a receipt. “No proposed change” means only that no qualifying change was found inside the disclosed source, cutoff, retrieval, and matcher boundary. It never means nothing changed.

## Layering if evidence later earns a build

1. Assumption Monitor — recurring bounded search.
2. Decision Review — one proposed state transition.
3. Claim graph — dependency and conflict representation.
4. Receipt — provenance and custody commitment.
5. Wallet — accepted-state and branch history.
6. Gate — receiver authority to accept the transition.

The `render-review` command in this repository is a verified diagnostic surface over an existing bundle. It is not the monitor and does not choose material changes.

## What resolves the human surface

The receiver-discovery pilot, not preference:

- graph beats extracted prose: study a graph-rendered Decision Review;
- extraction beats ordinary summary but graph adds nothing: use source-anchored prose;
- neither beats the baseline: retire the human-facing decision-value claim; keep only mechanics that have independent use.

## Explicit prohibitions

- No universal or sender-certified materiality scalar.
- No claim that a non-alert proves no relevant change exists.
- No automatic acceptance of a semantic mapping because its receipt is authentic.
- No monitor or continuous service before receiver value and extraction error are measured.
- No truth, consensus, alignment, or “knowledge operating system” claim.

## Next evidence dependency

This monitor remains dormant. Version `0.2.0.dev1` implements a separate deterministic operation, Evidence Recall: a known source-status event is applied to an already accepted dependency state. That operation does not search for new material, decide materiality, or authorize a state transition, so it does not quietly instantiate this monitor hypothesis.

The next product-relevant evidence for a monitor is an operational test on a maintained bounded state: does it catch required reconsideration that direct source lookup misses without creating unacceptable review volume? The dormant human protocol remains required before making any claim about human comprehension.

The PLOS evidence-recall specimen proves conditional propagation on one real correction event over authored dependencies. It does not establish continuous monitoring, automated extraction, adoption, or economic value.
