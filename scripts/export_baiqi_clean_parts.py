"""Export independent source parts; clipping ancestors never enter the image."""
import json
from PIL import Image
from baiqi_source_raster import SourceRaster,ROOT
r=SourceRaster();out=ROOT/'artifacts/baiqi_component_audit/clean_parts';out.mkdir(exist_ok=True);records=[]
for part in r.source['parts']:
    state='default';r.set_state();draws=[d for d in r.drawables if d['part']==part['id']]
    if draws and not any(d['opacity']>.001 and d['indices'] for d in draws):
        variant=next((v for v in r.source['variants'] if any(d['part']==part['id'] and next((x.get('opacity',d['opacity']) for x in v['draw_overrides'] if x['id']==d['id']),d['opacity'])>.001 for d in draws)),None)
        if variant:r.set_state(variant);state=variant['id']
        else:
            for d in draws:d['opacity']=1
            state='diagnostic part opacity reveal; not an original preset'
    image=Image.fromarray(r.render({part['id']}));path=out/(part['id']+'.png');image.save(path);records.append({'id':part['id'],'source_name':part['source_name'],'path':path.name,'state':state,'bbox':image.getbbox(),'own_drawables':part['drawables'],'note':'Only this Part is painted; required masks are sampled separately. Empty container/point-anchor parts have no raster surface.'})
r.set_state();image=Image.fromarray(r.render({None}));image.save(out/'ArtMesh215.png');records.append({'id':'ArtMesh215','parent':None,'role':'original coat rear backing','path':'ArtMesh215.png','state':'default','bbox':image.getbbox()})
(out/'manifest.json').write_text(json.dumps({'role':'original_2D_evidence_not_3D_validation','parts':records},ensure_ascii=False,indent=2),encoding='utf-8');r.close();print('BAIQI_CLEAN_SOURCE_PARTS',len(records),flush=True)
