# Frame Ledger

`Frame Ledger` audits an exact surface for reproducible framing devices and keeps semantic interpretation under an explicit receiver policy.

It does **not** answer “is this propaganda?” with a score. It answers smaller questions that can survive inspection:

- which epistemic word was actually used (`contradicting`, `false`, `lied`);
- which context connector was actually used (`amid`, `because`, `despite`);
- which declared issue-frame lexemes occur (`secret`, `threat`);
- whether a narrow local attribution grammar matched; and
- whether a receiver-declared term set is absent from the exact audited surface.

Every positive match is bound to a UTF-8 byte span. Every absence is bound to the complete audited scope and the exact term set searched. The ruleset, policy, source, findings, and report are content-addressed.

## Two layers

| Layer | What can enter it | Admission |
|---|---|---|
| Mechanical | Exact lexemes, local grammar patterns, declared scoped absences | Deterministic reproduction under the pinned ruleset |
| Advisory | Agency suppression, evidence asymmetry, implied causality, or fact-status omission | Signed receiver-policy quorum from distinct declared model families; proposer cannot review itself |

Human confirmation can be `OPTIONAL`, `REQUIRED`, or `DISABLED`. This is not a disguised human-review requirement. A fully autonomous receiver can select `OPTIONAL` or `DISABLED`, pin its proposer and reviewer keys, require two independent model families, and block on any signed challenge.

The guarantee remains conditional. Public keys prove which configured execution identities signed. A `family` label is declared by the receiver; the software cannot prove that two models are truly independent or free of shared training data.

## Why this is not a bias score

`RATIONALIZATION_VERDICT`, `PROPAGANDA_VERDICT`, `DECEPTION_INTENT`, `FAIRNESS_VERDICT`, `TRUTH_VERDICT`, and `BIAS_SCORE` are prohibited device types. The core can expose mechanisms that a reader may use when making those judgments, but it does not launder the judgment into a green check.

This boundary still permits pointed audits. The same rules can be applied to a Trump headline, a Biden headline, a corporate press release, a tax notice, or a model-generated answer. Evenhandedness is achieved through the declared rules and source scope—not by pretending every interpretation has equal evidentiary support.

## Autonomous frontier/open-model lane

`scripts/frame_agent_adapter.py` reads one proposal or review task on stdin and writes strict JSON on stdout. It supports:

- the official OpenAI Responses API with strict Structured Outputs and `store: false`; and
- OpenAI-compatible chat-completions servers used by vLLM, SGLang, llama.cpp, and many hosted open-weight services.

Example with a local vLLM server:

```bash
PYTHONPATH=src python scripts/frame_agent_adapter.py \
  --api-style chat \
  --base-url http://127.0.0.1:8000/v1 \
  --model Qwen/Qwen3.8-27B < proposal-task.json > proposal-output.json
```

The adapter constrains syntax. The importer still rejects invented quotes. Receiver policy still requires signed, non-self, heterogeneous review before an inference becomes `ADVISORY_ADMITTED`.

For a complete unattended run, copy `examples/frame-agent-run-config.template.json`, point its three actors at separate model endpoints, place each 32-byte Ed25519 private key in the named environment variable, build the pinned receiver policy, and run the orchestrator:

```bash
PYTHONPATH=src python scripts/build_frame_agent_policy.py \
  --config frame-agent-run-config.json \
  --human-mode OPTIONAL \
  --output frame-agent-policy.json

PYTHONPATH=src python scripts/run_autonomous_frame_pipeline.py \
  --source artifacts/wapo-headline-frame-ledger/source.json \
  --policy frame-agent-policy.json \
  --config frame-agent-run-config.json \
  --output autonomous-frame-run
```

The model calls are untrusted. The orchestrator imports only exact quotes, signs the configured execution identities' outputs, forbids proposer self-review, applies the pinned quorum, and renders a reproduced report. `OPTIONAL` means the cycle completes without a human action; a deployment that wants a mandatory sign-off can select `REQUIRED`.

`docs/open-model-candidates.json` records current model-card facts and our role-fit inferences separately. Every entry is `UNRUN_CANDIDATE`; the repository contains no fabricated frontier or open-model result.

## Research grounding

The typed-device approach composes existing framing research rather than claiming a new universal theory:

- Spinde et al., *The Media Bias Taxonomy: A Systematic Literature Review on the Forms and Automated Detection of Media Bias* — <https://arxiv.org/abs/2312.16148>
- Card et al., *The Media Frames Corpus* — <https://aclanthology.org/P15-2072/>
- Sap et al., *Connotation Frames of Power and Agency in Modern Films* — <https://aclanthology.org/D17-1247/>
- Hamborg et al., NewsWCL50 — <https://github.com/fhamborg/NewsWCL50>

Those resources support the general premise that framing devices can be annotated. They do not validate this ruleset or this one-headline specimen.

## Reproduce the checked-in specimen

```bash
PYTHONPATH=src python examples/build_wapo_frame_ledger.py \
  --output artifacts/wapo-headline-frame-ledger

PYTHONPATH=src python -m openline_claim_graph verify-frame \
  --report artifacts/wapo-headline-frame-ledger/report.json \
  --source artifacts/wapo-headline-frame-ledger/source.json \
  --findings artifacts/wapo-headline-frame-ledger/findings.json \
  --policy artifacts/wapo-headline-frame-ledger/policy.json
```

The specimen audits only the user-supplied headline. It does not audit the article body and does not determine whether the headline is fair, accurate, or rationalizing anyone.
