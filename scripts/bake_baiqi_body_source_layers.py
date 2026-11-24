"""Extract original garment/accessory appearances without surrounding parts."""
import json
from PIL import Image
from baiqi_source_raster import SourceRaster,ROOT
r=SourceRaster();out=ROOT/'artifacts/baiqi_component_audit/body_layers';out.mkdir(exist_ok=True)
parts={p['id']:p for p in r.source['parts']}
def desc(name):
    result={name}
    for child in parts[name]['children']:result.update(desc(child))
    return result
groups={'shirt':desc('Shirt')-desc('Part26'),'bow_tie':desc('Part26'),'coat':desc('Coat'),'girdle':desc('Part29'),'skirt':{'Skirt'},
        'sleeve_screen_left':{'Part38','Sleeve'},'sleeve_screen_right':{'Part39','Sleeve2'},'bandage':{'Bandage'},
        'wrist_screen_left':{'Ring'},'wrist_screen_right':{'Ring3'},'legs':{'Leg2'},'shoes':{'Part41','Part42','Part43','Part44'},'machine':desc('Machine')}
records=[]
for name,selected in groups.items():
    rgba=r.render(selected);path=out/(name+'.png');Image.fromarray(rgba).save(path)
    records.append({'layer':name,'source_parts':sorted(selected),'path':path.relative_to(ROOT).as_posix(),'state':'default'})
for name,part in [('ponytails','Ponytail'),('machine','Machine'),('hand_ring','Part34')]:
    variant=next((v for v in r.source['variants'] if v['id']==('E-Hair-Ponytail.exp3' if name=='ponytails' else 'E-Machine-Open.exp3')),None)
    if name=='hand_ring':variant=None
    r.set_state(variant)
    if name=='hand_ring':
        for d in r.drawables:
            if d['part'] in desc(part):d['opacity']=1
    path=out/(name+'_enabled.png');Image.fromarray(r.render(desc(part))).save(path)
    records.append({'layer':name+'_enabled','source_parts':sorted(desc(part)),'path':path.relative_to(ROOT).as_posix(),'state':variant['id'] if variant else 'diagnostic opacity reveal; not an original preset'})
(out/'manifest.json').write_text(json.dumps(records,indent=2));r.close();print('BAIQI_BODY_SOURCE_LAYERS',len(records))
