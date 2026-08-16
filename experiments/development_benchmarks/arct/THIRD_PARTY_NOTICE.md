# Third-party notice — ARCT fixture

This directory contains a 24-row derived subset of the Argument Reasoning Comprehension Task data from:

- Repository: `https://github.com/UKPLab/argument-reasoning-comprehension-task`
- Commit: `929f5847487e28036e60803f72e26a82c638db43`
- Source path: `experiments/src/main/python/data/dev.tsv`
- Git blob SHA: `f2a591421d1d61f16e8e5b54e28e9f71d41ba1f5`
- Authors: Ivan Habernal, Henning Wachsmuth, Iryna Gurevych, and Benno Stein
- Paper DOI: `10.18653/v1/N18-1175`
- Upstream license: Apache License 2.0

The source rows were transformed into JSON, field `id` was renamed `case_id`, `correctLabelW0orW1` was moved into `gold.revealed.json`, and a deterministic subset was selected. No claim is made that this project owns or originated the source data.
