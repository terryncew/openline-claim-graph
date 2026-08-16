# ARCT independent-gold development check

Status: `EXPLORATORY_INDEPENDENT_GOLD_POSITIVE_CONTROL`

This is not the receiver-discovery pilot and it cannot promote the graph claim. It tests an earlier boundary: can one source-to-graph mapping pass recover missing premises that were labeled by people outside this project?

The source is the Argument Reasoning Comprehension Task (ARCT) dev set. ARCT supplies authentic arguments as a premise, a claim, two plausible implicit warrants, and an independently produced correct-warrant label. The upstream paper describes a freely licensed dataset of roughly 2,000 authentic arguments. The frozen input here is a deterministic 24-case subset of the 316-row dev file at one named upstream commit.

## Custody record

The sequence executed in the build conversation was:

1. Fetch the upstream dev file at the named commit.
2. Select 24 rows using the frozen FNV-1a rule in `cases.blind.json`.
3. Show the mapper only premise, claim, both candidate warrants, and debate context.
4. Record one warrant prediction for every case.
5. Reveal the upstream labels and score the frozen vector.

The result was **21/24 (87.5%)**. The three misses remain in the artifact. The repository file was assembled after scoring, so there is no independent public timestamped precommit for the prediction vector; the conversation/tool transcript is the only ordering record. That limitation is why this remains exploratory.

The selected text and revealed labels were also compared field-for-field with the upstream file at the pinned commit. All 24 rows matched exactly. The live check is recorded in `upstream-verification.json`; `scripts/verify_arct_upstream.py` lets an outsider repeat it from a downloaded upstream TSV.

## What the executable check establishes

`scripts/run_arct_development_check.py` builds three claim graphs per case:

- the frozen blind prediction;
- the upstream gold warrant;
- the opposite-warrant control.

It then verifies that all 72 graphs are mechanically valid, the chosen warrant changes the committed state in all 24 cases, the gold control scores 24/24, the opposite control scores 0/24, and the frozen blind mapping scores 21/24.

This is evidence that the source-to-structure step can carry non-random signal on a small outside-labeled missing-premise task. It is not evidence that a graph helps a receiver more than prose. It is also not open-ended extraction: the mapper chose between two supplied warrants.

## Reproduce

```bash
PYTHONPATH=src python scripts/run_arct_development_check.py
PYTHONPATH=src python -m unittest tests.test_arct_development_check -v
python scripts/verify_arct_upstream.py --upstream-tsv /path/to/upstream/dev.tsv
```

## Known threats to validity

- 24 cases are a development sample, not a validating study.
- One interactive model pass was used; there was no replicated model cohort.
- ARCT is a public 2018 benchmark, so model pretraining contamination cannot be excluded.
- The task is multiple-choice, not free reconstruction.
- Gold labels reflect ARCT's annotation procedure; they are independent of OpenLine, not metaphysical truth.
- This does not exercise the human three-arm receiver protocol.

## Upstream attribution

Ivan Habernal, Henning Wachsmuth, Iryna Gurevych, and Benno Stein, “The Argument Reasoning Comprehension Task: Identification and Reconstruction of Implicit Warrants,” NAACL 2018, DOI `10.18653/v1/N18-1175`.

Upstream repository: `UKPLab/argument-reasoning-comprehension-task`, commit `929f5847487e28036e60803f72e26a82c638db43`, path `experiments/src/main/python/data/dev.tsv`, Git blob SHA `f2a591421d1d61f16e8e5b54e28e9f71d41ba1f5`.

The upstream repository is licensed under Apache License 2.0. See `THIRD_PARTY_NOTICE.md` and `LICENSE-ARCT-APACHE-2.0.txt`.
