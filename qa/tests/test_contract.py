import json, unittest
from pathlib import Path
from qa.motion_suite import load,acceptance
ROOT=Path(__file__).resolve().parents[2]
class ContractTests(unittest.TestCase):
    def test_unique_37_neck_cases(self):
        spec=load(ROOT/'qa/suites/humanoid_v1.json')
        cases=next(c for c in spec['cases'] if c['id']=='neck_combinations_37')['samples']
        poses=[json.dumps(s['value'],sort_keys=True) for s in cases]
        self.assertEqual(len(poses),37);self.assertEqual(len(set(poses)),37)
    def test_whole_body_coverage(self):
        ops={c['operator'] for c in load(ROOT/'qa/suites/humanoid_v1.json')['cases']}
        self.assertTrue({'neck','abduction','forward','elbow','twist','shrug','wrist','fingers','reach','spine','hip','knee','ankle','toes','squat'}<=ops)
    def fixture(self):
        m={'coverage_complete':True,'numerical_checks_passed':True,'input_hashes':{'model':'a','suite':'b'},'case_ids':['neck']}
        r={'input_hashes':dict(m['input_hashes']),'neutral_shape':'pass','cases':[{'id':'neck','status':'pass'}],'open_defects':[]}
        return m,r
    def test_numeric_pass_does_not_allow_pending_visual_review(self):
        m,r=self.fixture();r['neutral_shape']='pending'
        self.assertFalse(acceptance(m,r)['game_runtime_allowed'])
    def test_stale_review_is_rejected(self):
        m,r=self.fixture();r['input_hashes']['model']='old'
        self.assertFalse(acceptance(m,r)['game_runtime_allowed'])
    def test_missing_case_is_rejected(self):
        m,r=self.fixture();m['case_ids'].append('shoulder')
        self.assertFalse(acceptance(m,r)['game_runtime_allowed'])
    def test_open_defects_are_rejected(self):
        m,r=self.fixture();r['open_defects']=['neck rim']
        self.assertFalse(acceptance(m,r)['game_runtime_allowed'])
    def test_complete_review_can_pass(self):
        m,r=self.fixture();self.assertTrue(acceptance(m,r)['game_runtime_allowed'])
if __name__=='__main__':unittest.main()
