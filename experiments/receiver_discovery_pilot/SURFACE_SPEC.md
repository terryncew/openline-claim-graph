# Frozen Receiver-Surface Specification

This specification isolates extraction and structure without pretending the three arms are visually identical.

## Shared frame

Every arm uses the same:

- source packet, document order, paragraph identifiers, typography, width, and source-navigation controls;
- neutral receiver instructions;
- case time limit;
- response form and answer cap;
- device class declared in the pack manifest;
- absence of product names, logos, condition labels, cryptographic metadata, or claims about which format is advanced.

The aid appears beside or before the common source packet in the same location for all arms. Raw JSON, command-line output, signature details, and internal record hashes are not receiver surfaces.

## Arm A — ordinary summary

- Generated directly from the source packet in a fresh context.
- Uses the frozen baseline prompt and predeclared model/tool, token, time, and human-edit budgets.
- Written as ordinary prose with source paragraph citations permitted but not required beyond the frozen prompt.
- Cannot use the claim inventory, relation inventory, private key, or resolving document.
- Receives no manual factual improvement after the other arms are viewed.

Arm A is the realistic baseline. Its content need not equal Arms B and C.

## Shared extraction for Arms B and C

The key-blind extraction pass emits:

- admitted claim identifiers and plain-language claim text;
- claim type;
- source document and paragraph references;
- admitted relation identifiers, endpoints, and plain-language relation label;
- disclosed ambiguity or inference status.

The extraction prompt, model/tool, settings, token budget, human-review allowance, and every manual edit are locked and reported. Manual review may enforce the declared schema and source anchoring; it may not use the hidden key to add the desired fault line.

## Arm B — extraction rendered as prose

- Contains every claim and relation admitted to Arm C.
- Expresses relations as complete prose sentences rather than edge lists or diagrams.
- Preserves the same source references and ambiguity labels.
- Adds no substantive claim, relation, ordering hint, emphasis, or conclusion absent from Arm C.

## Arm C — extraction rendered as graph

- Contains the identical claim and relation inventory as Arm B.
- Shows claims as nodes and relations as labeled directed edges.
- Uses no truth, quality, importance, confidence, coherence, or ranking score.
- May group nodes only by mechanically shared source or declared claim type. It may not visually emphasize the hidden target.
- Uses a static, fully expanded view for the pilot; no search, filtering, or interaction unavailable to Arm B.

## Information-parity receipt for B and C

Before recruitment, a key-blind checker records:

- the canonical claim-ID set in B and C;
- the canonical relation-ID set in B and C;
- the source-reference set in B and C;
- every ambiguity/inference disclosure in B and C;
- hashes of the final surface files.

The sets must match exactly. Natural-language connective words required to render Arm B do not count as new claims, but any substantive addition does.

If parity fails after a trial begins, affected trials are invalid; the surface may not be repaired and retained in the same run.

## Usability dry run

A small, separately labeled dry run may test font size, navigation, timing, instructions, and response capture using non-study cases. Dry-run receivers and cases are excluded from Stage 1. Surface changes after the dry run require new hashes before recruitment begins.
