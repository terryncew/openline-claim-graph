from __future__ import annotations

import copy
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from openline_claim_graph.frame import (
    FRAME_RULESET_HASH,
    FrameValidationError,
    create_advisory_finding,
    create_frame_finding,
    create_frame_policy,
    create_frame_review,
    detect_mechanical_frame_devices,
    evaluate_frame_ledger,
    sign_frame_record,
    validate_frame_finding,
    verify_frame_attestation,
    verify_frame_report,
)
from openline_claim_graph.frame_review import FrameReviewError, render_frame_ledger
from openline_claim_graph.frontier import (
    FRAME_AGENT_OUTPUT_SCHEMA,
    FrontierAdapterError,
    call_openai_compatible,
    call_openai_responses,
    create_proposal_task,
    import_proposal_output,
    proposal_output_schema,
    run_autonomous_frame_pipeline,
)
from openline_claim_graph.graph import build_source
from openline_claim_graph.receipts import private_key_from_hex, public_key_hex


HEADLINE = (
    "Contradicting public statements, Trump took secret flight from Turkey amid Iranian threat"
)
ABSENCE_SETS = [
    {
        "set_id": "falsity_or_deception",
        "terms": ["false", "falsely", "misleading", "lie", "lied", "lying"],
    },
    {
        "set_id": "named_institutional_attribution",
        "terms": ["White House", "administration", "officials", "spokesperson"],
    },
]


class FrameLedgerTest(unittest.TestCase):
    def setUp(self):
        self.source = build_source(HEADLINE, locator="fixture:headline")
        self.findings = detect_mechanical_frame_devices(
            self.source,
            absence_sets=ABSENCE_SETS,
        )
        self.policy = create_frame_policy()

    def test_mechanical_detector_reproduces_seven_scoped_devices(self):
        self.assertEqual(7, len(self.findings))
        types = [item["device_type"] for item in self.findings]
        self.assertEqual(2, types.count("DECLARED_TERM_SET_ABSENCE"))
        self.assertIn("EPISTEMIC_LEXEME", types)
        self.assertIn("CONTEXT_CUE", types)
        self.assertIn("LOCAL_ATTRIBUTION_PATTERN_ABSENCE", types)
        for finding in self.findings:
            self.assertTrue(validate_frame_finding(finding, self.source)["valid"])

    def test_unicode_offsets_are_utf8_bytes(self):
        source = build_source("Éditorial: falsely framed.")
        findings = detect_mechanical_frame_devices(source)
        falsity = next(item for item in findings if item["parameters"].get("term") == "falsely")
        self.assertEqual(len("Éditorial: ".encode("utf-8")), falsity["anchors"][0]["span"]["start"])
        self.assertTrue(validate_frame_finding(falsity, source)["valid"])

    def test_absence_finding_cannot_survive_when_term_is_present(self):
        absence = next(
            item
            for item in self.findings
            if item["parameters"].get("set_id") == "falsity_or_deception"
        )
        changed_source = build_source(HEADLINE + " False.")
        tampered = copy.deepcopy(absence)
        tampered["source_id"] = changed_source["source_id"]
        tampered["anchors"][0]["source_id"] = changed_source["source_id"]
        tampered["anchors"][0]["span"]["end"] = len(changed_source["content"].encode("utf-8"))
        from openline_claim_graph.canonical import content_id, sha256_hex

        tampered["anchors"][0]["quote_sha256"] = sha256_hex(changed_source["content"].encode("utf-8"))
        body = dict(tampered)
        body.pop("finding_id")
        tampered["finding_id"] = content_id("frame-finding", body)
        check = validate_frame_finding(tampered, changed_source)
        self.assertFalse(check["valid"])
        self.assertIn("frame_finding_mechanical_reproduction_failed", check["errors"])

    def test_mechanical_report_and_renderer_are_reproducible(self):
        report = evaluate_frame_ledger(self.source, self.findings, self.policy)
        self.assertEqual(7, report["summary"]["established"])
        self.assertEqual(0, report["summary"]["advisory"])
        self.assertTrue(verify_frame_report(report, self.source, self.findings, self.policy)["valid"])
        html = render_frame_ledger(
            report=report,
            source=self.source,
            findings=self.findings,
            policy=self.policy,
        )
        self.assertIn("NOT A BIAS OR TRUTH VERDICT", html)
        self.assertIn("Contradicting", html)
        self.assertIn(FRAME_RULESET_HASH, html)

    def test_renderer_fails_closed_on_report_tamper(self):
        report = evaluate_frame_ledger(self.source, self.findings, self.policy)
        report["summary"]["established"] = 99
        with self.assertRaises(FrameReviewError):
            render_frame_ledger(
                report=report,
                source=self.source,
                findings=self.findings,
                policy=self.policy,
            )

    def test_prohibited_verdict_is_rejected(self):
        finding = create_frame_finding(
            self.source,
            device_type="PROPAGANDA_VERDICT",
            layer="INFERRED",
            observation="A prohibited verdict.",
            asserted_by="model:a",
            start=0,
            end=13,
            rule_id="MODEL_PROPOSAL.v1",
        )
        check = validate_frame_finding(finding, self.source)
        self.assertFalse(check["valid"])
        self.assertIn("frame_finding_prohibited_verdict:PROPAGANDA_VERDICT", check["errors"])


