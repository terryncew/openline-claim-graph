import copy
import json
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path
from demo import (fixture, execute, verify, hash_object, signed, authorize,
                  read, inputs, conventional, page)


class AssessmentRecallTests(unittest.TestCase):
    def setUp(self):
        self.packets = fixture()
        self.bundle = execute(self.packets)
        self.checkpoint = hash_object(self.packets)

    def rejected(self, packets):
        with self.assertRaises((ValueError, KeyError)):
            execute(packets)

    def test_relevant_change_records_review_and_preserves_independent_basis(self):
        record = verify(self.bundle, self.checkpoint)
        self.assertEqual(record['statuses'], {'payments': 'REVIEW REQUIRED', 'offline-export': 'APPROVED'})
        report = self.bundle['graph']['report']
        cid = self.bundle['graph']['decision_ids']['offline-export']
        survivor = next(x for x in report['classifications']['survives'] if x['claim_id'] == cid)
        self.assertEqual(len(survivor['retained_support_claim_ids']), 1)
        self.assertEqual(record['next_authority'], 'enterprise:risk-owner')

    def test_unrelated_change_preserves_both_recorded_approvals(self):
        b = execute(fixture('unrelated'))
        self.assertEqual(list(read(b['current'], 'receiver')['statuses'].values()), ['APPROVED', 'APPROVED'])

    def test_missing_dependency_escalates_in_record(self):
        b = execute(fixture('missing'))
        self.assertEqual(read(b['current'], 'receiver')['statuses']['payments'], 'REVIEW REQUIRED')

    def test_ambiguous_meaning_escalates_both_in_record(self):
        b = execute(fixture('ambiguous'))
        self.assertEqual(set(read(b['current'], 'receiver')['statuses'].values()), {'REVIEW REQUIRED'})

    def test_tampered_event_rejected(self):
        self.packets['change']['record']['changed_field'] = 'display_name'
        self.rejected(self.packets)

    def test_untrusted_event_signer_rejected(self):
        self.packets['change'] = signed(self.packets['change']['record'], 'evaluator')
        self.rejected(self.packets)

    def test_invalid_signature_rejected(self):
        self.packets['change']['receipt']['proof']['signature'] = '00' * 64
        self.rejected(self.packets)

    def test_developer_cannot_alter_acceptance(self):
        self.packets['acceptance'] = signed(self.packets['acceptance']['record'], 'developer')
        self.rejected(self.packets)

    def test_evaluator_cannot_alter_trust_policy(self):
        self.packets['admission'] = signed(self.packets['admission']['record'], 'evaluator')
        self.rejected(self.packets)

    def test_historical_assessment_rewrite_rejected_even_if_resigned(self):
        a = copy.deepcopy(self.packets['assessment']['record'])
        a['finding'] = 'new conclusion'
        self.packets['assessment'] = signed(a, 'evaluator')
        self.rejected(self.packets)

    def test_configuration_substitution_rejected(self):
        c = copy.deepcopy(self.packets['configuration']['record'])
        c['model'] = 'different model'
        self.packets['configuration'] = signed(c, 'developer')
        self.rejected(self.packets)

    def test_old_approval_cannot_authorize_after_change(self):
        with self.assertRaises(ValueError):
            authorize(self.bundle, self.checkpoint, 'receiver')
        old = execute(fixture('unrelated'))
        with self.assertRaises(ValueError):
            authorize(old, self.checkpoint, 'receiver')

    def test_evaluation_not_enterprise_authorization(self):
        b = execute(fixture('unrelated'))
        checkpoint = hash_object(b['packets'])
        for role in ['developer', 'evaluator']:
            with self.assertRaises(ValueError):
                authorize(b, checkpoint, role)
        self.assertEqual(read(authorize(b, checkpoint, 'receiver'), 'receiver')['checkpoint'], checkpoint)

    def test_protected_output_tampering_rejected(self):
        for target in ['graph', 'current', 'baseline']:
            b = copy.deepcopy(self.bundle)
            if target == 'graph':
                b['graph']['policy']['hard_relation_ids'] = []
            elif target == 'current':
                b['current']['record']['statuses']['payments'] = 'APPROVED'
            else:
                b['baseline']['statuses']['payments'] = 'APPROVED'
            with self.subTest(target=target), self.assertRaises(ValueError):
                verify(b, self.checkpoint)

    def test_serialized_records_roundtrip(self):
        exported = json.loads(json.dumps(self.bundle))
        self.assertEqual(verify(exported, self.checkpoint)['statuses']['payments'], 'REVIEW REQUIRED')
        self.assertIn('enterprise:risk-owner', page(exported))

    def test_matched_comparator_all_cases(self):
        for variant in ['relevant', 'unrelated', 'missing', 'ambiguous']:
            b = execute(fixture(variant))
            self.assertEqual(read(b['current'], 'receiver')['statuses'], b['baseline']['statuses'])

    def test_declared_capture_gap_is_real(self):
        # Known bypass: a dishonest completeness claim cannot be discovered by either system.
        p = fixture('missing')
        a = copy.deepcopy(p['acceptance']['record'])
        a['complete']['payments'] = True
        a['dependencies']['payments'] = ['offline']
        p['acceptance'] = signed(a, 'receiver')
        b = execute(p)
        self.assertEqual(read(b['current'], 'receiver')['statuses']['payments'], 'APPROVED')
        self.assertEqual(b['baseline']['statuses']['payments'], 'APPROVED')


    def test_exported_verifier_rejects_tampered_html(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / 'bundle.json').write_text(json.dumps(self.bundle))
            (output / 'checkpoint.json').write_text(json.dumps({'checkpoint': self.checkpoint}))
            (output / 'review.html').write_text(page(self.bundle))
            command = [sys.executable, str(Path(__file__).with_name('verify.py')),
                       '--output', str(output), '--checkpoint', str(output / 'checkpoint.json')]
            good = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            (output / 'review.html').write_text('tampered: all deployments approved')
            bad = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn('review page tampered', bad.stderr)

if __name__ == '__main__':
    unittest.main(verbosity=2)
