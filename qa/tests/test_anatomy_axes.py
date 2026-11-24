import hashlib,json,math,unittest
from pathlib import Path
from qa.anatomy_axes import finger_flexion,thumb_grip
class AnatomicalDirectionTests(unittest.TestCase):
    def test_flexion_agrees_with_original_soul_clips(self):
        data=json.loads((Path(__file__).parents[1]/'native_finger_axes.json').read_text(encoding='utf-8'))
        for side in ['l','r']:
            samples=[r for r in data['samples'] if r['bone'].endswith('_'+side)];observed=[sum(r['angle_rad']*r['bend_towards'][i] for r in samples) for i in range(3)];length=math.sqrt(sum(v*v for v in observed));axis=finger_flexion(side)
            self.assertAlmostEqual(sum(v*v for v in axis),1,places=5)
            self.assertGreater(sum(a*b/length for a,b in zip(axis,observed)),.99)
            self.assertLess(sum(a*b for a,b in zip(axis,data['previous_operator'][side]['normal'])),-.9)
    def test_thumb_reference_matches_distributed_native_source(self):
        root=Path(__file__).resolve().parents[2]
        data=json.loads((root/'qa/native_thumb_grip.json').read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256((root/data['source_clip']).read_bytes()).hexdigest(),data['source_sha256'])
        expected={f'thumb_{i:02}_{s}' for s in ['l','r'] for i in [1,2,3]}
        self.assertEqual(set(data['local_rotation_quaternions']),expected)
        for name in expected:self.assertAlmostEqual(sum(x*x for x in thumb_grip(name)),1,places=4)
