# Automated Receiver Benchmark

Status: `HARNESS_READY_DEVELOPMENT_PACK_ONLY_NO_EXTERNAL_RESULT`

This experiment replaces the immediate human-recruitment dependency with a
narrower, fully automated question:

> Under a fixed task, model, context, and budget, does a verified structured
> state help an isolated machine receiver recover the correct label and
> external evidence better than ordinary or extracted prose?

That result would apply to machine receivers only. It would not establish
human readability, truth, open-domain generalization, or production safety.

The executable implementation is in `openline_claim_graph.benchmark`. The
checked-in ARCT pack under `artifacts/automated-receiver-benchmark/` is a
development-only fixture. It contains no receiver outputs and cannot pass the
promotion gate because it is one public dataset, has possible pretraining
contamination, and contains no no-conflict controls.

See [PROTOCOL.md](PROTOCOL.md) for the authority separation, success bar, and
failure rules.