class AutonomousFramePolicyTest(unittest.TestCase):
    def setUp(self):
        self.source = build_source(HEADLINE)
        self.proposer_key = private_key_from_hex("21" * 32)
        self.r1_key = private_key_from_hex("22" * 32)
        self.r2_key = private_key_from_hex("23" * 32)
        self.human_key = private_key_from_hex("24" * 32)
        self.finding = create_advisory_finding(
            self.source,
            quote="Contradicting public statements",
            device_type="FACT_STATUS_OMISSION",
            observation=(
                "The surface uses conflict language without itself stating the public statements' factual status."
            ),
            asserted_by="agent:proposer",
        )
        self.finding_attestation = sign_frame_record(
            self.finding,
            record_type="finding",
            record_id=self.finding["finding_id"],
            signer_id="agent:proposer",
            private_key=self.proposer_key,
            issued_at="2026-08-16T12:00:00Z",
        )

    def actor(self, actor_id, model_id, family, key, kind="AI"):
        return {
            "actor_id": actor_id,
            "model_id": model_id,
            "family": family,
            "kind": kind,
            "public_key": public_key_hex(key),
        }

    def policy(self, *, family2="family-b", human_mode="OPTIONAL", reviewers=None):
        reviewer_rows = reviewers or [
            self.actor("agent:r1", "model-r1", "family-a", self.r1_key),
            self.actor("agent:r2", "model-r2", family2, self.r2_key),
        ]
        return create_frame_policy(
            human_mode=human_mode,
            proposers=[self.actor("agent:proposer", "model-p", "family-p", self.proposer_key)],
            reviewers=reviewer_rows,
        )

    def signed_review(self, reviewer_id, key, verdict="CONFIRM"):
        review = create_frame_review(
            finding_id=self.finding["finding_id"],
            reviewer_id=reviewer_id,
            verdict=verdict,
            rationale=f"Fixture {verdict.lower()} review.",
        )
        attestation = sign_frame_record(
            review,
            record_type="review",
            record_id=review["review_id"],
            signer_id=reviewer_id,
            private_key=key,
            issued_at="2026-08-16T12:01:00Z",
        )
        return review, attestation

    def test_two_signed_distinct_family_reviews_admit_only_as_advisory(self):
        r1, a1 = self.signed_review("agent:r1", self.r1_key)
        r2, a2 = self.signed_review("agent:r2", self.r2_key)
        report = evaluate_frame_ledger(
            self.source,
            [self.finding],
            self.policy(),
            finding_attestations=[self.finding_attestation],
            reviews=[r1, r2],
            review_attestations=[a1, a2],
        )
        self.assertEqual(1, report["summary"]["advisory"])
        self.assertEqual("ADVISORY_ADMITTED", report["classifications"]["advisory"][0]["disposition"])

    def test_same_family_does_not_satisfy_independence_quorum(self):
        r1, a1 = self.signed_review("agent:r1", self.r1_key)
        r2, a2 = self.signed_review("agent:r2", self.r2_key)
        report = evaluate_frame_ledger(
            self.source,
            [self.finding],
            self.policy(family2="family-a"),
            finding_attestations=[self.finding_attestation],
            reviews=[r1, r2],
            review_attestations=[a1, a2],
        )
        self.assertEqual(1, report["summary"]["unadmitted"])

    def test_one_signed_challenge_blocks(self):
        r1, a1 = self.signed_review("agent:r1", self.r1_key)
        r2, a2 = self.signed_review("agent:r2", self.r2_key, verdict="CHALLENGE")
        report = evaluate_frame_ledger(
            self.source,
            [self.finding],
            self.policy(),
            finding_attestations=[self.finding_attestation],
            reviews=[r1, r2],
            review_attestations=[a1, a2],
        )
        self.assertEqual(1, report["summary"]["blocked"])

    def test_human_required_policy_stays_unadmitted_without_human(self):
        r1, a1 = self.signed_review("agent:r1", self.r1_key)
        r2, a2 = self.signed_review("agent:r2", self.r2_key)
        report = evaluate_frame_ledger(
            self.source,
            [self.finding],
            self.policy(human_mode="REQUIRED"),
            finding_attestations=[self.finding_attestation],
            reviews=[r1, r2],
            review_attestations=[a1, a2],
        )
        self.assertEqual(1, report["summary"]["unadmitted"])

    def test_self_approval_is_rejected_even_when_policy_pins_actor_in_both_roles(self):
        policy = create_frame_policy(
            advisory_min_confirmations=1,
            advisory_min_distinct_families=1,
            proposers=[self.actor("agent:proposer", "model-p", "family-p", self.proposer_key)],
            reviewers=[self.actor("agent:proposer", "model-p", "family-p", self.proposer_key)],
        )
        review, attestation = self.signed_review("agent:proposer", self.proposer_key)
        with self.assertRaises(FrameValidationError):
            evaluate_frame_ledger(
                self.source,
                [self.finding],
                policy,
                finding_attestations=[self.finding_attestation],
                reviews=[review],
                review_attestations=[attestation],
            )

    def test_signature_tamper_is_rejected(self):
        tampered = copy.deepcopy(self.finding_attestation)
        tampered["proof"]["signature"] = "00" * 64
        check = verify_frame_attestation(
            tampered,
            self.finding,
            expected_public_key=public_key_hex(self.proposer_key),
        )
        self.assertFalse(check["valid"])


