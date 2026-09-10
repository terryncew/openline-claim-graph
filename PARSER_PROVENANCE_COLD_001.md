# PARSER-PROVENANCE-COLD-001

Status: **cold external experiment — no production feature change**.

Pinned OpenLine Claim Graph base:

```text
559d179dcb30417f7e453edf3ed5778ba99733a0
```

External trigger: *PARSER: Read in Parallel, Reason in Depth for Long-Context LLM Agents*, arXiv `2609.06702v1` (2026-09-06).

## Why this experiment exists

PARSER parallelizes long-document reading by binding lightweight subagents to chunks and letting a lead agent gather their findings over multiple reasoning rounds.

Its published failure case is more interesting to OpenLine than the speedup. A chunk-local reader sees a similarly named person, returns a locally plausible husband, and the lead agent accepts that answer even though another reader returned identity-grounded evidence for the correct person. The paper says the lead agent does not have the subagent's source reference and therefore cannot directly verify the grounding of the local conclusion.

That attacks an OpenLine boundary already present on current main: exact source bytes and quote spans are mechanically verifiable, while semantic truth and semantic mappings are not automatically established.

The question is therefore not whether Claim Graph can solve entity resolution. It does not claim that. The question is whether represented parallel findings can lose their provenance or collapse a contradiction silently before a receiver makes an explicit choice.

## Controlled adaptation

This experiment does not copy PARSER's benchmark item or run PARSER models. It uses a small synthetic same-name fixture with the same failure shape.

Two parallel readers produce claims for one represented slot:

```text
person:princess-elene-of-georgia:husband
```

One finding is source-exact and correct for the target. The other is also source-exact, but its source is about a different similarly named person. The second reader therefore attaches exact local evidence to the wrong target slot.

This distinction is deliberate: provenance can be mechanically exact while identity binding is semantically wrong.

## Frozen probes

### 1. Source-anchor tamper

Mutate the misleading source bytes after its QUOTE anchor and snapshot are committed.

Falsifier: the snapshot still validates.

Expected current invariant: source hash/span/quote integrity rejects the mutation.

### 2. Parallel same-slot conflict

Create two parent snapshots, one per reader, with different values for the same slot. Attempt to create a child containing both findings without a merge resolution.

Falsifier: the merge succeeds silently.

Expected current invariant: `merge_conflict_unresolved:<slot>` refuses the child.

Then preserve both findings explicitly with `PRESERVE_ALL` and a `CONTRADICTS` relation. That state should validate while retaining the disagreement.

### 3. Semantic identity boundary

Run the stronger negative control: explicitly select the misleading same-name finding.

This asks what provenance does **not** establish. The selected claim has an exact QUOTE anchor, but the mapping from those bytes to the target `slot/value` is semantic judgment.

If current Claim Graph validates and signs that explicit selection, the result is not described as a provenance failure. It establishes the narrower boundary: OpenLine can preserve the evidence and force a represented conflict to be resolved explicitly, but it does not know that the receiver chose the wrong person.

The proof also asks `verify_projection` to evaluate the selected claim under a structural receiver policy requiring the target slot, anchored claims, and QUOTE provenance. If that projection is admitted, the experiment records that semantic identity adjudication remains unearned.

### 4. Receipt binding

After the wrong selection is signed, mutate the recorded merge-resolution reason.

Falsifier: the altered state still validates against the original receipt.

Expected current invariant: the state/receipt binding fails.

## Verdicts

`PROVENANCE_OR_LINEAGE_BARRIER_FAILED`
: A claimed integrity/lineage invariant failed. This earns repair before any broader work.

`SEMANTIC_IDENTITY_GUARD_ALREADY_PRESENT`
: Current OpenLine already rejects or quarantines the misbound identity representation under the frozen structural policy.

`PROVENANCE_BARRIER_HELD_IDENTITY_SEMANTICS_UNEARNED`
: Source integrity, explicit parallel-conflict handling, and receipt binding hold, while the deliberately wrong but source-exact identity selection can still be structurally admitted. This is an external confirmation of the existing provenance boundary and a negative result for any stronger semantic-identity claim.

`INCONCLUSIVE_EXISTING_BOUNDARY`
: The observed behavior does not fit one of the preregistered branches.

## What a positive integrity result would earn

Only this:

> Current OpenLine preserves exact source/quote integrity and refuses a silent same-slot collapse across represented parallel findings; an explicit conflicting selection is bound into lineage and receipt state.

It does **not** earn “OpenLine prevents hallucinations,” “OpenLine resolves identity,” or “OpenLine makes parallel agents correct.”

If the semantic negative control is admitted, preserve that negative result too:

> Exact provenance does not establish that a slot/value identity mapping is semantically correct. A receiver can still explicitly select and sign the wrong same-name mapping.

That is a useful boundary, not wording to clean away.

## Run

```bash
python experiments/parser-provenance-cold-001/run.py --self-test
rm -rf parser-provenance-cold-artifacts
python experiments/parser-provenance-cold-001/run.py --output parser-provenance-cold-artifacts
python experiments/parser-provenance-cold-001/verify.py parser-provenance-cold-artifacts
```

The dedicated CI workflow runs the same cold probe on Python 3.11, 3.12, and 3.13. Ordinary Claim Graph CI remains unchanged and must also stay green.
