# IDENTITY-BINDING-GATE-001

This closes the exact admission gap frozen by `PARSER-PROVENANCE-COLD-001` without pretending Claim Graph is an entity-resolution engine.

Exact provenance still authenticates bytes and lineage, not semantic identity. The new receiver-owned gate requires pre-verified provenance plus frozen discriminator rules. Same-name-only evidence quarantines as `UNRESOLVED_IDENTITY`; hard conflicts deny; corroborated or authoritative mappings may commit under the receiver policy.

The agent may propose evidence. It cannot alter the policy or issue its own identity decision.

Run:

```bash
python -m unittest tests/test_identity_binding_gate.py -v
python experiments/identity-binding-gate-001/run.py
```

Expected verdict: `IDENTITY_ADMISSION_BARRIER_HELD`.

Earned claim: No identity mapping enters accepted state merely because its provenance is exact; it must also satisfy receiver-owned identity-binding rules.
