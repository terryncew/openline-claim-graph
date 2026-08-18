from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cohort001_script", ROOT / "scripts" / "cohort001.py")
assert SPEC and SPEC.loader
cohort001 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cohort001)


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True)
    return completed.stdout.strip()


class Cohort001Tests(unittest.TestCase):
    def test_change_set_excludes_cohort_and_generated_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            base = tmp / "base"
            candidate = tmp / "candidate"
            base.mkdir(); candidate.mkdir()
            (base / "src").mkdir(); (candidate / "src").mkdir()
            (base / "src" / "x.py").write_text("x = 1\n", encoding="utf-8")
            (candidate / "src" / "x.py").write_text("x = 2\n", encoding="utf-8")
            (base / "MANIFEST.json").write_text("old\n", encoding="utf-8")
            (candidate / "MANIFEST.json").write_text("new\n", encoding="utf-8")
            cohort = candidate / "artifacts" / "decision-recall-prospective" / "cohort-001" / "observations"
            cohort.mkdir(parents=True)
            (cohort / "d.json").write_text("{}\n", encoding="utf-8")
            patterns = ["MANIFEST.json", "EVIDENCE.json", "artifacts/decision-recall-prospective/cohort-001/**"]
            result = cohort001.change_set_from_dirs(base, candidate, patterns)
            self.assertEqual([entry["path"] for entry in result["entries"]], ["src/x.py"])

    def _make_repo(self, tmp: Path, *, frozen=False) -> Path:
        root = tmp / "repo"
        root.mkdir()
        git(root, "init", "-q")
        git(root, "config", "user.email", "test@example.com")
        git(root, "config", "user.name", "Test")
        designation = root / cohort001.DESIGNATION_REL
        designation.parent.mkdir(parents=True)
        frozen_map = {}
        if frozen:
            instrument = root / "instrument.txt"
            instrument.write_text("frozen\n", encoding="utf-8")
            frozen_map["instrument.txt"] = cohort001.sha256_file(instrument)
        designation.write_text(json.dumps({
            "schema": "openline.decision-recall-cohort-designation.v1",
            "cohort_id": "decision-recall-cohort-001",
            "minimum_real_accepted_decisions": 30,
            "acceptable_capture_timing_sources": ["MONOTONIC_CLI", "MONOTONIC_UI"],
            "allowed_exclusion_reasons": ["NON_CONSEQUENTIAL_MECHANICAL", "GENERATED_METADATA_ONLY"],
            "change_set_exclude_globs": [
                "MANIFEST.json", "EVIDENCE.json", "artifacts/decision-recall-prospective/cohort-001/**"
            ],
            "frozen_instrument_sha256": frozen_map,
        }, indent=2) + "\n", encoding="utf-8")
        git(root, "add", ".")
        git(root, "commit", "-qm", "install cohort")
        return root

    def test_setup_commit_is_never_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(Path(tmp))
            status = cohort001.status_payload(root)
            self.assertEqual(status["state"], "ACCUMULATING")
            self.assertEqual(status["real_accepted_decisions"], 0)
            self.assertEqual(status["unclassified_post_activation_commits"], [])
            self.assertFalse(status["setup_commit_counts"])

    def test_post_activation_change_is_visible_until_classified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(Path(tmp))
            (root / "app.py").write_text("print('hello')\n", encoding="utf-8")
            git(root, "add", ".")
            git(root, "commit", "-qm", "real change")
            status = cohort001.status_payload(root)
            self.assertEqual(len(status["unclassified_post_activation_commits"]), 1)
            change = status["unclassified_post_activation_commits"][0]
            body = {
                "schema": cohort001.EXCLUSION_SCHEMA,
                "cohort_id": "decision-recall-cohort-001",
                "subject_change_set_sha256": change["change_set_sha256"],
                "reason": "NON_CONSEQUENTIAL_MECHANICAL",
                "detail": "test exclusion",
                "recorded_at": "2026-08-18T00:00:00Z",
            }
            body["cohort_exclusion_id"] = cohort001.content_id("decision-recall-cohort-exclusion", body)
            out = root / cohort001.COHORT_DATA_REL / "exclusions" / "x.json"
            cohort001.write(out, body)
            status = cohort001.status_payload(root)
            self.assertEqual(status["unclassified_post_activation_commits"], [])

    def test_frozen_instrument_mutation_forces_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(Path(tmp), frozen=True)
            (root / "instrument.txt").write_text("changed\n", encoding="utf-8")
            status = cohort001.status_payload(root)
            self.assertEqual(status["state"], "RESTART_REQUIRED_INSTRUMENT_MUTATED")
            self.assertFalse(status["instrument_health"]["valid"])

    def test_content_id_verification_detects_tampering(self):
        body = {
            "schema": cohort001.OBSERVATION_SCHEMA,
            "cohort_id": "decision-recall-cohort-001",
            "decision_id": "d1",
            "manifest_id": "m",
            "pre_trigger_record_id": "r",
            "subject_change_set_sha256": "a" * 64,
            "eligibility": "NATURAL_ACCEPTED_DECISION",
            "would_have_happened_without_benchmark": True,
            "consequentiality_basis": "real",
            "recorded_at": "2026-08-18T00:00:00Z",
            "capture_timing_source": "MONOTONIC_CLI",
            "setup_or_instrument_change": False,
        }
        body["cohort_observation_id"] = cohort001.content_id("decision-recall-cohort-observation", body)
        self.assertTrue(cohort001._verify_record_id(body, "cohort_observation_id", "decision-recall-cohort-observation"))
        body["decision_id"] = "tampered"
        self.assertFalse(cohort001._verify_record_id(body, "cohort_observation_id", "decision-recall-cohort-observation"))


if __name__ == "__main__":
    unittest.main()
