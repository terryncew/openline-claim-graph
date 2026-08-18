from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def main() -> int:
    parser = argparse.ArgumentParser(description='Independent stdlib-only verifier for Cohort 001 instrument setup')
    parser.add_argument('--root', default='.')
    parser.add_argument('--output')
    args = parser.parse_args()
    root = Path(args.root).resolve()

    checks: list[dict[str, Any]] = []
    def check(name: str, condition: bool, detail: Any = None) -> None:
        checks.append({'name': name, 'pass': bool(condition), 'detail': detail})

    designation_path = root / 'experiments/decision-recall-prospective-001/cohort-001/DESIGNATION.json'
    cohort_doc = root / 'experiments/decision-recall-prospective-001/cohort-001/COHORT.md'
    operator_doc = root / 'experiments/decision-recall-prospective-001/cohort-001/OPERATOR_CONTRACT.md'
    policy_path = root / 'experiments/decision-recall-prospective-001/promotion-policy.json'
    ledger_readme = root / 'artifacts/decision-recall-prospective/cohort-001/README.md'

    check('designation_exists', designation_path.exists())
    check('cohort_doc_exists', cohort_doc.exists())
    check('operator_contract_exists', operator_doc.exists())
    check('ledger_readme_exists', ledger_readme.exists())
    if not designation_path.exists():
        result = {'schema': 'openline.cohort001-instrument-verification.v1', 'valid': False, 'failed_count': 1, 'check_count': len(checks), 'checks': checks}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2

    designation = load(designation_path)
    policy = load(policy_path)
    check('designation_schema', designation.get('schema') == 'openline.decision-recall-cohort-designation.v1', designation.get('schema'))
    check('cohort_id', designation.get('cohort_id') == 'decision-recall-cohort-001', designation.get('cohort_id'))
    check('protocol_id', designation.get('protocol_id') == 'decision-recall-prospective-001-v1', designation.get('protocol_id'))
    check('setup_commit_excluded', designation.get('setup_commit_counts') is False)
    check('activation_rule', designation.get('activation_rule') == 'FIRST_GIT_COMMIT_CONTAINING_DESIGNATION_THEN_DESCENDANTS_ONLY', designation.get('activation_rule'))
    check('minimum_30', designation.get('minimum_real_accepted_decisions') == 30)
    check('controlled_10', designation.get('minimum_controlled_revocations') == 10)
    check('policy_id_binding', designation.get('promotion_policy_id') == policy.get('promotion_policy_id'), designation.get('promotion_policy_id'))
    check('policy_sha_binding', designation.get('promotion_policy_sha256') == sha256_file(policy_path), designation.get('promotion_policy_sha256'))
    check('natural_only', designation.get('natural_decisions_only') is True)
    check('no_manufactured_work', designation.get('manufactured_decisions_forbidden') is True)
    check('restart_on_instrument_change', designation.get('restart_on_frozen_instrument_change') is True)
    check('capture_sources', set(designation.get('acceptable_capture_timing_sources', [])) == {'MONOTONIC_CLI', 'MONOTONIC_UI'}, designation.get('acceptable_capture_timing_sources'))

    globs = designation.get('change_set_exclude_globs', [])
    check('exclude_cohort_ledger', 'artifacts/decision-recall-prospective/cohort-001/**' in globs)
    check('exclude_manifest_generated', 'MANIFEST.json' in globs)
    check('exclude_evidence_generated', 'EVIDENCE.json' in globs)

    frozen = designation.get('frozen_instrument_sha256', {})
    check('frozen_map_nonempty', len(frozen) >= 8, len(frozen))
    for rel, expected in sorted(frozen.items()):
        path = root / rel
        observed = sha256_file(path) if path.exists() else 'MISSING'
        check(f'frozen:{rel}', observed == expected, observed)

    cohort_text = cohort_doc.read_text(encoding='utf-8') if cohort_doc.exists() else ''
    operator_text = operator_doc.read_text(encoding='utf-8') if operator_doc.exists() else ''
    check('cohort_says_zero_at_install', 'ZERO EMPIRICAL DECISIONS AT INSTALL' in cohort_text)
    check('cohort_says_no_manufacture', 'may not manufacture work' in cohort_text)
    check('cohort_says_every_commit_classified', 'observation or an explicit exclusion' in cohort_text)
    check('cohort_says_restart', 'RESTART_REQUIRED_INSTRUMENT_MUTATED' in cohort_text)
    check('operator_uses_normal_confirmation', 'ordinary ship / reject confirmation' in operator_text)
    check('operator_requires_independent_record', 'Independently construct the conventional pre-trigger record' in operator_text)
    check('operator_forbids_future_peeking', 'Do not inspect future challenge selection or later gold' in operator_text)
    check('operator_forbids_manufacture', 'Do not manufacture decisions' in operator_text)

    for subdir in ('observations', 'exclusions', 'manifests', 'pre-trigger-records'):
        directory = root / 'artifacts/decision-recall-prospective/cohort-001' / subdir
        payloads = [p for p in directory.glob('*.json')] if directory.exists() else []
        check(f'empty_empirical_{subdir}', len(payloads) == 0, len(payloads))

    manager = root / 'scripts/cohort001.py'
    check('manager_exists', manager.exists())
    check('manager_is_frozen', 'scripts/cohort001.py' in frozen)
    test_file = root / 'tests/test_cohort001.py'
    check('cohort_tests_exist', test_file.exists())

    failed = [item for item in checks if not item['pass']]
    result = {
        'schema': 'openline.cohort001-instrument-verification.v1',
        'valid': not failed,
        'disposition': 'PASS' if not failed else 'FAIL',
        'check_count': len(checks),
        'failed_count': len(failed),
        'checks': checks,
        'claim_boundary': 'This verifier checks frozen instrument custody and zero-state cohort setup only. It does not establish capture usability, selection neutrality, prospective recall accuracy, review savings, natural revocation frequency, market demand, or product promotion.'
    }
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result['valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
