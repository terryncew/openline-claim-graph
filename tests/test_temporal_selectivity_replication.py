from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "artifacts/evidence-recall-temporal/replication-001-selectivity"
FROZEN_ENGINE_SHA256 = {
    "src/openline_claim_graph/temporal_holdout.py": "bc8f0011d65cb1c2c728ef374ebb82b86c3c08657e9919427ff5d80b2707886a",
    "src/openline_claim_graph/comparative_benchmark.py": "6c04e9e021cbc1c01aae78606acc6cd41393c99673185e1e8e3ee4ccaa06e4b1",
    "src/openline_claim_graph/impact.py": "1757340f69e919ff68d3cdfe4265fc1ac330bc99ff5bcd20b69058fa846905a2",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    return h


class TemporalSelectivityReplicationTests(unittest.TestCase):
    def test_replication_crosses_predeclared_bar(self):
        summary = json.loads((CASE / "summary.json").read_text())
        result = json.loads((CASE / "promotion-result.json").read_text())
        metrics = json.loads((CASE / "episode-metrics.json").read_text())
        verification = json.loads((CASE / "independent-verification.json").read_text())
        self.assertEqual("TEMPORAL_SELECTIVITY_REPLICATION_PROMOTED", summary["status"])
        self.assertEqual(5, summary["episode_count"])
        self.assertEqual(14, summary["scored_targets"])
        self.assertEqual(8, summary["reopen_gold"])
        self.assertEqual(6, summary["no_reopen_gold"])
        self.assertEqual(8, summary["evidence_recall_reopenings_caught"])
        self.assertEqual(0, summary["evidence_recall_missed_reopenings"])
        self.assertEqual(14, summary["review_all_review_load"])
        self.assertEqual(8, summary["evidence_recall_review_load"])
        self.assertEqual(6, summary["evidence_recall_reviewer_savings_vs_review_all"])
        self.assertEqual(4285, summary["evidence_recall_review_load_reduction_basis_points"])
        self.assertEqual(10000, summary["evidence_recall_reconsideration_recall_basis_points"])
        self.assertEqual(4, summary["episodes_with_recurring_savings"])
        self.assertEqual(5000, metrics["median_episode_review_savings_basis_points"])
        self.assertEqual("PROMOTION", result["verdict"])
        self.assertEqual([], result["failed_conditions"])
        self.assertEqual("PASS", verification["disposition"])
        self.assertGreaterEqual(verification["check_count"], 100)

    def test_kataoka_aggregate_is_not_promoted_to_case_level_gold(self):
        admission = json.loads((CASE / "source-evidence/kataoka-case-level-admission.json").read_text())
        self.assertEqual(0, admission["scored_rows_admitted"])
        self.assertEqual(335, admission["aggregate_facts"]["pre_retraction_reviews_or_guidelines"])
        self.assertEqual(239, admission["aggregate_facts"]["included_later_retracted_rct"])

    def test_builder_is_deterministic_and_engine_is_frozen(self):
        for rel, expected in FROZEN_ENGINE_SHA256.items():
            self.assertEqual(expected, sha256_file(ROOT / rel), rel)
        with tempfile.TemporaryDirectory(prefix="temporal-replication-") as temp:
            out = Path(temp) / "case"
            env = os.environ.copy(); env["PYTHONPATH"] = str(ROOT / "src")
            subprocess.run([sys.executable, str(ROOT / "scripts/build_temporal_selectivity_replication_corpus.py"), "--output", str(out)], cwd=ROOT, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for rel in (
                "pack.json", "authority.json", "future-seal.private.json", "promotion-policy.json",
                "predictions.json", "gold.private.json", "score.json", "episode-metrics.json",
                "promotion-result.json", "target-ledger.json", "custody.json", "summary.json",
                "REPORT.md", "POINT_BECAUSE_BUT_SO.md", "POINT_BECAUSE_BUT_SO.audit.json", "source-evidence/kataoka-case-level-admission.json",
            ):
                self.assertEqual((CASE / rel).read_bytes(), (out / rel).read_bytes(), rel)


    def test_human_contract_is_root_canonical_and_auditable(self):
        contract = (ROOT / "HUMAN_CONTRACT.md").read_text(encoding="utf-8")
        self.assertIn("POINT", contract)
        self.assertIn("BECAUSE", contract)
        self.assertIn("BUT", contract)
        self.assertIn("SO", contract)
        audit = json.loads((CASE / "POINT_BECAUSE_BUT_SO.audit.json").read_text(encoding="utf-8"))
        self.assertTrue(all(audit["constraints"].values()))
        self.assertTrue(all(audit["lines"][name]["trace"] for name in ("POINT", "BECAUSE", "BUT", "SO")))

    def test_independent_verifier_reproduces_artifact(self):
        with tempfile.TemporaryDirectory(prefix="temporal-replication-verify-") as temp:
            out = Path(temp) / "verification.json"
            subprocess.run([sys.executable, str(ROOT / "scripts/verify_temporal_selectivity_replication_corpus.py"), "--artifact", str(CASE), "--output", str(out)], cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(json.loads((CASE / "independent-verification.json").read_text()), json.loads(out.read_text()))


if __name__ == "__main__":
    unittest.main()
