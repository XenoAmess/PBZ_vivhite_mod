"""Composite original head artwork into non-overlapping appearance layers."""
import json
from PIL import Image
from baiqi_source_raster import SourceRaster,ROOT
r=SourceRaster();out=ROOT/'artifacts/baiqi_component_audit/head_layers';out.mkdir(exist_ok=True)
parts={p['id']:p for p in r.source['parts']}
def descendants(name):
    result={name}
    for child in parts[name]['children']:result.update(descendants(child))
    return result
groups={'hair_front':descendants('Hair')|descendants('Ponytail')|{'Mhair'},'hair_back':{'Bhair'},
    'face':descendants('Face')-{'Glasses'},'glasses':{'Glasses'},'headdress':descendants('Headdress')}
records=[]
face_shadows={d['id'] for d in r.source['drawables'] if d['part']=='Fhair' and 'Facecolor' in d['masks']}
for name,selected in groups.items():
    rgba=r.render(selected,occluders={'Face2'} if name=='hair_front' else None,include_drawables=face_shadows if name=='face' else None,exclude_drawables=face_shadows if name=='hair_front' else None);path=out/(name+'.png');Image.fromarray(rgba).save(path)
    records.append({'layer':name,'source_parts':sorted(selected),'included_face_shadow_drawables':sorted(face_shadows) if name=='face' else [],'excluded_face_shadow_drawables':sorted(face_shadows) if name=='hair_front' else [],'path':path.relative_to(ROOT).as_posix(),'method':'original atlas compositing with original masks and render order'})
back=Image.open(out/'hair_back.png').convert('RGBA');opaque=Image.new('RGBA',back.size,(222,234,242,255));opaque.alpha_composite(back);opaque.save(out/'hair_back_opaque.png')
(out/'manifest.json').write_text(json.dumps(records,indent=2));r.close();print('BAIQI_HEAD_APPEARANCE_LAYERS',len(records))
