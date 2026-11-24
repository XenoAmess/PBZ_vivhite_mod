"""DCC-independent loading, validation and fail-closed acceptance decisions."""
import hashlib, json
from pathlib import Path
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):
    spec=json.loads(Path(path).read_text(encoding='utf-8'))
    assert spec['schema_version']==1
    assert spec['skinning']=='LINEAR_BLEND'
    ids=[c['id'] for c in spec['cases']];assert len(ids)==len(set(ids))
    assert spec['passes']==['clay','textured']
    assert all(c['samples'] and c['group'] in spec['views'] for c in spec['cases'])
    return spec
def acceptance(manifest,review):
    reasons=[]
    if not manifest.get('coverage_complete'):reasons.append('missing render coverage')
    if not manifest.get('numerical_checks_passed'):reasons.append('numerical checks failed')
    if review.get('input_hashes')!=manifest.get('input_hashes'):reasons.append('review belongs to a different input')
    if review.get('neutral_shape')!='pass':reasons.append('neutral anatomy not accepted')
    expected=set(manifest.get('case_ids',[]))
    actual={r['id']:r.get('status') for r in review.get('cases',[])}
    if not expected or set(actual)!=expected or any(v!='pass' for v in actual.values()):reasons.append('case review incomplete or failed')
    if review.get('open_defects'):reasons.append('unresolved defects')
    shape=review.get('shape_check',{})
    required={s['id'] for s in json.loads((Path(__file__).parent/'shape_audit_v1.json').read_text(encoding='utf-8'))['sections']}
    sections={s['id']:s.get('status') for s in shape.get('sections',[])}
    if not shape.get('coverage_complete'):reasons.append('whole-body shape coverage missing')
    if shape.get('model_sha256')!=manifest.get('input_hashes',{}).get('model'):reasons.append('shape review belongs to a different model')
    if set(sections)!=required or any(v!='pass' for v in sections.values()):reasons.append('whole-body shape review incomplete or failed')
    if shape.get('open_defects'):reasons.append('unresolved shape defects')
    return {'status':'failed' if reasons else 'offline_accepted','game_runtime_allowed':not reasons,'reasons':reasons}
