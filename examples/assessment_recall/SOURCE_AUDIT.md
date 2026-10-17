# Initial source audit

Base: `30a3ee1316d0b388fd4f20fa49e25556fef1985b`.

Reuse `graph.py` (sources, claims, SUPPORTS, snapshots), `receipts.py`
(pinned Ed25519 snapshot receipts), and `impact.py` (receiver admission,
source-status events, deterministic classifications, report replay). These are
existing Evidence Recall APIs; stable 0.5.2 claims remain unchanged. A required
prerequisite is conjunctive; independently sufficient SUPPORTS edges are
alternatives. Use those semantics without modifying the engine.

Standing Recall (`docs/STANDING_RECALL.md`) is experimental. Neither its code
nor its claimed repair-surface advantage is imported. Prospective Decision
Recall's frozen protocol explicitly identifies dependency capture as an
unresolved upstream assumption. This example is synthetic, authored with
knowledge of the event, and is not a prospective run or promotion evidence.
No frozen instrument or ledger will be changed.

Minimal glue: put ordinary JSON records in existing signed source/snapshot
receipts; pin three local test identities; check actor permissions, exact
configuration and record bindings; translate receiver-authenticated change
scope into an existing source-status event; record current review status;
compare with a flat dependency table; render one HTML page. This is an example
application convention, not a new interoperability protocol. Core rendering
is available, but an application-specific page avoids requiring the risk owner
to interpret graph vocabulary. The exported graph report remains inspectable.

Signatures establish recorded authorship and integrity, not truth. Receiver
acceptance establishes authority. Changed configuration is not proof of harm.
Current-head freshness is provided by a receiver-held checkpoint in this local
workflow; offline records alone cannot prove absence of later events.
