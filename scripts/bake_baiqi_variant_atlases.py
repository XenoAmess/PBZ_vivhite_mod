"""Bake original expression/accessory states to versioned head atlases."""
import hashlib,json
from PIL import Image
from baiqi_source_raster import SourceRaster,ROOT
r=SourceRaster(2800,4400);out=ROOT/'artifacts/baiqi_component_audit/variant_atlases';out.mkdir(exist_ok=True)
parts={p['id']:p for p in r.source['parts']}
def desc(name):
    result={name}
    for child in parts[name]['children']:result.update(desc(child))
    return result
groups={'face':desc('Face')-{'Glasses'},'glasses':{'Glasses'},'hair_front':desc('Hair')|{'Mhair'},'headdress':desc('Headdress')}
states=[{'id':'default'}]+r.source['variants']
states.extend(r.source['derived_variants'])
atlases={k:Image.new('RGBA',(5280,4000)) for k in groups};rows=[]
face_shadows={d['id'] for d in r.source['drawables'] if d['part']=='Fhair' and 'Facecolor' in d['masks']}
for index,state in enumerate(states):
    r.set_state(state)
    for name,selected in groups.items():
        image=Image.fromarray(r.render(selected,include_drawables=face_shadows if name=='face' else None,exclude_drawables=face_shadows if name=='hair_front' else None)).crop((960,600,1840,1400));atlases[name].paste(image,((index%6)*880,(index//6)*800))
    rows.append({'index':index,'id':state['id'],'role':'original preset' if index in range(1,26) else 'default' if index==0 else 'derived combination'})
    print('BAIQI_STATE_BAKED',index,state['id'],flush=True)
images=[]
for name,image in atlases.items():
    path=out/(name+'.png');image.save(path);images.append({'layer':name,'path':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(out/'manifest.json').write_text(json.dumps({'character':'白绮','source_expression_presets':25,'states':rows,'source_canvas':{'width':1400,'height':2200,'crop':[480,300,920,700]},'tile':[880,800],'columns':6,'rows':5,'images':images},ensure_ascii=False,indent=2),encoding='utf-8');r.close();print('BAIQI_VARIANT_ATLASES_READY',len(states),flush=True)
