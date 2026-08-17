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
CASE = ROOT / "artifacts/evidence-recall-temporal/real-001-shah-iron"
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


class TemporalRealCaseTests(unittest.TestCase):
    def test_first_real_case_records_no_selectivity_advantage(self):
        summary = json.loads((CASE / "summary.json").read_text(encoding="utf-8"))
        score = json.loads((CASE / "score.json").read_text(encoding="utf-8"))
        verification = json.loads((CASE / "independent-verification.json").read_text(encoding="utf-8"))

        self.assertEqual("REAL_TEMPORAL_CASE_001_RUN_NO_SELECTIVITY_ADVANTAGE", summary["status"])
        self.assertTrue(summary["engine_unchanged"])
        self.assertEqual(1, summary["direct_review_load"])
        self.assertEqual(1, summary["direct_missed_reopenings"])
        self.assertEqual(2, summary["review_all_review_load"])
        self.assertEqual(2, summary["evidence_recall_review_load"])
        self.assertEqual(0, summary["evidence_recall_missed_reopenings"])
        self.assertEqual(0, summary["evidence_recall_reviewer_savings_vs_review_all"])
        self.assertEqual(2, score["metrics"]["EVIDENCE_RECALL"]["hard_quarantine_load"])
        self.assertEqual(0, score["metrics"]["EVIDENCE_RECALL"]["unnecessary_reviews"])
        self.assertEqual("PASS", verification["disposition"])
        self.assertTrue(verification["valid"])
        self.assertGreaterEqual(verification["check_count"], 36)

    def test_first_real_case_builder_is_deterministic_and_engine_is_frozen(self):
        for relative, expected in FROZEN_ENGINE_SHA256.items():
            self.assertEqual(expected, sha256_file(ROOT / relative), relative)

        with tempfile.TemporaryDirectory(prefix="temporal-real-001-") as temporary:
            output = Path(temporary) / "case"
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/build_real_temporal_case_shah_iron.py"),
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
                "future-seal.private.json",
                "gold.private.json",
                "predictions.json",
                "score.json",
                "custody.json",
                "summary.json",
                "REPORT.md",
                "source-evidence/pre-cutoff.json",
                "source-evidence/trigger.json",
                "source-evidence/later.private.json",
            ):
                self.assertEqual(
                    (CASE / relative).read_bytes(),
                    (output / relative).read_bytes(),
                    relative,
                )


if __name__ == "__main__":
    unittest.main()
