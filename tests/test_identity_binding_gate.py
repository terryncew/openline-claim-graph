import unittest
from identity_binding_gate import BindingEvidence, BindingPolicy, BindingProposal, IdentityBindingGate
POLICY = BindingPolicy(policy_id="parser-same-name-v1", min_independent_matches=2, required_attributes=("name",), hard_conflict_attributes=("birth_date", "parent", "unique_id"), authoritative_attributes=("unique_id",))
class T(unittest.TestCase):
    def setUp(self): self.gate = IdentityBindingGate(POLICY)
    def test_same_name_only_is_unresolved(self):
        g=self.gate.evaluate(BindingProposal("p","target","candidate",(BindingEvidence("name","Elene","Elene","s1"),)))
        self.assertEqual((g["disposition"],g["reason"]),("QUARANTINE","UNRESOLVED_IDENTITY")); self.assertFalse(g["semantic_truth_attested"])
    def test_corroborated_can_commit(self):
        g=self.gate.evaluate(BindingProposal("p","target","candidate",(BindingEvidence("name","Princess Elene of Georgia","Princess Elene of Georgia","s1"),BindingEvidence("family_context","daughter of Heraclius II","daughter of Heraclius II","s2"))))
        self.assertEqual((g["disposition"],g["reason"]),("COMMIT","CORROBORATED_BINDING_EARNED"))
    def test_hard_conflict_denies(self):
        g=self.gate.evaluate(BindingProposal("p","target","candidate",(BindingEvidence("name","John Smith","John Smith","s1"),BindingEvidence("birth_date","1970","1988","s2"))))
        self.assertEqual((g["disposition"],g["reason"]),("DENY","IDENTITY_CONFLICT"))
    def test_unverified_never_commits(self):
        g=self.gate.evaluate(BindingProposal("p","target","candidate",(BindingEvidence("name","A","A","s1"),BindingEvidence("family_context","B","B","s2",provenance_status="UNVERIFIED"))))
        self.assertEqual(g["reason"],"PROVENANCE_NOT_VERIFIED")
    def test_authoritative_id_can_commit(self):
        p=BindingPolicy(policy_id="auth",min_independent_matches=3,authoritative_attributes=("unique_id",))
        g=IdentityBindingGate(p).evaluate(BindingProposal("p","target","candidate",(BindingEvidence("unique_id","Q123","Q123","registry",authoritative=True),)))
        self.assertEqual(g["reason"],"AUTHORITATIVE_BINDING_EARNED")
if __name__=="__main__": unittest.main()
