"""Provider-neutral frontier/open-model lane for advisory frame findings.

Network calls live outside the trusted mechanical core.  This adapter requests
schema-constrained JSON, then imports only exact source quotes into the Frame
Ledger.  Provider output is never treated as a verdict merely because it is
valid JSON.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping, Sequence

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .canonical import content_id, hash_object
from .frame import (
    ADVISORY_DEVICE_TYPES,
    create_advisory_finding,
    create_frame_review,
    detect_mechanical_frame_devices,
    evaluate_frame_ledger,
    sign_frame_record,
)


FRAME_AGENT_TASK_SCHEMA = "openline.frame-agent-task.v1"
FRAME_AGENT_OUTPUT_SCHEMA = "openline.frame-agent-output.v1"


class FrontierAdapterError(ValueError):
    """Raised when an agent endpoint fails or returns a nonconforming result."""


def proposal_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema", "role", "abstained", "findings"],
        "properties": {
            "schema": {"type": "string", "const": FRAME_AGENT_OUTPUT_SCHEMA},
            "role": {"type": "string", "const": "PROPOSER"},
            "abstained": {"type": "boolean"},
            "findings": {
                "type": "array",
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["device_type", "quote", "occurrence", "observation"],
                    "properties": {
                        "device_type": {"type": "string", "enum": list(ADVISORY_DEVICE_TYPES)},
                        "quote": {"type": "string", "minLength": 1},
                        "occurrence": {"type": "integer", "minimum": 1},
                        "observation": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    }


def review_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema", "role", "finding_id", "verdict", "rationale"],
        "properties": {
            "schema": {"type": "string", "const": FRAME_AGENT_OUTPUT_SCHEMA},
            "role": {"type": "string", "const": "REVIEWER"},
            "finding_id": {"type": "string", "minLength": 1},
            "verdict": {"type": "string", "enum": ["CONFIRM", "CHALLENGE", "ABSTAIN"]},
            "rationale": {"type": "string", "minLength": 1},
        },
    }


def create_proposal_task(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": FRAME_AGENT_TASK_SCHEMA,
        "role": "PROPOSER",
        "source": {
            "source_id": source["source_id"],
            "locator": source.get("locator"),
            "content": source["content"],
        },
        "allowed_device_types": list(ADVISORY_DEVICE_TYPES),
        "instructions": [
            "Return only findings anchored to a verbatim quote from the supplied surface.",
            "Abstain when the surface is insufficient.",
            "Do not issue truth, bias-score, fairness, propaganda, rationalization, or intent verdicts.",
            "A finding is a proposal for independent review, not an accepted conclusion.",
        ],
        "output_schema": proposal_output_schema(),
    }


def create_review_task(source: Mapping[str, Any], finding: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": FRAME_AGENT_TASK_SCHEMA,
        "role": "REVIEWER",
        "source": {
            "source_id": source["source_id"],
            "locator": source.get("locator"),
            "content": source["content"],
        },
        "finding": dict(finding),
        "instructions": [
            "Review the proposed interpretation against only the supplied surface.",
            "CHALLENGE if the device is not supported by the exact surface or exceeds its scope.",
            "ABSTAIN when the surface is insufficient.",
            "Agreement does not turn an advisory interpretation into a truth or intent verdict.",
        ],
        "output_schema": review_output_schema(),
    }


def _validate_exact_keys(value: Mapping[str, Any], required: set[str]) -> None:
    if set(value) != required:
        raise FrontierAdapterError(
            f"output fields differ from contract: expected {sorted(required)}, got {sorted(value)}"
        )


def import_proposal_output(
    source: Mapping[str, Any], output: Mapping[str, Any], *, asserted_by: str
) -> list[dict[str, Any]]:
    _validate_exact_keys(output, {"schema", "role", "abstained", "findings"})
    if output.get("schema") != FRAME_AGENT_OUTPUT_SCHEMA or output.get("role") != "PROPOSER":
        raise FrontierAdapterError("proposal output schema or role is invalid")
    if not isinstance(output.get("abstained"), bool) or not isinstance(output.get("findings"), list):
        raise FrontierAdapterError("proposal output types are invalid")
    if output["abstained"] and output["findings"]:
        raise FrontierAdapterError("an abstaining proposer cannot emit findings")
    if len(output["findings"]) > 8:
        raise FrontierAdapterError("proposal answer cap exceeded")
    imported = []
    for item in output["findings"]:
        if not isinstance(item, Mapping):
            raise FrontierAdapterError("proposal finding must be an object")
        _validate_exact_keys(item, {"device_type", "quote", "occurrence", "observation"})
        if item["device_type"] not in ADVISORY_DEVICE_TYPES:
            raise FrontierAdapterError("proposal device type is not allowed")
        if not isinstance(item["occurrence"], int) or isinstance(item["occurrence"], bool):
            raise FrontierAdapterError("proposal occurrence must be an integer")
        try:
            finding = create_advisory_finding(
                source,
                quote=str(item["quote"]),
                occurrence=int(item["occurrence"]),
                device_type=str(item["device_type"]),
                observation=str(item["observation"]),
                asserted_by=asserted_by,
            )
        except ValueError as exc:
            raise FrontierAdapterError(f"proposal quote could not be anchored: {exc}") from exc
        imported.append(finding)
    return sorted(imported, key=lambda item: str(item["finding_id"]))


def import_review_output(output: Mapping[str, Any], *, reviewer_id: str) -> dict[str, Any]:
    _validate_exact_keys(output, {"schema", "role", "finding_id", "verdict", "rationale"})
    if output.get("schema") != FRAME_AGENT_OUTPUT_SCHEMA or output.get("role") != "REVIEWER":
        raise FrontierAdapterError("review output schema or role is invalid")
    return create_frame_review(
        finding_id=str(output["finding_id"]),
        reviewer_id=reviewer_id,
        verdict=str(output["verdict"]),
        rationale=str(output["rationale"]),
    )


def _post_json(
    url: str,
    payload: Mapping[str, Any],
    *,
    api_key: str | None,
    timeout_seconds: int,
) -> Mapping[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise FrontierAdapterError(f"agent endpoint failed: {exc}") from exc
    if not isinstance(data, Mapping):
        raise FrontierAdapterError("agent endpoint returned a non-object response")
    return data


def _parse_strict_json(text: str) -> Mapping[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FrontierAdapterError("model output is not strict JSON") from exc
    if not isinstance(value, Mapping):
        raise FrontierAdapterError("model output must be one JSON object")
    return value


def call_openai_compatible(
    *,
    base_url: str,
    model: str,
    task: Mapping[str, Any],
    output_schema: Mapping[str, Any],
    api_key: str | None = None,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    """Call a chat-completions endpoint served by vLLM/SGLang/llama.cpp or a provider."""

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are one bounded component in a receiver-owned audit. Return only the requested "
                    "JSON. Abstain rather than inventing source text or exceeding the declared scope."
                ),
            },
            {"role": "user", "content": json.dumps(task, ensure_ascii=False, sort_keys=True)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "openline_frame_agent_output", "strict": True, "schema": output_schema},
        },
    }
    data = _post_json(
        base_url.rstrip("/") + "/chat/completions",
        payload,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
    )
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise FrontierAdapterError("chat response does not contain message content") from exc
    if isinstance(content, Mapping):
        result = dict(content)
    elif isinstance(content, str):
        result = dict(_parse_strict_json(content))
    else:
        raise FrontierAdapterError("chat message content has an unsupported type")
    return {
        "result": result,
        "execution": {
            "api_style": "openai_compatible_chat_completions",
            "model": model,
            "task_hash": hash_object(task),
            "response_id": data.get("id"),
            "usage": data.get("usage"),
        },
    }


def _responses_text(data: Mapping[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return str(data["output_text"])
    pieces: list[str] = []
    for output in data.get("output", []):
        if not isinstance(output, Mapping):
            continue
        for content in output.get("content", []):
            if isinstance(content, Mapping) and content.get("type") == "output_text":
                pieces.append(str(content.get("text", "")))
    if not pieces:
        raise FrontierAdapterError("Responses API output contains no output_text")
    return "".join(pieces)


def call_openai_responses(
    *,
    base_url: str,
    model: str,
    task: Mapping[str, Any],
    output_schema: Mapping[str, Any],
    api_key: str,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    """Call the official Responses API with strict Structured Outputs and storage disabled."""

    payload = {
        "model": model,
        "store": False,
        "input": [
            {
                "role": "developer",
                "content": (
                    "You are one bounded component in a receiver-owned audit. Return only the requested "
                    "JSON. Abstain rather than inventing source text or exceeding the declared scope."
                ),
            },
            {"role": "user", "content": json.dumps(task, ensure_ascii=False, sort_keys=True)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "openline_frame_agent_output",
                "strict": True,
                "schema": output_schema,
            }
        },
    }
    data = _post_json(
        base_url.rstrip("/") + "/responses",
        payload,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
    )
    result = dict(_parse_strict_json(_responses_text(data)))
    return {
        "result": result,
        "execution": {
            "api_style": "openai_responses",
            "model": model,
            "task_hash": hash_object(task),
            "response_id": data.get("id"),
            "usage": data.get("usage"),
        },
    }


def run_autonomous_frame_pipeline(
    *,
    source: Mapping[str, Any],
    policy: Mapping[str, Any],
    proposer_id: str,
    reviewer_ids: Sequence[str],
    private_keys: Mapping[str, Ed25519PrivateKey],
    agent_call: Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]],
    issued_at: str,
    absence_sets: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Run proposal and non-self review unattended, then apply receiver policy.

    ``agent_call`` is the untrusted execution boundary.  It receives an actor
    id, task, and output schema and returns a model result.  Exact quote import,
    signatures, reviewer separation, quorum, and the final report are handled
    after that boundary.
    """

    if proposer_id in reviewer_ids:
        raise FrontierAdapterError("proposer cannot also be configured as a reviewer")
    if len(reviewer_ids) != len(set(reviewer_ids)):
        raise FrontierAdapterError("reviewer identities must be unique")
    required_actors = {proposer_id, *reviewer_ids}
    missing_keys = required_actors - set(private_keys)
    if missing_keys:
        raise FrontierAdapterError(f"private execution keys missing: {sorted(missing_keys)}")

    execution_log: list[dict[str, Any]] = []
    mechanical = detect_mechanical_frame_devices(source, absence_sets=absence_sets)
    proposal_task = create_proposal_task(source)
    proposal_output = dict(agent_call(proposer_id, proposal_task, proposal_output_schema()))
    execution_log.append(
        {
            "actor_id": proposer_id,
            "role": "PROPOSER",
            "task_hash": hash_object(proposal_task),
            "output_hash": hash_object(proposal_output),
        }
    )
    inferred = import_proposal_output(source, proposal_output, asserted_by=proposer_id)
    finding_attestations = [
        sign_frame_record(
            finding,
            record_type="finding",
            record_id=str(finding["finding_id"]),
            signer_id=proposer_id,
            private_key=private_keys[proposer_id],
            issued_at=issued_at,
        )
        for finding in inferred
    ]

    reviews: list[dict[str, Any]] = []
    review_attestations: list[dict[str, Any]] = []
    for finding in inferred:
        for reviewer_id in reviewer_ids:
            task = create_review_task(source, finding)
            output = dict(agent_call(reviewer_id, task, review_output_schema()))
            execution_log.append(
                {
                    "actor_id": reviewer_id,
                    "role": "REVIEWER",
                    "finding_id": finding["finding_id"],
                    "task_hash": hash_object(task),
                    "output_hash": hash_object(output),
                }
            )
            review = import_review_output(output, reviewer_id=reviewer_id)
            reviews.append(review)
            review_attestations.append(
                sign_frame_record(
                    review,
                    record_type="review",
                    record_id=str(review["review_id"]),
                    signer_id=reviewer_id,
                    private_key=private_keys[reviewer_id],
                    issued_at=issued_at,
                )
            )

    findings = sorted([*mechanical, *inferred], key=lambda item: str(item["finding_id"]))
    report = evaluate_frame_ledger(
        source,
        findings,
        policy,
        finding_attestations=finding_attestations,
        reviews=reviews,
        review_attestations=review_attestations,
    )
    body = {
        "schema": "openline.autonomous-frame-run.v1",
        "source_id": source["source_id"],
        "policy_id": policy["policy_id"],
        "proposer_id": proposer_id,
        "reviewer_ids": list(reviewer_ids),
        "findings": findings,
        "finding_attestations": finding_attestations,
        "reviews": reviews,
        "review_attestations": review_attestations,
        "execution_log": execution_log,
        "report": report,
        "claim_boundary": (
            "This records an unattended receiver-policy run. Signatures bind configured execution "
            "identities to exact records; they do not establish model identity, family independence, "
            "semantic correctness, truth, intent, fairness, or reader effect."
        ),
    }
    return {"run_id": content_id("autonomous-frame-run", body), **body}
