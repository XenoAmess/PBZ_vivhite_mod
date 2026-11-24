"""Evaluate compound source states in Cubism Core rather than merging images."""
import importlib,json
from pathlib import Path
e=importlib.import_module('extract_baiqi_components');ROOT=e.ROOT
for i in range(e.parameters):e.values[i]=e.defaults[i]
used=[]
for name in ['E-Machine-Open.exp3.json','E-Machine-Screen.exp3.json']:
    expression=json.loads((e.SRC/'Emotion'/name).read_text(encoding='utf-8'));used.append('Emotion/'+name)
    for p in expression['Parameters']:
        i=e.lookup[p['Id']];value=p['Value'];blend=p.get('Blend','Add');v=e.values[i]+value if blend=='Add' else e.values[i]*value if blend=='Multiply' else value;e.values[i]=max(e.minimum[i],min(e.maximum[i],v))
e.update(e.model);overrides=[]
for i,original in enumerate(e.records):
    current={'positions_xy':[[float(e.positions[i][j].x),float(e.positions[i][j].y)] for j in range(e.vertex_counts[i])],'opacity':float(e.alpha[i]),'draw_order':int(e.orders[i]),'render_order':int(e.render_orders[i]),'multiply_color':[float(getattr(e.multiply[i],k)) for k in ['x','y','z','w']],'screen_color':[float(getattr(e.screen[i],k)) for k in ['x','y','z','w']]}
    delta={k:v for k,v in current.items() if original[k]!=v}
    if delta:overrides.append(dict(delta,id=e.draw_names[i]))
path=ROOT/'repro/baiqi_source/core_geometry.json';source=json.loads(path.read_text(encoding='utf-8'));source['derived_variants']=[{'id':'Machine_And_Screen','sources':used,'evaluation':'combined original parameter values evaluated by Cubism Core','draw_overrides':overrides}];path.write_text(json.dumps(source,ensure_ascii=False,indent=2),encoding='utf-8');print('BAIQI_COMPOUND_STATE_EXTRACTED',len(overrides),flush=True)
