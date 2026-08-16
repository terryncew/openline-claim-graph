# Receiver Discovery Pilot

Status: `PROTOCOL_READY_CASE_PACK_EMPTY`

This directory defines the first real-value test for the claim-graph prototype:

> Does claim-level extraction or graph structure help an unfamiliar human receiver locate a consequential disagreement or missing premise in a fixed source packet?

The pilot has not been run. No cases, receivers, or results are included. Nothing here changes the repository's `UNPROMOTED_EXTERNAL_VALUE_UNTESTED` status.

## What is fixed now

- the human receiver is the target of this study;
- three presentation arms separate ordinary summarization, claim extraction, and graph structure;
- condition is assigned between receivers to prevent graph exposure from training later control responses;
- one domain and one declared receiver population are used per pilot;
- case admission and sampling are fixed before artifacts are built;
- resolving events anchor the location of a fault line, not which side was true;
- no-conflict cases measure false discovery;
- top-ranked answers determine the primary result, preventing answer spraying;
- Stage 1 estimates feasibility and effect size only;
- Stage 2 requires a new, simulation-powered preregistration and substantially more independent cases.

## What remains empty on purpose

- the candidate-case screening log;
- the eligible-case population;
- the public random seed used to sample cases;
- the private answer-key custody file;
- the three matched receiver surfaces;
- receiver assignments and responses.

Inventing those items merely to make this directory look complete would recreate the failure this experiment is meant to prevent.

## Files

- `PROTOCOL.md` — study design and dispositions.
- `CASE_ADMISSION.md` — eligibility, sampling, external anchors, and custody separation.
- `SURFACE_SPEC.md` — information and presentation rules for Arms A, B, and C.
- `SCORING_RUBRIC.md` — fixed response and scoring rules.
- `ANALYSIS_PLAN.md` — Stage 1 estimates and the boundary for any later Stage 2 study.
- `RECEIVER_INSTRUCTIONS.md` — hypothesis-neutral participant instructions.
- `pilot-contract.json` — machine-readable version of the fixed design.
- `templates/` — public case, private key, response, score, and pack-manifest templates.
- `../../scripts/build_pilot_assignments.py` — deterministic, between-receiver assignment tool.

## Required order

1. Declare one domain, one receiver population, and one candidate source universe.
2. Screen every candidate under `CASE_ADMISSION.md`; retain exclusions and reasons.
3. Commit the eligible list before obtaining the declared future public random seed.
4. Sample cases. Two independent key adjudicators then create the hidden keys.
5. Lock the private-key hashes. Only then may key-blind builders produce the three surfaces.
6. Validate information parity between Arms B and C and freeze every receiver file.
7. Generate assignments and run a small usability dry run with data excluded from analysis.
8. Run Stage 1. Report every case and every deviation. Do not promote or archive the value claim from Stage 1.

The protocol may be revised before a run, but revisions create a new version with a parent hash and a written delta. A hash establishes custody, not correctness.