class _AgentHandler(BaseHTTPRequestHandler):
    response_payload = {}
    requests = []

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        type(self).requests.append((self.path, payload))
        body = json.dumps(type(self).response_payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class FrontierAdapterTest(unittest.TestCase):
    def setUp(self):
        _AgentHandler.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _AgentHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}/v1"
        self.source = build_source(HEADLINE)
        self.task = create_proposal_task(self.source)
        self.output = {
            "schema": FRAME_AGENT_OUTPUT_SCHEMA,
            "role": "PROPOSER",
            "abstained": False,
            "findings": [
                {
                    "device_type": "FACT_STATUS_OMISSION",
                    "quote": "Contradicting public statements",
                    "occurrence": 1,
                    "observation": "Conflict is named; factual status is not stated in this headline.",
                }
            ],
        }

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_openai_compatible_adapter_requests_schema_and_imports_exact_quote(self):
        _AgentHandler.response_payload = {
            "id": "chat-fixture",
            "choices": [{"message": {"content": json.dumps(self.output)}}],
            "usage": {"total_tokens": 42},
        }
        response = call_openai_compatible(
            base_url=self.base,
            model="open-model-fixture",
            task=self.task,
            output_schema=proposal_output_schema(),
        )
        imported = import_proposal_output(self.source, response["result"], asserted_by="agent:test")
        self.assertEqual(1, len(imported))
        self.assertEqual("INFERRED", imported[0]["layer"])
        path, payload = _AgentHandler.requests[0]
        self.assertEqual("/v1/chat/completions", path)
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])

    def test_official_responses_adapter_disables_storage(self):
        _AgentHandler.response_payload = {
            "id": "response-fixture",
            "output": [{"content": [{"type": "output_text", "text": json.dumps(self.output)}]}],
            "usage": {"total_tokens": 42},
        }
        response = call_openai_responses(
            base_url=self.base,
            model="frontier-fixture",
            task=self.task,
            output_schema=proposal_output_schema(),
            api_key="fixture-key",
        )
        self.assertEqual(self.output, response["result"])
        _, payload = _AgentHandler.requests[0]
        self.assertIs(payload["store"], False)
        self.assertTrue(payload["text"]["format"]["strict"])

    def test_import_rejects_unanchored_quote(self):
        bad = copy.deepcopy(self.output)
        bad["findings"][0]["quote"] = "text that is not present"
        with self.assertRaises(FrontierAdapterError):
            import_proposal_output(self.source, bad, asserted_by="agent:test")

    def test_full_unattended_pipeline_signs_and_applies_heterogeneous_quorum(self):
        proposer_key = private_key_from_hex("31" * 32)
        r1_key = private_key_from_hex("32" * 32)
        r2_key = private_key_from_hex("33" * 32)
        policy = create_frame_policy(
            proposers=[
                {
                    "actor_id": "agent:p",
                    "model_id": "open-proposer",
                    "family": "family-p",
                    "kind": "AI",
                    "public_key": public_key_hex(proposer_key),
                }
            ],
            reviewers=[
                {
                    "actor_id": "agent:r1",
                    "model_id": "open-reviewer-1",
                    "family": "family-r1",
                    "kind": "AI",
                    "public_key": public_key_hex(r1_key),
                },
                {
                    "actor_id": "agent:r2",
                    "model_id": "open-reviewer-2",
                    "family": "family-r2",
                    "kind": "AI",
                    "public_key": public_key_hex(r2_key),
                },
            ],
        )

        def fake_call(actor_id, task, schema):
            self.assertEqual("object", schema["type"])
            if task["role"] == "PROPOSER":
                return copy.deepcopy(self.output)
            return {
                "schema": FRAME_AGENT_OUTPUT_SCHEMA,
                "role": "REVIEWER",
                "finding_id": task["finding"]["finding_id"],
                "verdict": "CONFIRM",
                "rationale": f"{actor_id} confirms the bounded interpretation.",
            }

        run = run_autonomous_frame_pipeline(
            source=self.source,
            policy=policy,
            proposer_id="agent:p",
            reviewer_ids=["agent:r1", "agent:r2"],
            private_keys={"agent:p": proposer_key, "agent:r1": r1_key, "agent:r2": r2_key},
            agent_call=fake_call,
            issued_at="2026-08-16T13:00:00Z",
            absence_sets=ABSENCE_SETS,
        )
        self.assertEqual(7, run["report"]["summary"]["established"])
        self.assertEqual(1, run["report"]["summary"]["advisory"])
        self.assertEqual(3, len(run["execution_log"]))


if __name__ == "__main__":
    unittest.main()
