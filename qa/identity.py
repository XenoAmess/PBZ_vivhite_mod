"""Fail closed if a female foundation has not become the requested BaiQi."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def identity_reasons(review,model_sha256):
    source=json.loads((ROOT/'characters/baiqi/source_contract.json').read_text(encoding='utf-8'))
    reasons=[]
    if review.get('character')!='白绮':reasons.append('BaiQi character identity missing')
    if review.get('model_sha256')!=model_sha256:reasons.append('identity review belongs to a different model')
    def check(field,expected):
        rows=review.get(field,[]);actual={r.get('id'):r for r in rows}
        if len(actual)!=len(rows) or set(actual)!=expected:
            reasons.append('BaiQi '+field+' coverage incomplete');return
        for row in rows:
            if row.get('status')!='pass' or not row.get('target_objects') or not row.get('verification_images'):
                reasons.append('BaiQi '+field+' review incomplete or failed');break
    check('components',{p['id'] for p in source['components']})
    check('variants',{p['id'] for p in source['variants']})
    check('unparented_drawables',{p['id'] for p in source.get('unparented_drawables',[])})
    if review.get('open_defects'):reasons.append('unresolved BaiQi identity defects')
    return reasons
