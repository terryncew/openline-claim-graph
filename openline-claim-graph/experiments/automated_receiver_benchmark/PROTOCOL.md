# Protocol: Automated Receiver Value Benchmark v1

Status: `PUSH_READY_HARNESS_PROTOCOL`; no validating run exists.

## Claim under test

For a declared task, receiver model, source boundary, context, and budget, a
verified structured claim state improves a machine receiver's exact decision
and evidence recovery over matched prose without increasing false conflicts.

This protocol does not test or imply human comprehension.

## Four separate authorities

1. **External gold** — a versioned dataset or publisher correction supplies
   labels and evidence identifiers. The mapper and receiver never see it.
2. **Surface builder** — creates all three arms from source material, freezes
   them, and commits their hashes. The harness recomputes the common source and
   inventory roots, requires B to equal its deterministic prose renderer, and
   requires C to equal the exact structured inventory.
3. **Receiver** — gets one case and one arm in a fresh process. It emits strict
   identifiers, not free-form prose for another model to grade.
4. **Scorer** — deterministic code compares the response with the bound gold
   file. Missing, malformed, timed-out, or skipped responses count as misses.

No role may generate its own answer key. No LLM judge is admissible.

The validator can prove byte-level pack/gold separation and deterministic
surface parity. It cannot prove that a case author omitted no relevant fact or
that an external gold source is correct. Those remain dataset-custody claims.

## Arms

| Arm | Surface | Estimand |
|---|---|---|
| A | source packet plus ordinary summary | realistic baseline |
| B | frozen claim inventory rendered as prose | value of extraction |
| C | the identical inventory as verified structured state | added value of structure |

Every receiver-model/case/arm/repetition trial runs in a fresh process. A
receiver sees no other arm for the case and receives no hypothesis language.

## Gold and pack eligibility

A validating pack must:

- bind the private gold file to the exact public-pack SHA-256;
- include at least two independently created datasets;
- include a declared no-conflict label and negative-control cases;
- use exact labels and evidence/premise identifiers that code can score;
- disclose public-benchmark and model-pretraining contamination risk;
- keep development cases out of any claimed temporal holdout; and
- freeze task, prompts, model identifiers, tools, temperature, token budget,
  retry policy, repetitions, and dollar ceiling before execution.

The checked-in ARCT pack is deliberately `DEVELOPMENT_ONLY` and fails these
eligibility conditions. It exercises the harness; it is not evidence that the
graph helps a receiver.

## Predeclared primary rule

The checked-in default contract requires all of the following:

- Arm C minus Arm A joint-hit rate: at least +10 percentage points;
- Arm C minus Arm B joint-hit rate: at least +5 percentage points;
- no increase in false-conflict rate above the declared tolerance;
- positive paired confidence bounds when the pack requires them;
- complete valid responses;
- at least two datasets and two frozen receiver families; and
- a pack marked `VALIDATION_ELIGIBLE` before the run.

The scorer enforces the machine-readable contract and reports every blocker.
It does not silently promote a development pack.

## Interpretation

- **C beats A and B across eligible datasets and receivers:** structured state
  earns a temporal holdout and one real agent-to-agent handoff pilot.
- **B beats A; C does not beat B:** extraction helps; graph presentation does
  not. Keep the graph only where custody or lineage independently needs it.
- **Neither beats A:** retire the receiver-value claim.
- **One model or one public dataset wins:** report a local effect only.
- **Leakage, mismatch, ambiguity, missing output, or budget drift:** invalidate
  or fail the affected trials. Never interpret a favorable partial result.

## Cost and reproducibility

Ordinary CI runs only offline fixtures. Paid receiver runs use a separate,
resumable workflow with a declared micro-dollar stop ceiling. The harness stops
launching trials when reported cumulative cost reaches the ceiling; the
provider adapter must also enforce a per-call provider limit because the core
cannot reverse a charge or independently observe a provider bill. Every trial records the
surface hash, model/receiver identifier, latency, token counts, cost, raw-output
hashes, and strict parsed answer. The scorer includes missing trials so a run
cannot improve by dropping failures.

## Human protocol

The existing `receiver_discovery_pilot` remains available if a future claim is
specifically about human comprehension. It is not a dependency of this
machine-receiver experiment and is not authorized by a machine-only result.
