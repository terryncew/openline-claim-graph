from __future__ import annotations
import copy, json, unittest
from pathlib import Path
from openline_claim_graph.decision_recall import DecisionRecallError, create_standing_state, create_standing_event, analyze_gain_of_standing, verify_gain_report
ROOT=Path(__file__).resolve().parents[1]; CASE=ROOT/'artifacts/decision-recall-prospective/conformance'
class GainStandingTests(unittest.TestCase):
    def setUp(self): self.seal=json.loads((CASE/'stream-seal.json').read_text())
    def test_sole_missing_required_basis_becomes_reconsiderable(self):
        all_ids={x['basis_id'] for x in self.seal['eligible_bases']}; standing=sorted(all_ids-{'dep-1'})
        state=create_standing_state(stream_seal=self.seal,standing_basis_ids=standing,recorded_at='2026-08-19T12:00:00Z')
        event=create_standing_event(state=state,seal=self.seal,basis_id='dep-1',event_type='GAIN_OF_STANDING',event_at='2026-08-19T12:01:00Z',asserted_by='receiver:test',reason='restored')
        report=analyze_gain_of_standing(seal=self.seal,state=state,event=event)
        row=next(x for x in report['classifications'] if x['decision_id']=='decision-1')
        self.assertEqual('BLOCKED',row['before']); self.assertEqual('RECONSIDERABLE',row['classification'])
        self.assertTrue(verify_gain_report(report,seal=self.seal,state=state,event=event)['valid'])
    def test_unresolved_blocker_cannot_be_laundered(self):
        all_ids={x['basis_id'] for x in self.seal['eligible_bases']}; state=create_standing_state(stream_seal=self.seal,standing_basis_ids=sorted(all_ids-{'dep-1'}),unresolved_blockers={'decision-1':['policy-hold']},recorded_at='2026-08-19T12:00:00Z')
        event=create_standing_event(state=state,seal=self.seal,basis_id='dep-1',event_type='GAIN_OF_STANDING',event_at='2026-08-19T12:01:00Z',asserted_by='receiver:test',reason='restored')
        row=next(x for x in analyze_gain_of_standing(seal=self.seal,state=state,event=event)['classifications'] if x['decision_id']=='decision-1')
        self.assertEqual('AFFECTED_UNRESOLVED',row['classification'])
    def test_existing_alternative_is_not_falsely_attributed(self):
        all_ids={x['basis_id'] for x in self.seal['eligible_bases']}; standing=sorted((all_ids-{'dep-2'})|{'alt-2'})
        state=create_standing_state(stream_seal=self.seal,standing_basis_ids=standing,recorded_at='2026-08-19T12:00:00Z')
        event=create_standing_event(state=state,seal=self.seal,basis_id='dep-2',event_type='GAIN_OF_STANDING',event_at='2026-08-19T12:01:00Z',asserted_by='receiver:test',reason='restored')
        ids={x['decision_id'] for x in analyze_gain_of_standing(seal=self.seal,state=state,event=event)['classifications']}
        self.assertNotIn('decision-2',ids)
    def test_replay_stale_binding_unknown_basis_and_tamper_fail_closed(self):
        all_ids={x['basis_id'] for x in self.seal['eligible_bases']}; state=create_standing_state(stream_seal=self.seal,standing_basis_ids=sorted(all_ids),recorded_at='2026-08-19T12:00:00Z')
        event=create_standing_event(state=state,seal=self.seal,basis_id='dep-1',event_type='GAIN_OF_STANDING',event_at='2026-08-19T12:01:00Z',asserted_by='receiver:test',reason='replay')
        self.assertEqual('NO_CHANGE',event['transition']); self.assertEqual([],analyze_gain_of_standing(seal=self.seal,state=state,event=event)['classifications'])
        stale=copy.deepcopy(event); stale['pre_state_id']='decision-recall-standing-state:sha256:'+'0'*64
        with self.assertRaises(DecisionRecallError): analyze_gain_of_standing(seal=self.seal,state=state,event=stale)
        with self.assertRaises(DecisionRecallError): create_standing_event(state=state,seal=self.seal,basis_id='UNKNOWN',event_type='GAIN_OF_STANDING',event_at='2026-08-19T12:01:00Z',asserted_by='x',reason='x')
