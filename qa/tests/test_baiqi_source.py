import hashlib,json,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class BaiQiSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads((ROOT/'repro/baiqi_source/core_geometry.json').read_text(encoding='utf-8'))
        cls.ledger=json.loads((ROOT/'characters/baiqi/components.json').read_text(encoding='utf-8'))
    def test_every_original_part_is_in_ledger(self):
        with zipfile.ZipFile(ROOT/'resources/Delta.zip') as z:display=json.loads(z.read('Delta/Delta.cdi3.json'))
        expected={p['Id']:p['Name'] for p in display['Parts']}
        self.assertEqual(expected,{p['id']:p['source_name'] for p in self.ledger['components']})
        self.assertEqual(len(self.ledger['components']),98)
    def test_geometry_is_tied_to_the_user_moc(self):
        with zipfile.ZipFile(ROOT/'resources/Delta.zip') as z:data=z.read('Delta/Delta.moc3')
        self.assertEqual(hashlib.sha256(data).hexdigest(),self.source['source_moc_sha256'])
    def test_source_clipping_dependencies_are_complete(self):
        draws=self.source['drawables'];ids={d['id'] for d in draws};parts={p['id'] for p in self.source['parts']}
        self.assertEqual(len(ids),290)
        for d in draws:
            if d['part'] is not None:self.assertIn(d['part'],parts)
            self.assertTrue(set(d['masks'])<=ids)
            self.assertEqual(len(d['uvs']),len(d['positions_xy']))
            self.assertEqual(len(d['indices'])%3,0)
            if d['indices']:self.assertLess(max(d['indices']),len(d['uvs']))
            else:self.assertLess(len(d['uvs']),3)  # Original Cubism skinning anchors.
        grouped={d for p in self.source['parts'] for d in p['drawables']}
        unparented={d['id'] for d in draws if d['part'] is None}
        self.assertEqual(unparented,{'ArtMesh215'});self.assertEqual(grouped|unparented,ids);self.assertFalse(grouped&unparented)
    def test_all_original_presets_are_preserved(self):
        with zipfile.ZipFile(ROOT/'resources/Delta.zip') as z:expected={Path(n).name.removesuffix('.json') for n in z.namelist() if n.startswith('Delta/Emotion/') and n.endswith('.exp3.json')}
        self.assertEqual(expected,{v['id'] for v in self.source['variants']});self.assertEqual(len(expected),25)
if __name__=='__main__':unittest.main()
