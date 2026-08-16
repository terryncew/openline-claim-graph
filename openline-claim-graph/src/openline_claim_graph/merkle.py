"""Small deterministic Merkle tree for graph-record inclusion proofs."""

from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping

from .canonical import canonical_json


EMPTY_ROOT = hashlib.sha256(b"openline.claim-graph.merkle.empty.v1").hexdigest()


class MerkleError(ValueError):
    pass


def _leaf_hash(key: str, record: Any) -> bytes:
    return hashlib.sha256(b"leaf\x00" + key.encode("utf-8") + b"\x00" + canonical_json(record)).digest()


def _node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"node\x00" + left + right).digest()


def _ordered(leaves: Iterable[tuple[str, Any]]) -> list[tuple[str, Any]]:
    ordered = sorted(leaves, key=lambda item: item[0])
    keys = [key for key, _ in ordered]
    if len(keys) != len(set(keys)):
        raise MerkleError("duplicate Merkle leaf key")
    return ordered


def merkle_root(leaves: Iterable[tuple[str, Any]]) -> str:
    ordered = _ordered(leaves)
    if not ordered:
        return EMPTY_ROOT
    level = [_leaf_hash(key, record) for key, record in ordered]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [_node_hash(level[index], level[index + 1]) for index in range(0, len(level), 2)]
    return level[0].hex()


def merkle_proof(leaves: Iterable[tuple[str, Any]], target_key: str) -> list[dict[str, str]]:
    ordered = _ordered(leaves)
    keys = [key for key, _ in ordered]
    try:
        target_index = keys.index(target_key)
    except ValueError as exc:
        raise MerkleError(f"unknown leaf key: {target_key}") from exc

    level = [_leaf_hash(key, record) for key, record in ordered]
    index = target_index
    proof: list[dict[str, str]] = []
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        if index % 2 == 0:
            sibling_index = index + 1
            side = "right"
        else:
            sibling_index = index - 1
            side = "left"
        proof.append({"side": side, "sha256": level[sibling_index].hex()})
        next_level = [_node_hash(level[position], level[position + 1]) for position in range(0, len(level), 2)]
        index //= 2
        level = next_level
    return proof


def verify_merkle_proof(
    key: str,
    record: Any,
    proof: Iterable[Mapping[str, str]],
    expected_root: str,
) -> bool:
    try:
        current = _leaf_hash(key, record)
        for step in proof:
            sibling = bytes.fromhex(str(step["sha256"]))
            side = step["side"]
            if len(sibling) != 32:
                return False
            if side == "left":
                current = _node_hash(sibling, current)
            elif side == "right":
                current = _node_hash(current, sibling)
            else:
                return False
        return current.hex() == expected_root
    except (KeyError, TypeError, ValueError):
        return False
