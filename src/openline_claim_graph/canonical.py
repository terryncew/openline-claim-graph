"""Restricted canonical JSON helpers.

This is deliberately smaller than JSON Canonicalization Scheme (JCS).  It is
an internal prototype profile: UTF-8, NFC-normalized strings, sorted object
keys, compact separators, integers only, and no non-JSON values.  The profile
is named in every graph receipt so a receiver never mistakes these bytes for a
different canonicalization standard.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any


PROFILE = "openline.restricted-canonical-json.v1"


class CanonicalizationError(ValueError):
    """Raised when a value falls outside the restricted canonical profile."""


def _normalize(value: Any, path: str = "$") -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        raise CanonicalizationError(f"{path}: floating-point values are forbidden")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, (list, tuple)):
        return [_normalize(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            if not isinstance(raw_key, str):
                raise CanonicalizationError(f"{path}: object keys must be strings")
            key = unicodedata.normalize("NFC", raw_key)
            if key in normalized:
                raise CanonicalizationError(f"{path}: duplicate key after NFC normalization: {key!r}")
            normalized[key] = _normalize(raw_value, f"{path}.{key}")
        return normalized
    raise CanonicalizationError(f"{path}: unsupported value type {type(value).__name__}")


def canonical_value(value: Any) -> Any:
    """Return the JSON-safe, NFC-normalized representation of ``value``."""

    return _normalize(value)


def canonical_json(value: Any) -> bytes:
    """Encode a value under the prototype's declared canonical profile."""

    return json.dumps(
        canonical_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_object(value: Any) -> str:
    return sha256_hex(canonical_json(value))


def content_id(namespace: str, value: Any) -> str:
    if not namespace or ":" in namespace:
        raise ValueError("namespace must be a non-empty token without ':'")
    return f"{namespace}:sha256:{hash_object(value)}"
