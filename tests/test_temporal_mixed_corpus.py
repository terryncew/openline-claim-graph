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
CASE = ROOT / "artifacts/evidence-recall-temporal/mixed-001-selectivity"
FROZEN_ENGINE_SHA256 = {
    "src/openline_claim_graph/temporal_holdout.py": "bc8f0011d65cb1c2c728ef374ebb82b86c3c08657e9919427ff5d80b2707886a",
    "src/openline_claim_graph/comparative_benchmark.py": "6c04e9e021cbc1c01aae78606acc6cd41393c99673185e1e8e3ee4ccaa06e4b1",
    "src/openline_claim_graph/impact.py": "1757340f69e919ff68d3cdfe4265fc1ac330bc99ff5bcd20b69058fa846905a2",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class TemporalMixedCorpusTests(unittest.TestCase):
    def test_mixed_real_corpus_records_selectivity_below_promotion_bar(self):
        summary = json.loads((CASE / "summary.json").read_text(encoding="utf-8"))
        score = json.loads((CASE / "score.json").read_text(encoding="utf-8"))
        promotion = json.loads((CASE / "promotion-result.json").read_text(encoding="utf-8"))
        verification = json.loads((CASE / "independent-verification.json").read_text(encoding="utf-8"))

        self.assertEqual("MIXED_TEMPORAL_SELECTIVITY_CORPUS_RUN_BELOW_PROMOTION_BAR", summary["status"])
        self.assertEqual(3, summary["reopen_gold"])
        self.assertEqual(1, summary["no_reopen_gold"])
        self.assertEqual(2, summary["direct_reopenings_caught"])
        self.assertEqual(1, summary["direct_missed_reopenings"])
        self.assertEqual(3, summary["review_all_reopenings_caught"])
        self.assertEqual(4, summary["review_all_review_load"])
        self.assertEqual(1, summary["review_all_unnecessary_reviews"])
        self.assertEqual(3, summary["evidence_recall_reopenings_caught"])
        self.assertEqual(0, summary["evidence_recall_missed_reopenings"])
        self.assertEqual(3, summary["evidence_recall_review_load"])
        self.assertEqual(0, summary["evidence_recall_unnecessary_reviews"])
        self.assertEqual(1, summary["evidence_recall_reviewer_savings_vs_review_all"])
        self.assertEqual(2500, summary["evidence_recall_review_load_reduction_basis_points"])
        self.assertEqual(10000, summary["evidence_recall_reconsideration_recall_basis_points"])
        self.assertEqual("NO_PROMOTION", promotion["verdict"])
        self.assertEqual(["minimum_review_load_reduction"], promotion["failed_conditions"])
        self.assertEqual(10000, score["metrics"]["EVIDENCE_RECALL"]["reconsideration_precision"]["basis_points"])
        self.assertEqual("PASS", verification["disposition"])
        self.assertGreaterEqual(verification["check_count"], 50)

    def test_builder_is_deterministic_and_engine_stays_frozen(self):
        for relative, expected in FROZEN_ENGINE_SHA256.items():
            self.assertEqual(expected, sha256_file(ROOT / relative), relative)

        with tempfile.TemporaryDirectory(prefix="temporal-mixed-001-") as temporary:
            output = Path(temporary) / "case"
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/build_mixed_temporal_selectivity_corpus.py"),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                env=env,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for relative in (
                "pack.json",
                "authority.json",
                "promotion-policy.json",
                "future-seal.private.json",
                "gold.private.json",
                "predictions.json",
                "score.json",
                "promotion-result.json",
                "custody.json",
                "summary.json",
                "REPORT.md",
                "source-evidence/narayan-pre-cutoff.json",
                "source-evidence/narayan-trigger.json",
                "source-evidence/narayan-later.private.json",
            ):
                self.assertEqual((CASE / relative).read_bytes(), (output / relative).read_bytes(), relative)

    def test_independent_verifier_reproduces_current_artifact(self):
        with tempfile.TemporaryDirectory(prefix="temporal-mixed-verify-") as temporary:
            output = Path(temporary) / "verification.json"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/verify_mixed_temporal_selectivity_corpus.py"),
                    "--artifact",
                    str(CASE),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(
                json.loads((CASE / "independent-verification.json").read_text(encoding="utf-8")),
                json.loads(output.read_text(encoding="utf-8")),
            )


if __name__ == "__main__":
    unittest.main()
